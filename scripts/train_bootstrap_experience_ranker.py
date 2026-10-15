"""Train an explicitly experimental bootstrap ranker from the supplied weak-label CSV.

This script does not produce a human-verified or production-eligible artifact. It
uses the same feature builder and rule baseline as the FastAPI inference path.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
API_APP = ROOT / "apps" / "api"
if str(API_APP) not in sys.path:
    sys.path.insert(0, str(API_APP))

from app.services.ranker_baseline import RULE_BASELINE_VERSION, rule_baseline_score  # noqa: E402
from app.services.ranker_features import (  # noqa: E402
    FEATURE_VERSION,
    build_feature_row,
    feature_names_for_version,
)


DATASET_STATUS = "bootstrap_weak_labeled"
MODEL_MODE = "bootstrap_pilot"
SEED = 41
MIN_VALIDATION_NDCG5_GAIN = 0.01
REQUIRED_COLUMNS = {
    "query_id", "scenario_family_id", "poi_id", "candidate_experience_id",
    "user_intent_tags", "candidate_tags", "relevance_grade", "label_status",
    "label_method", "grade_origin", "dataset_status", "context_origin",
    "eta_origin", "slot_origin", "capacity_origin", "hard_feasible",
    "deployment_eligible", "estimated_columns", "remaining_time_min",
    "group_size", "budget_remaining_vnd", "duration_min", "eta_min",
    "price_vnd_per_person", "total_cost_vnd", "is_hands_on", "is_indoor",
}
PROVENANCE_MARKERS = {
    "label_status": "bootstrap_weak_labeled",
    "label_method": "bootstrap_rule_v1",
    "grade_origin": "deterministic_weak_rule_not_feedback",
    "dataset_status": "BOOTSTRAP_NOT_HUMAN_VERIFIED",
    "context_origin": "synthetic_scenario",
    "eta_origin": "synthetic_fixture_not_routing",
    "slot_origin": "synthetic_fixture_not_booking",
    "capacity_origin": "synthetic_fixture_not_inventory",
    "hard_feasible": "NOT_VERIFIED",
    "deployment_eligible": "FALSE",
}
FEATURE_NAMES = feature_names_for_version(FEATURE_VERSION)
WARNING = (
    "Bootstrap pilot trained on deterministic weak labels and synthetic scenario/ETA/slot/capacity "
    "fixtures. This is rule imitation only, not evidence of real traveler preference or operational "
    "availability. Planner hard constraints remain authoritative; collect consented real outcomes "
    "and human-reviewed labels before any production promotion."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_dataset(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"CSV thiếu cột bootstrap bắt buộc: {missing}")
    if frame.empty:
        raise ValueError("CSV không có bản ghi; không tạo model rỗng.")
    for column, expected in PROVENANCE_MARKERS.items():
        values = set(frame[column].astype(str).str.strip())
        if values != {expected}:
            raise ValueError(
                f"Cột {column} phải chỉ chứa provenance {expected!r}; nhận được {sorted(values)[:5]}"
            )
    if not frame["estimated_columns"].astype(str).str.strip().ne("").all():
        raise ValueError("Dataset phải giữ nguyên cột estimated_columns; không được xóa dấu dữ liệu ước tính.")
    if frame["query_id"].astype(str).str.strip().eq("").any():
        raise ValueError("Có query_id rỗng.")
    if frame["scenario_family_id"].astype(str).str.strip().eq("").any():
        raise ValueError("Có scenario_family_id rỗng; không thể chia tập chống rò rỉ.")
    duplicate_mask = frame.duplicated(["query_id", "candidate_experience_id"], keep=False)
    if duplicate_mask.any():
        raise ValueError("Có cặp query_id/candidate_experience_id trùng lặp.")
    frame["relevance_grade"] = pd.to_numeric(frame["relevance_grade"], errors="raise")
    grades = set(frame["relevance_grade"].astype(int))
    if not grades.issubset({0, 1, 2, 3}):
        raise ValueError(f"relevance_grade phải thuộc 0..3, nhận được {sorted(grades)}")
    if not np.equal(frame["relevance_grade"], frame["relevance_grade"].astype(int)).all():
        raise ValueError("relevance_grade phải là số nguyên.")
    frame["relevance_grade"] = frame["relevance_grade"].astype(int)
    candidates_per_query = frame.groupby("query_id")["candidate_experience_id"].nunique()
    if (candidates_per_query < 2).any():
        raise ValueError("Mỗi query cần ít nhất 2 ứng viên để học xếp hạng.")
    query_families = frame.groupby("query_id")["scenario_family_id"].nunique()
    if (query_families != 1).any():
        raise ValueError("Một query_id đang thuộc nhiều scenario_family_id khác nhau.")
    poi_count = frame["poi_id"].nunique()
    if poi_count < 2:
        raise ValueError("Cần ít nhất hai POI để tạo phép chia thử nghiệm có ý nghĩa tối thiểu.")
    return frame


def split_by_scenario_family(frame: pd.DataFrame, seed: int = SEED) -> dict[str, set[str]]:
    """Keep every query variant from one synthetic scenario family in one split."""
    families = sorted(frame["scenario_family_id"].astype(str).unique())
    if len(families) < 10:
        raise ValueError("Cần tối thiểu 10 scenario family để chia train/validation/test.")
    shuffled = list(families)
    random.Random(seed).shuffle(shuffled)
    train_end = max(1, int(len(shuffled) * 0.70))
    validation_count = max(1, int(len(shuffled) * 0.15))
    validation_end = min(len(shuffled) - 1, train_end + validation_count)
    return {
        "train": set(shuffled[:train_end]),
        "validation": set(shuffled[train_end:validation_end]),
        "test": set(shuffled[validation_end:]),
    }


def _as_number(row: dict[str, Any], name: str) -> float | None:
    value = row.get(name)
    if value in (None, "", "nan", "NaN"):
        return None
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (TypeError, ValueError):
        return None


def api_feature_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Build the exact online v2 features; IDs, labels and provenance are never features."""
    rows: list[dict[str, float]] = []
    for row in frame.to_dict(orient="records"):
        query = {
            "user_intent_tags": row["user_intent_tags"],
            "remaining_time_min": _as_number(row, "remaining_time_min"),
            "group_size": _as_number(row, "group_size"),
            "budget_remaining_vnd": _as_number(row, "budget_remaining_vnd"),
            "rain_mm": _as_number(row, "rain_mm"),
            "temperature_c": _as_number(row, "temperature_c"),
            "pm2_5": _as_number(row, "pm2_5"),
            "european_aqi": _as_number(row, "european_aqi"),
        }
        candidate = {
            "candidate_tags": row["candidate_tags"],
            "duration_min": _as_number(row, "duration_min"),
            "eta_min": _as_number(row, "eta_min"),
            "price_vnd_per_person": _as_number(row, "price_vnd_per_person"),
            "total_cost_vnd": _as_number(row, "total_cost_vnd"),
            "is_hands_on": row["is_hands_on"],
            "is_indoor": row["is_indoor"],
        }
        rows.append(build_feature_row(query, candidate))
    return pd.DataFrame(rows, columns=FEATURE_NAMES)


