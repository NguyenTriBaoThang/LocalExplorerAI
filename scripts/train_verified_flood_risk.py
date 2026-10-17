"""Train a flood classifier only from traceable, directly verified observations.

This intentionally refuses report-absence pseudo-negatives and never generates labels.
The output remains blocked from inference unless a reviewer approves deployment and the
held-out chronological metrics pass the minimum quality gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data/training/flood_risk_verified_template.csv"
DEFAULT_OUTPUT = ROOT / "models/flood-risk-candidate"
MINIMUMS = {"verified_flood": 100, "verified_no_flood": 200, "edges_per_class": 20, "groups_per_class": 20}
NUMERIC_FEATURES = [
    "horizon_min", "rain_15m_mm", "rain_30m_mm", "rain_60m_mm", "rain_180m_mm",
    "rain_forecast_15m_mm", "rain_forecast_30m_mm", "rain_forecast_60m_mm", "elevation_m",
    "slope_pct", "depression_index", "distance_to_canal_m", "tide_level_m", "tide_change_30m_m",
    "drainage_density_km2", "road_width_m", "nearby_flood_reports_30m", "latest_depth_cm",
    "observation_age_min", "coverage_ratio",
]
CATEGORICAL_FEATURES = ["region", "road_class"]
FEATURE_COLUMNS = NUMERIC_FEATURES + CATEGORICAL_FEATURES
TIME_COLUMNS = ["decision_time", "issued_at", "received_at", "label_window_start", "label_window_end", "observed_at", "reviewed_at"]
REQUIRED_COLUMNS = {
    "sample_id", "edge_id", "decision_time", "issued_at", "received_at", "horizon_min", "region", "road_class",
    "observation_group_id", "target_flood", "label_status", "label_window_start", "label_window_end",
    "observed_at", "label_coverage_ratio", "source_id", "source_url", "evidence_url",
    "provenance_type", "spatial_precision", "reviewer_id", "reviewed_at",
    *NUMERIC_FEATURES[1:],
}
ALLOWED_PROVENANCE = {
    "official_monitoring", "field_audit", "field_report", "road_sensor",
    "camera_review", "partner_confirmation",
}


def _iso_utc(value: object, column: str, index: int) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise ValueError(f"Row {index + 2}: {column} is required.")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"Row {index + 2}: {column} must be an ISO-8601 timestamp with a timezone.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"Row {index + 2}: {column} must include a timezone offset.")
    return parsed.astimezone(timezone.utc)


def _https(value: object, column: str, index: int) -> str:
    text = str(value).strip()
    try:
        parsed = urlsplit(text)
    except ValueError as error:
        raise ValueError(f"Row {index + 2}: {column} must be a valid HTTPS evidence URL.") from error
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError(f"Row {index + 2}: {column} must be a valid HTTPS evidence URL.")
    return text


def _load_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("Dataset is missing required columns: " + ", ".join(missing))
    if frame.empty:
        raise ValueError("No observations supplied. The verified template is header-only; collect real audited observations first.")

    for column in ("sample_id", "edge_id", "observation_group_id", "label_status", "source_id", "reviewer_id", "provenance_type"):
        frame[column] = frame[column].str.strip()
        if frame[column].eq("").any():
            raise ValueError(f"{column} must be present for every observation.")
    if frame["sample_id"].duplicated().any():
        raise ValueError("sample_id values must be unique.")

    frame["target_flood"] = pd.to_numeric(frame["target_flood"], errors="coerce")
    if frame["target_flood"].isna().any() or not frame["target_flood"].isin([0, 1]).all():
        raise ValueError("target_flood must be explicitly labeled 0 or 1 for every row; no labels are inferred.")
    expected_status = frame["target_flood"].map({0: "verified_no_flood", 1: "verified_flood"})
    if not frame["label_status"].eq(expected_status).all():
        raise ValueError("target_flood must agree exactly with verified_flood / verified_no_flood label_status.")
    if not frame["provenance_type"].str.strip().str.lower().isin(ALLOWED_PROVENANCE).all():
        raise ValueError("Unsupported provenance_type. Use a direct monitoring, sensor, field, camera, or partner verification method.")

    for column in ("source_url", "evidence_url"):
        frame[column] = [_https(value, column, i) for i, value in enumerate(frame[column])]
    for column in TIME_COLUMNS:
        frame[column] = [_iso_utc(value, column, i) for i, value in enumerate(frame[column])]
    if (frame["issued_at"] > frame["decision_time"]).any() or (frame["received_at"] > frame["decision_time"]).any():
        raise ValueError("Feature source issue/receive times must be at or before decision_time to prevent look-ahead leakage.")
    if (frame["reviewed_at"] < frame["observed_at"]).any():
        raise ValueError("reviewed_at cannot precede the labeled observation.")
    frame["horizon_min"] = pd.to_numeric(frame["horizon_min"], errors="coerce")
    if frame["horizon_min"].isna().any() or not frame["horizon_min"].between(1, 1440).all() or not frame["horizon_min"].mod(1).eq(0).all():
        raise ValueError("horizon_min must be a whole number between 1 and 1440.")

    durations = frame["label_window_end"] - frame["label_window_start"]
    if (durations <= pd.Timedelta(0)).any():
        raise ValueError("Every label window must have a positive duration.")
    if (frame["label_window_start"] < frame["decision_time"]).any():
        raise ValueError("Label windows must begin at or after decision_time; future outcomes must not leak into features.")
    horizon_ends = frame["decision_time"] + pd.to_timedelta(frame["horizon_min"], unit="m")
    if (frame["label_window_end"] > horizon_ends).any():
        raise ValueError("A label window extends beyond its decision horizon.")
    if ((frame["observed_at"] < frame["label_window_start"]) | (frame["observed_at"] > frame["label_window_end"])).any():
        raise ValueError("observed_at must fall within its labeled observation window.")

    frame["label_coverage_ratio"] = pd.to_numeric(frame["label_coverage_ratio"], errors="coerce")
    negative = frame["target_flood"].eq(0)
    provided_coverage = frame["label_coverage_ratio"].dropna()
    if not provided_coverage.between(0, 1).all():
        raise ValueError("label_coverage_ratio must be between 0 and 1.")
    if frame.loc[negative, "label_coverage_ratio"].isna().any() or not frame.loc[negative, "label_coverage_ratio"].ge(0.95).all():
        raise ValueError("Verified no-flood labels require at least 95% directly observed coverage over the label window.")
    if frame["spatial_precision"].str.strip().str.lower().isin({"low", "unknown", ""}).any():
        raise ValueError("All road-edge flood labels need edge-level or better spatial precision.")

    frame["target_flood"] = frame["target_flood"].astype(int)
    for column in NUMERIC_FEATURES:
        if column not in frame:
            frame[column] = np.nan
        raw = frame[column].replace("", np.nan)
        frame[column] = pd.to_numeric(raw, errors="coerce")
        if (raw.notna() & frame[column].isna()).any():
            raise ValueError(f"{column} contains a non-numeric feature value.")
    if frame["coverage_ratio"].dropna().between(0, 1).eq(False).any():
        raise ValueError("coverage_ratio must be between 0 and 1.")
    for column in ("rain_15m_mm", "rain_30m_mm", "rain_60m_mm", "rain_180m_mm", "rain_forecast_15m_mm",
                   "rain_forecast_30m_mm", "rain_forecast_60m_mm", "depression_index", "distance_to_canal_m",
                   "drainage_density_km2", "road_width_m", "nearby_flood_reports_30m", "latest_depth_cm", "observation_age_min"):
        if frame[column].dropna().lt(0).any():
            raise ValueError(f"{column} cannot be negative.")
    if frame["depression_index"].dropna().gt(1).any():
        raise ValueError("depression_index must be between 0 and 1.")
    for column in CATEGORICAL_FEATURES:
        frame[column] = frame[column].replace("", "unknown").fillna("unknown")
    duplicates = frame.duplicated(["edge_id", "decision_time", "horizon_min"])
    if duplicates.any():
        raise ValueError("Duplicate edge_id + decision_time + horizon_min samples are not allowed.")
    return frame


def _check_minimums(frame: pd.DataFrame) -> dict[str, int]:
    counts = {}
    for label, status in ((1, "verified_flood"), (0, "verified_no_flood")):
        rows = frame[frame["target_flood"] == label]
        counts[status] = len(rows)
        counts[f"{status}_edges"] = rows["edge_id"].nunique()
        counts[f"{status}_groups"] = rows["observation_group_id"].nunique()
    if counts["verified_flood"] < MINIMUMS["verified_flood"]:
        raise ValueError(f"Need at least {MINIMUMS['verified_flood']} verified flood observations; found {counts['verified_flood']}.")
    if counts["verified_no_flood"] < MINIMUMS["verified_no_flood"]:
        raise ValueError(f"Need at least {MINIMUMS['verified_no_flood']} verified no-flood observations; found {counts['verified_no_flood']}.")
    for status in ("verified_flood", "verified_no_flood"):
        if counts[f"{status}_edges"] < MINIMUMS["edges_per_class"]:
            raise ValueError(f"Need at least {MINIMUMS['edges_per_class']} distinct road edges for {status}; found {counts[f'{status}_edges']}.")
        if counts[f"{status}_groups"] < MINIMUMS["groups_per_class"]:
            raise ValueError(f"Need at least {MINIMUMS['groups_per_class']} distinct observation groups for {status}; found {counts[f'{status}_groups']}.")
    return counts


def _temporal_group_split(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    group_times = frame.groupby("observation_group_id")["decision_time"].max().sort_values()
    groups = list(group_times.index)
    validation_start = math.floor(len(groups) * 0.60)
    test_start = math.floor(len(groups) * 0.80)
    train_groups, validation_groups, test_groups = set(groups[:validation_start]), set(groups[validation_start:test_start]), set(groups[test_start:])
    masks = [frame["observation_group_id"].isin(group_set).to_numpy() for group_set in (train_groups, validation_groups, test_groups)]
    for name, mask in zip(("train", "validation", "test"), masks, strict=True):
        if len(np.unique(frame.loc[mask, "target_flood"])) != 2:
            raise ValueError(f"The chronological {name} split does not contain both labels. Collect more independent groups over time.")
    return tuple(np.flatnonzero(mask) for mask in masks)  # type: ignore[return-value]


def _calibrate(raw: np.ndarray, target: np.ndarray) -> tuple[dict[str, float | str], np.ndarray]:
    clipped = np.clip(raw, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped)).reshape(-1, 1)
    calibrator = LogisticRegression(C=1e4, solver="lbfgs", random_state=42).fit(logits, target)
    calibrated = calibrator.predict_proba(logits)[:, 1]
    return {"method": "sigmoid", "coef": float(calibrator.coef_[0, 0]), "intercept": float(calibrator.intercept_[0])}, calibrated


def _apply_calibrator(spec: dict[str, float | str], raw: np.ndarray) -> np.ndarray:
    clipped = np.clip(raw, 1e-6, 1 - 1e-6)
    logits = np.log(clipped / (1 - clipped))
    z = float(spec["coef"]) * logits + float(spec["intercept"])
    return 1 / (1 + np.exp(-z))


def _threshold(target: np.ndarray, probability: np.ndarray) -> tuple[float, float]:
    candidates = []
    for value in np.linspace(0.05, 0.95, 181):
        predicted = probability >= value
        recall = recall_score(target, predicted, zero_division=0)
        if recall < 0.85:
            continue
        true_positive = np.sum((target == 1) & predicted)
        false_positive = np.sum((target == 0) & predicted)
        precision = true_positive / max(1, true_positive + false_positive)
        f2 = (5 * precision * recall) / max(1e-12, 4 * precision + recall)
        candidates.append((f2, float(value), float(recall)))
    if not candidates:
        return 0.5, float(recall_score(target, probability >= 0.5, zero_division=0))
    _, value, recall = max(candidates)
    return value, recall


def _metrics(target: np.ndarray, probability: np.ndarray, threshold: float) -> dict[str, float]:
    return {
        "average_precision": float(average_precision_score(target, probability)),
        "roc_auc": float(roc_auc_score(target, probability)),
        "brier_score": float(brier_score_loss(target, probability)),
        "recall_at_threshold": float(recall_score(target, probability >= threshold, zero_division=0)),
    }


def train(input_path: Path, output_path: Path, approve_deployment: bool) -> dict:
    frame = _load_dataset(input_path)
    counts = _check_minimums(frame)
    train_idx, validation_idx, test_idx = _temporal_group_split(frame)
    numeric = Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True))])
    categorical = Pipeline([("imputer", SimpleImputer(strategy="constant", fill_value="unknown")),
                            ("onehot", OneHotEncoder(handle_unknown="ignore"))])
    preprocessor = ColumnTransformer([("numeric", numeric, NUMERIC_FEATURES), ("categorical", categorical, CATEGORICAL_FEATURES)])
    model = RandomForestClassifier(n_estimators=500, min_samples_leaf=3, max_features="sqrt",
                                   class_weight="balanced_subsample", n_jobs=-1, random_state=42)
    transformed_train = preprocessor.fit_transform(frame.iloc[train_idx][FEATURE_COLUMNS])
    model.fit(transformed_train, frame.iloc[train_idx]["target_flood"])

    raw_validation = model.predict_proba(preprocessor.transform(frame.iloc[validation_idx][FEATURE_COLUMNS]))[:, 1]
    calibrator, validation_probability = _calibrate(raw_validation, frame.iloc[validation_idx]["target_flood"].to_numpy())
    threshold, validation_recall = _threshold(frame.iloc[validation_idx]["target_flood"].to_numpy(), validation_probability)
    raw_test = model.predict_proba(preprocessor.transform(frame.iloc[test_idx][FEATURE_COLUMNS]))[:, 1]
    test_metrics = _metrics(frame.iloc[test_idx]["target_flood"].to_numpy(), _apply_calibrator(calibrator, raw_test), threshold)
    quality_passed = test_metrics["average_precision"] >= 0.50 and test_metrics["brier_score"] <= 0.20 and test_metrics["recall_at_threshold"] >= 0.80
    if output_path.exists():
        raise FileExistsError(f"Output directory already exists: {output_path}. Choose a new candidate path.")
    output_path.mkdir(parents=True)
    joblib.dump(model, output_path / "model.joblib")
    joblib.dump(preprocessor, output_path / "preprocessor.joblib")
    (output_path / "feature_schema.json").write_text(json.dumps({
        "schema_version": 1, "numeric_features": NUMERIC_FEATURES, "categorical_features": CATEGORICAL_FEATURES,
    }, indent=2), encoding="utf-8")
    (output_path / "calibration.json").write_text(json.dumps(calibrator, indent=2), encoding="utf-8")
    (output_path / "threshold.json").write_text(json.dumps({
        "threshold": threshold, "selection_metric": "validation_f2_at_recall_ge_0.85", "validation_recall": validation_recall,
    }, indent=2), encoding="utf-8")
    metadata = {
        "model_version": f"flood-risk-rf-v1-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "model_family": "RandomForestClassifier",
        "dataset_status": "verified_human_labeled",
        "demo_mode": False,
        "deployment_eligible": bool(approve_deployment and quality_passed),
        "deployment_approval_required": True,
        "deployment_gate": {"quality_passed": quality_passed, "minimum_test_average_precision": 0.50,
                            "maximum_test_brier_score": 0.20, "minimum_test_recall": 0.80},
        "verified_observations": counts,
        "split": {"method": "chronological_group_60_20_20", "train_rows": len(train_idx),
                  "validation_rows": len(validation_idx), "test_rows": len(test_idx)},
        "metrics": {"validation_recall_at_threshold": validation_recall, "test": test_metrics},
        "threshold": threshold,
        "input_sha256": hashlib.sha256(input_path.read_bytes()).hexdigest(),
        "feature_contract": "apps/api/app/schemas/ml.py::FloodRiskSample",
    }
    (output_path / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--approve-deployment", action="store_true", help="Mark the bundle deployable only if held-out metrics pass the gate.")
    args = parser.parse_args()
    try:
        metadata = train(args.input, args.output, args.approve_deployment)
    except (ValueError, FileNotFoundError, FileExistsError, pd.errors.ParserError) as error:
        parser.error(str(error))
    print(json.dumps(metadata, indent=2))
    if not metadata["deployment_eligible"]:
        print("Candidate bundle was written but is blocked from API inference; review provenance/metrics and explicitly approve deployment if appropriate.")


if __name__ == "__main__":
    main()