def ndcg_at_k(frame: pd.DataFrame, scores: np.ndarray, k: int) -> tuple[float, float]:
    """Return mean NDCG@k and standard deviation over query groups."""
    work = frame[["query_id", "relevance_grade"]].copy()
    work["score"] = np.asarray(scores, dtype=float)
    values: list[float] = []
    for _query_id, group in work.groupby("query_id", sort=False):
        labels = group["relevance_grade"].to_numpy(dtype=float)
        predictions = group["score"].to_numpy(dtype=float)
        order = np.argsort(-predictions, kind="stable")[:k]
        ideal = np.argsort(-labels, kind="stable")[:k]
        discounts = 1.0 / np.log2(np.arange(2, len(order) + 2))
        dcg = float(np.sum((np.power(2.0, labels[order]) - 1.0) * discounts))
        ideal_discounts = 1.0 / np.log2(np.arange(2, len(ideal) + 2))
        idcg = float(np.sum((np.power(2.0, labels[ideal]) - 1.0) * ideal_discounts))
        values.append(dcg / idcg if idcg else 0.0)
    return (float(np.mean(values)), float(np.std(values, ddof=0))) if values else (0.0, 0.0)


def baseline_scores(frame: pd.DataFrame) -> np.ndarray:
    scores = []
    for row in frame.to_dict(orient="records"):
        scores.append(rule_baseline_score(
            {"user_intent_tags": row["user_intent_tags"]},
            {"candidate_tags": row["candidate_tags"]},
        ))
    return np.asarray(scores, dtype=float)


def query_groups(frame: pd.DataFrame) -> list[int]:
    return [int(count) for count in frame.groupby("query_id", sort=False).size().tolist()]


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def run_training(csv_path: Path, output_dir: Path) -> Path:
    try:
        import xgboost as xgb
    except ImportError as error:
        raise RuntimeError("Cài xgboost trước khi train: pip install 'xgboost>=3.4.1,<4.0'") from error

    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Thư mục output không rỗng; chọn thư mục mới để tránh ghi đè: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    frame = validate_dataset(csv_path)
    split_families = split_by_scenario_family(frame)
    split_by_name: dict[str, pd.DataFrame] = {}
    for name, family_ids in split_families.items():
        split_frame = frame.loc[frame["scenario_family_id"].isin(family_ids)].copy()
        split_frame = split_frame.sort_values(["query_id", "candidate_experience_id"], kind="stable").reset_index(drop=True)
        if split_frame.empty:
            raise ValueError(f"Tập {name} rỗng sau khi chia theo scenario_family_id.")
        split_by_name[name] = split_frame

    train = split_by_name["train"]
    validation = split_by_name["validation"]
    test = split_by_name["test"]
    features = {name: api_feature_rows(part) for name, part in split_by_name.items()}

    # One small, fixed configuration: no tuning on a 60-family synthetic set.
    model = xgb.XGBRanker(
        objective="rank:ndcg",
        eval_metric="ndcg@5",
        n_estimators=160,
        max_depth=3,
        learning_rate=0.04,
        subsample=0.85,
        colsample_bytree=0.9,
        reg_lambda=2.0,
        tree_method="hist",
        random_state=SEED,
        n_jobs=2,
    )
    model.fit(
        features["train"],
        train["relevance_grade"].to_numpy(dtype=int),
        group=query_groups(train),
        verbose=False,
    )

    validation_model = np.asarray(model.predict(features["validation"]), dtype=float)
    validation_baseline = baseline_scores(validation)
    val_model_5, val_model_5_std = ndcg_at_k(validation, validation_model, 5)
    val_rule_5, val_rule_5_std = ndcg_at_k(validation, validation_baseline, 5)
    val_model_10, val_model_10_std = ndcg_at_k(validation, validation_model, 10)
    val_rule_10, val_rule_10_std = ndcg_at_k(validation, validation_baseline, 10)
    selected_runtime = (
        "bootstrap_xgboost_pilot"
        if val_model_5 >= val_rule_5 + MIN_VALIDATION_NDCG5_GAIN
        else RULE_BASELINE_VERSION
    )

    # The test split is only evaluated after the validation-based runtime comparison above.
    test_prediction_parts: list[np.ndarray] = []
    inference_ms_per_query: list[float] = []
    for _query_id, positions in test.groupby("query_id", sort=False).indices.items():
        batch = features["test"].iloc[list(positions)]
        started = time.perf_counter()
        prediction = np.asarray(model.predict(batch), dtype=float)
        inference_ms_per_query.append((time.perf_counter() - started) * 1000.0)
        test_prediction_parts.append(prediction)
    test_model = np.concatenate(test_prediction_parts)
    test_baseline = baseline_scores(test)
    test_model_5, test_model_5_std = ndcg_at_k(test, test_model, 5)
    test_rule_5, test_rule_5_std = ndcg_at_k(test, test_baseline, 5)
    test_model_10, test_model_10_std = ndcg_at_k(test, test_model, 10)
    test_rule_10, test_rule_10_std = ndcg_at_k(test, test_baseline, 10)

    model_file = "xgboost_ranker.json"
    model_path = output_dir / model_file
    model.save_model(str(model_path))
    model_sha = sha256_file(model_path)
    dataset_sha = sha256_file(csv_path)
    created_at = datetime.now(UTC).isoformat()
    metadata = {
        "model_version": f"localexplorer-bootstrap-xgb-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}",
        "model_family": "xgboost",
        "model_file": model_file,
        "model_sha256": model_sha,
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "dataset_status": DATASET_STATUS,
        "model_mode": MODEL_MODE,
        "pilot_runtime_eligible": True,
        "deployment_eligible": False,
        "production_eligible": False,
        "runtime_recommendation_by_validation_ndcg_at_5": selected_runtime,
        "label_provenance": "bootstrap_rule_v1; deterministic weak labels; not traveler feedback",
        "source_dataset_name": csv_path.name,
        "source_dataset_sha256": dataset_sha,
        "model_parameters": {
            "objective": "rank:ndcg",
            "n_estimators": 160,
            "max_depth": 3,
            "learning_rate": 0.04,
            "subsample": 0.85,
            "colsample_bytree": 0.9,
            "reg_lambda": 2.0,
            "tree_method": "hist",
            "random_seed": SEED,
        },
        "estimated_columns_preserved": True,
        "created_at_utc": created_at,
        "warning": WARNING,
        "reproducibility": {"random_seed": SEED, "xgboost_version": xgb.__version__},
    }
    schema = {
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "feature_builder": "apps/api/app/services/ranker_features.py::build_feature_row",
        "target": "relevance_grade (weak bootstrap labels only)",
        "excluded_columns": [
            "query_id", "scenario_family_id", "poi_id", "candidate_experience_id",
            "candidate_slot_id", "relevance_grade", "label_rationale", "label_status",
            "label_method", "grade_origin", "estimated_columns", "source/provenance fields",
        ],
    }
    preprocessing = {
        "strategy": "none; native XGBoost missing-value handling",
        "fit_scope": "No learned preprocessing was fitted. Features are created by the shared API function.",
        "feature_version": FEATURE_VERSION,
        "unknown_values": "Preserved as missing where the shared feature builder specifies NaN.",
    }
    metrics = {
        "dataset_status": DATASET_STATUS,
        "model_mode": MODEL_MODE,
        "warning": WARNING,
        "split_method": "70/15/15 by scenario_family_id; all query variants in a family stay together",
        "split_counts": {
            name: {
                "scenario_families": len(split_families[name]),
                "queries": int(part["query_id"].nunique()),
                "rows": int(len(part)),
            }
            for name, part in split_by_name.items()
        },
        "validation": {
            "xgboost_ndcg_at_5_mean": val_model_5,
            "xgboost_ndcg_at_5_std": val_model_5_std,
            "rule_baseline_ndcg_at_5_mean": val_rule_5,
            "rule_baseline_ndcg_at_5_std": val_rule_5_std,
            "xgboost_ndcg_at_10_mean": val_model_10,
            "xgboost_ndcg_at_10_std": val_model_10_std,
            "rule_baseline_ndcg_at_10_mean": val_rule_10,
            "rule_baseline_ndcg_at_10_std": val_rule_10_std,
            "selected_runtime": selected_runtime,
            "minimum_ndcg_at_5_gain_to_recommend_model": MIN_VALIDATION_NDCG5_GAIN,
        },
        "test_after_validation_selection": {
            "xgboost_ndcg_at_5_mean": test_model_5,
            "xgboost_ndcg_at_5_std": test_model_5_std,
            "rule_baseline_ndcg_at_5_mean": test_rule_5,
            "rule_baseline_ndcg_at_5_std": test_rule_5_std,
            "xgboost_ndcg_at_10_mean": test_model_10,
            "xgboost_ndcg_at_10_std": test_model_10_std,
            "rule_baseline_ndcg_at_10_mean": test_rule_10,
            "rule_baseline_ndcg_at_10_std": test_rule_10_std,
        },
        "source_data": {
            "file_name": csv_path.name,
            "sha256": dataset_sha,
            "rows": int(len(frame)),
            "queries": int(frame["query_id"].nunique()),
            "scenario_families": int(frame["scenario_family_id"].nunique()),
            "pois": int(frame["poi_id"].nunique()),
            "grade_distribution": {str(key): int(value) for key, value in frame["relevance_grade"].value_counts().sort_index().items()},
            "training_eligible_field_ignored": True,
            "all_rows_are_weak_and_estimated": True,
        },
        "model_size_bytes": model_path.stat().st_size,
        "model_inference_runtime_ms_per_query_median": float(np.median(inference_ms_per_query)),
        "model_inference_runtime_ms_per_query_p95": float(np.percentile(inference_ms_per_query, 95)),
        "note": "No real-user, booking, verified-route, provider-slot, or capacity evidence is present.",
    }
    write_json(output_dir / "model_metadata.json", metadata)
    write_json(output_dir / "feature_schema.json", schema)
    write_json(output_dir / "preprocessing.json", preprocessing)
    write_json(output_dir / "metrics.json", metrics)

    validation_comparison = pd.DataFrame([
        {"split": "validation", "model": "xgboost_ranker", "ndcg_at_5": val_model_5, "ndcg_at_10": val_model_10},
        {"split": "validation", "model": RULE_BASELINE_VERSION, "ndcg_at_5": val_rule_5, "ndcg_at_10": val_rule_10},
        {"split": "test_after_selection", "model": "xgboost_ranker", "ndcg_at_5": test_model_5, "ndcg_at_10": test_model_10},
        {"split": "test_after_selection", "model": RULE_BASELINE_VERSION, "ndcg_at_5": test_rule_5, "ndcg_at_10": test_rule_10},
    ])
    validation_comparison.to_csv(output_dir / "validation_comparison.csv", index=False)
    test_predictions = test[["query_id", "scenario_family_id", "poi_id", "candidate_experience_id", "relevance_grade"]].copy()
    test_predictions["xgboost_score"] = test_model
    test_predictions["rule_baseline_score"] = test_baseline
    test_predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    card = f"""# LocalExplorerAI bootstrap ranker (experimental)

- Mode: `{MODEL_MODE}`
- Dataset status: `{DATASET_STATUS}`
- Selected runtime by validation NDCG@5: `{selected_runtime}`
- Validation NDCG@5: XGBoost `{val_model_5:.4f}`; rule baseline `{val_rule_5:.4f}`
- Test NDCG@5 (read after validation selection): XGBoost `{test_model_5:.4f}`; rule baseline `{test_rule_5:.4f}`
- POIs: {frame['poi_id'].nunique()}; queries: {frame['query_id'].nunique()}; scenario families: {frame['scenario_family_id'].nunique()}

## Limitations

The labels come from deterministic `bootstrap_rule_v1`, not travelers. Scenario, ETA, slot, and capacity inputs include synthetic/estimated values; no candidate is operationally verified by this CSV. This benchmark measures imitation of the bootstrap labeling process only. The family split prevents related scenario variants crossing splits, but POIs repeat between splits and this small sample does not establish generalization to new places, users, or intents. The feature allowlist excludes IDs, labels/rationales, and provenance.

This artifact is explicitly **not production eligible**. The API accepts it only when `ENABLE_BOOTSTRAP_RANKER=true` and reports a warning; production eligibility and deployment eligibility remain false. The planner must continue to enforce hard time, budget, availability, capacity, locked-stop, and route constraints before scoring.

## Next data collection

Log the alternatives actually shown, planner decisions, booking/completion/cancellation outcomes, consented post-trip feedback, and reviewed human grades. Replace weak labels only with adjudicated evidence; do not promote by editing metadata.
"""
    (output_dir / "model_card.md").write_text(card, encoding="utf-8")

    bundle_path = output_dir / "localexplorer_bootstrap_ranker_bundle.zip"
    bundle_files = [
        model_file, "model_metadata.json", "feature_schema.json", "preprocessing.json",
        "metrics.json", "validation_comparison.csv", "test_predictions.csv", "model_card.md",
    ]
    with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename in bundle_files:
            archive.write(output_dir / filename, arcname=filename)
    return bundle_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True, help="CSV bootstrap đã cung cấp")
    parser.add_argument("--output-dir", type=Path, required=True, help="Thư mục output mới, phải rỗng/chưa tồn tại")
    args = parser.parse_args()
    if not args.csv.is_file():
        raise FileNotFoundError(f"Không tìm thấy CSV: {args.csv}")
    bundle = run_training(args.csv.resolve(), args.output_dir.resolve())
    print(f"Bundle: {bundle}")
    print(f"Metrics: {args.output_dir.resolve() / 'metrics.json'}")


if __name__ == "__main__":
    main()
