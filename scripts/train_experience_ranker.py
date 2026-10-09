"""Compare ranking models on the explicitly weak-labeled POI experiment.

The supplied dataset is not human preference data. This script deliberately
keeps that fact in every output and will only export an ML bundle when it
meaningfully beats the rule baseline on validation. It never loads joblib or
pickle files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.ranker_baseline import rule_baseline_score  # noqa: E402
from app.services.ranker_features import (  # noqa: E402
    FEATURE_NAMES,
    FEATURE_VERSION,
    build_feature_row,
)


DEFAULT_DATA = ROOT / "data" / "experimental" / "ranking" / "ranking_candidates_labeled.csv"
DEFAULT_OUTPUT = ROOT / "models" / "ai-ranker" / "weak-experiment"
EXPECTED_WEAK_LABEL_METHOD = "category_rule_weak_label"
FORBIDDEN_FEATURE_COLUMNS = {
    "relevance_grade", "label_rationale", "label_evidence", "label_method",
    "reviewer_id", "poi_id", "candidate_experience_id", "candidate_slot_id",
    "candidate_source_ref", "candidate_verification_status", "query_source",
    "decision_time", "planner_checked_at", "planner_source_ref", "capture_id",
    "feature_provenance", "estimated_columns", "training_eligible",
}
MIN_MEANINGFUL_NDCG5_GAIN = 0.01
TUNING_CONFIGS = (
    {"max_depth": 2, "n_estimators": 50},
    {"max_depth": 2, "n_estimators": 100},
    {"max_depth": 3, "n_estimators": 50},
    {"max_depth": 3, "n_estimators": 100},
)
STABILITY_SEEDS = (17, 41, 73)
LABEL_GAIN = [0, 1, 3, 7]


class DatasetContractError(ValueError):
    """Raised when provenance or ranking data do not match the selected mode."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_weak_dataset(path: Path, mode: str) -> pd.DataFrame:
    if mode != "weak_label":
        raise DatasetContractError(
            "This dataset can only run with --mode weak_label. It has no human labels, verified slots, or planner evidence."
        )
    frame = pd.read_csv(path, encoding="utf-8-sig")
    required = {
        "query_id", "poi_id", "candidate_tags", "user_intent_tags",
        "duration_min", "price_vnd_per_person", "eta_min", "is_hands_on",
        "is_indoor", "relevance_grade", "label_method", "label_rationale",
        "estimated_columns", "estimated_resource_feasible", "candidate_slot_id",
        "candidate_verification_status", "training_eligible", "query_source",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise DatasetContractError(f"Missing required columns: {missing}")
    if frame.empty:
        raise DatasetContractError("The ranking CSV is empty.")
    if frame[list(required)].isna().all(axis=1).any():
        raise DatasetContractError("The CSV contains a completely empty candidate row.")
    if not frame["label_method"].fillna("").eq(EXPECTED_WEAK_LABEL_METHOD).all():
        raise DatasetContractError("Only the declared category_rule_weak_label mode is accepted here.")
    if not frame["query_source"].fillna("").eq("analyst_assumed_scenario").all():
        raise DatasetContractError("The query contexts are not the declared assumed scenarios.")
    if frame["training_eligible"].fillna(True).astype(str).str.casefold().isin({"true", "1", "yes"}).any():
        raise DatasetContractError("Weak rows must not be relabeled training_eligible=true.")
    if frame["candidate_verification_status"].fillna("").ne("osm_record_not_operationally_verified").any():
        raise DatasetContractError("Expected OSM source rows with operational status explicitly unverified.")
    grades = pd.to_numeric(frame["relevance_grade"], errors="raise")
    if not grades.isin([0, 1, 2, 3]).all():
        raise DatasetContractError("relevance_grade must be an integer in [0, 3].")
    if not np.equal(grades.to_numpy(), np.floor(grades.to_numpy())).all():
        raise DatasetContractError("relevance_grade values must be integers.")
    if frame.duplicated(["query_id", "poi_id"]).any():
        raise DatasetContractError("Duplicate POI within an assumed query; refusing inflated query counts.")
    if frame["candidate_slot_id"].fillna("").astype(str).str.strip().ne("").any():
        raise DatasetContractError("This weak-label POI dataset must not claim actual slot IDs.")

    # This only reproduces the source's estimated resource screen. It is not a
    # planner check and is kept as such in the output metadata.
    estimated_feasible = frame["estimated_resource_feasible"].fillna("").astype(str).str.casefold().isin(
        {"true", "1", "yes"}
    )
    frame = frame.loc[estimated_feasible].copy().reset_index(drop=True)
    if frame.empty:
        raise DatasetContractError("No rows pass the source's estimated resource screen.")
    frame["relevance_grade"] = pd.to_numeric(frame["relevance_grade"], errors="raise").astype(int)
    return frame


def _query_and_candidate(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Whitelist only inference-time fields; labels, IDs and provenance never enter X."""
    query = {
        "user_intent_tags": row.get("user_intent_tags"),
        "remaining_time_min": row.get("remaining_time_min"),
        "group_size": row.get("group_size"),
        "budget_remaining_vnd": row.get("budget_remaining_vnd"),
        "rain_mm": row.get("rain_mm"),
        "temperature_c": row.get("temperature_c"),
        "pm2_5": row.get("pm2_5"),
        "european_aqi": row.get("european_aqi"),
    }
    candidate = {
        "candidate_tags": row.get("candidate_tags"),
        "duration_min": row.get("duration_min"),
        "price_vnd_per_person": row.get("price_vnd_per_person"),
        "total_cost_vnd": row.get("total_cost_vnd"),
        "is_hands_on": row.get("is_hands_on"),
        "is_indoor": row.get("is_indoor"),
        "eta_min": row.get("eta_min"),
    }
    return query, candidate


def build_feature_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for record in frame.to_dict(orient="records"):
        query, candidate = _query_and_candidate(record)
        rows.append(build_feature_row(query, candidate))
    matrix = pd.DataFrame(rows, columns=FEATURE_NAMES, dtype=float)
    if list(matrix.columns) != FEATURE_NAMES:
        raise AssertionError("Feature order differs from the API contract.")
    if FORBIDDEN_FEATURE_COLUMNS.intersection(matrix.columns):
        raise AssertionError("A label, rationale, or identifier leaked into the feature matrix.")
    return matrix


def build_baseline_scores(frame: pd.DataFrame) -> np.ndarray:
    scores = []
    for record in frame.to_dict(orient="records"):
        query, candidate = _query_and_candidate(record)
        scores.append(rule_baseline_score(query, candidate))
    return np.asarray(scores, dtype=float)


def split_by_group(frame: pd.DataFrame, group_key: str, seed: int = 42) -> dict[str, np.ndarray]:
    """Split on one stable entity key and keep every group in exactly one fold."""
    if group_key not in frame.columns:
        raise DatasetContractError(f"Cannot split: missing group key {group_key}.")
    group_ids = np.asarray(sorted(frame[group_key].dropna().astype(str).unique()))
    if len(group_ids) < 10:
        raise DatasetContractError(f"Too few distinct {group_key} groups for 70/15/15 holdout.")
    shuffled = np.random.default_rng(seed).permutation(group_ids)
    n_train = int(0.70 * len(shuffled))
    n_validation = int(0.15 * len(shuffled))
    memberships = {
        "train": set(shuffled[:n_train]),
        "validation": set(shuffled[n_train:n_train + n_validation]),
        "test": set(shuffled[n_train + n_validation:]),
    }
    if memberships["train"] & memberships["validation"] or memberships["train"] & memberships["test"] or memberships["validation"] & memberships["test"]:
        raise AssertionError(f"{group_key} split overlap detected.")
    result = {
        name: np.flatnonzero(frame[group_key].astype(str).isin(groups).to_numpy())
        for name, groups in memberships.items()
    }
    if set(np.concatenate(list(result.values()))) != set(range(len(frame))):
        raise AssertionError("The group split lost or duplicated source rows.")
    return result


def split_by_poi(frame: pd.DataFrame, seed: int = 42) -> dict[str, np.ndarray]:
    """Weak-data holdout: unseen POIs, while retaining the six existing contexts."""
    result = split_by_group(frame, "poi_id", seed)
    query_ids = set(frame["query_id"].astype(str))
    for name, indices in result.items():
        if set(frame.iloc[indices]["query_id"].astype(str)) != query_ids:
            raise DatasetContractError(f"{name} split does not contain every original query context.")
    return result


def split_by_query_id(frame: pd.DataFrame, seed: int = 42) -> dict[str, np.ndarray]:
    """Real-feedback holdout: no query/request may cross a train/val/test fold."""
    return split_by_group(frame, "query_id", seed)


def ndcg_at_k(labels: np.ndarray, scores: np.ndarray, k: int) -> float:
    labels = np.asarray(labels, dtype=float)
    scores = np.asarray(scores, dtype=float)
    if labels.size == 0:
        return math.nan
    gains = np.exp2(labels) - 1.0
    order = np.argsort(-scores, kind="stable")[:k]
    ideal = np.argsort(-labels, kind="stable")[:k]
    discounts = np.log2(np.arange(2, len(order) + 2))
    ideal_discounts = np.log2(np.arange(2, len(ideal) + 2))
    dcg = float(np.sum(gains[order] / discounts))
    idcg = float(np.sum(gains[ideal] / ideal_discounts))
    return dcg / idcg if idcg > 0 else math.nan


def ranking_metrics(frame: pd.DataFrame, scores: np.ndarray) -> dict[str, Any]:
    if len(frame) != len(scores):
        raise ValueError("One score is required per candidate row.")
    labels = frame["relevance_grade"].to_numpy(dtype=int)
    ndcg5: list[float] = []
    ndcg10: list[float] = []
    recall5: list[float] = []
    top1: list[float] = []
    for _, positions in frame.reset_index(drop=True).groupby("query_id", sort=True).indices.items():
        indices = np.asarray(positions, dtype=int)
        group_labels, group_scores = labels[indices], scores[indices]
        score5 = ndcg_at_k(group_labels, group_scores, 5)
        score10 = ndcg_at_k(group_labels, group_scores, 10)
        if math.isfinite(score5):
            ndcg5.append(score5)
            ndcg10.append(score10)
            best = int(np.max(group_labels))
            best_count = int(np.count_nonzero(group_labels == best))
            order = np.argsort(-group_scores, kind="stable")
            recall5.append(float(np.count_nonzero(group_labels[order[:5]] == best) / best_count))
            top1.append(float(group_labels[order[0]] == best))
    return {
        "NDCG@5": float(np.mean(ndcg5)) if ndcg5 else math.nan,
        "NDCG@10": float(np.mean(ndcg10)) if ndcg10 else math.nan,
        "Recall@5_best_grade": float(np.mean(recall5)) if recall5 else math.nan,
        "Top1_best_grade": float(np.mean(top1)) if top1 else math.nan,
        "queries": len(ndcg5),
    }


def _ordered_split(frame: pd.DataFrame, features: pd.DataFrame, indices: np.ndarray):
    rows = frame.iloc[indices].copy()
    rows["_original_index"] = indices
    sort_columns = ["query_id", "poi_id"]
    ordered = rows.sort_values(sort_columns, kind="mergesort")
    ordered_indices = ordered["_original_index"].to_numpy(dtype=int)
    qid, _ = pd.factorize(ordered["query_id"].astype(str), sort=True)
    group_sizes = ordered.groupby("query_id", sort=True).size().astype(int).tolist()
    if any(size < 2 for size in group_sizes):
        raise DatasetContractError("A ranking query must contain at least two candidate rows.")
    return (
        features.iloc[ordered_indices].reset_index(drop=True),
        frame.iloc[ordered_indices]["relevance_grade"].to_numpy(dtype=int),
        qid.astype(np.int32),
        group_sizes,
        ordered_indices,
    )


def _estimator(family: str, params: dict[str, int], seed: int):
    if family == "xgboost":
        from xgboost import XGBRanker

        return XGBRanker(
            objective="rank:ndcg",
            eval_metric=["ndcg@5", "ndcg@10"],
            tree_method="hist",
            learning_rate=0.05,
            max_depth=params["max_depth"],
            n_estimators=params["n_estimators"],
            min_child_weight=5,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=seed,
            n_jobs=1,
        )
    if family == "lightgbm":
        from lightgbm import LGBMRanker

        return LGBMRanker(
            objective="lambdarank",
            metric="ndcg",
            eval_at=[5, 10],
            label_gain=LABEL_GAIN,
            lambdarank_truncation_level=10,
            learning_rate=0.05,
            max_depth=params["max_depth"],
            num_leaves=(2 ** params["max_depth"]) - 1,
            n_estimators=params["n_estimators"],
            min_child_samples=5,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=seed,
            deterministic=True,
            force_col_wise=True,
            n_jobs=1,
            verbosity=-1,
        )
    raise ValueError(f"Unsupported ranker family: {family}")


def _fit(model, family: str, X: pd.DataFrame, y: np.ndarray, qid: np.ndarray, groups: list[int]):
    if family == "xgboost":
        model.fit(X, y, qid=qid, verbose=False)
    else:
        model.fit(X, y, group=groups)
    return model


def _save_native_model(model, family: str, path: Path) -> None:
    if family == "xgboost":
        model.save_model(str(path))
    else:
        model.booster_.save_model(str(path))


def _model_latency_ms(model, matrix: pd.DataFrame) -> float:
    model.predict(matrix.iloc[: min(32, len(matrix))])  # warm-up
    sample = matrix.iloc[: min(128, len(matrix))]
    durations = []
    for _ in range(25):
        start = time.perf_counter()
        model.predict(sample)
        durations.append((time.perf_counter() - start) * 1000.0)
    return float(statistics.median(durations))


def _baseline_rows(frame: pd.DataFrame, scores: np.ndarray) -> list[dict[str, Any]]:
    metrics = ranking_metrics(frame, scores)
    return [{"model": "rule_baseline", "params": "tags/category only", **metrics,
             "inference_ms_per_128_candidates": 0.0, "artifact_size_bytes": 0,
             "stability_std_NDCG@5": 0.0, "status": "ok"}]


def _read_current_model_reference() -> dict[str, Any] | None:
    metadata_path = ROOT / "models" / "ai-ranker" / "model_metadata.json"
    if not metadata_path.is_file():
        return None
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "metadata_unreadable", "same_data_comparison": False}
    return {
        "model_version": metadata.get("model_version"),
        "model_type": metadata.get("model_type"),
        "dataset_status": metadata.get("dataset_status"),
        "historical_test_metrics": metadata.get("test_metrics"),
        "same_data_comparison": False,
        "reason": "Existing bundle was trained on another CSV/split; its historical metric is not a fair same-split benchmark.",
    }


def _fit_and_score(
    family: str,
    params: dict[str, int],
    seed: int,
    train_data,
    validation_data,
    frame: pd.DataFrame,
) -> tuple[Any, np.ndarray, dict[str, Any]]:
    X_train, y_train, qid_train, group_train, _ = train_data
    X_val, _, _, _, val_indices = validation_data
    model = _estimator(family, params, seed)
    _fit(model, family, X_train, y_train, qid_train, group_train)
    predictions = np.asarray(model.predict(X_val), dtype=float)
    metrics = ranking_metrics(frame.iloc[val_indices].reset_index(drop=True), predictions)
    return model, predictions, metrics


def _write_bundle(
    out_dir: Path,
    model: Any,
    family: str,
    params: dict[str, int],
    metrics: dict[str, Any],
    data_hash: str,
    frame: pd.DataFrame,
) -> Path:
    bundle_dir = out_dir / "selected_model"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    extension = "json" if family == "xgboost" else "txt"
    model_file = f"{family}_ranker.{extension}"
    _save_native_model(model, family, bundle_dir / model_file)
    metadata = {
        "model_version": f"local-explorer-{family}-weak-experiment-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "model_family": family,
        "model_file": model_file,
        "model_type": "XGBRanker" if family == "xgboost" else "LGBMRanker",
        "objective": "rank:ndcg" if family == "xgboost" else "lambdarank",
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "dataset_status": "weak_label_experiment",
        "training_mode": "weak_label",
        "deployment_eligible": False,
        "dataset_filename": "ranking_candidates_labeled.csv",
        "dataset_sha256": data_hash,
        "rows": int(len(frame)),
        "unique_pois": int(frame["poi_id"].nunique()),
        "query_contexts": int(frame["query_id"].nunique()),
        "human_labels": False,
        "verified_slots": False,
        "verified_planner_constraints": False,
        "estimated_columns": sorted({
            part.strip()
            for value in frame["estimated_columns"].fillna("").astype(str)
            for part in value.split(";") if part.strip()
        }),
        "selected_params": params,
        "validation_metrics": metrics,
        "warning": "Weak labels from assumed intent/category rules; scores measure rule imitation, not user preference.",
    }
    (bundle_dir / "model_metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    schema = {
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "label": "relevance_grade",
        "group_key": "query_id",
        "weak_split_key": "poi_id",
        "missing_value_policy": "NaN stays missing; each tree ranker uses its native missing-value handling.",
        "training_feature_function": "apps/api/app/services/ranker_features.py::build_feature_row",
        "hard_constraint": "filter before ranking in the planner; this dataset did not verify feasibility",
    }
    (bundle_dir / "feature_schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")
    preprocessing = {
        "type": "deterministic_shared_feature_builder",
        "module": "app.services.ranker_features.build_feature_row",
        "feature_version": FEATURE_VERSION,
        "fitted_transformer": None,
        "fit_scope": "No learned preprocessing; all ratios are computed with the shared API feature builder.",
        "missing_values": "Preserved as NaN, not converted to false or zero.",
    }
    (bundle_dir / "preprocessing.json").write_text(json.dumps(preprocessing, ensure_ascii=False, indent=2), encoding="utf-8")
    (bundle_dir / "validation_metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    archive = out_dir / "weak_experiment_ranker_bundle.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for file in sorted(bundle_dir.iterdir()):
            bundle.write(file, arcname=file.name)
    return archive


def _write_experiment_artifacts(out_dir: Path, report: dict[str, Any]) -> None:
    schema = {
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "label": "relevance_grade",
        "group_key": "query_id",
        "weak_holdout_key": "poi_id",
        "forbidden_feature_columns": sorted(FORBIDDEN_FEATURE_COLUMNS),
        "missing_value_policy": "Unknown hands-on/indoor remain NaN and have explicit known flags.",
        "feature_function": "apps/api/app/services/ranker_features.py::build_feature_row",
    }
    preprocessing = {
        "type": "deterministic_shared_feature_builder",
        "feature_version": FEATURE_VERSION,
        "fitted_transformer": None,
        "fit_scope": "No learned preprocessing. Ratios and tag matching use the same deterministic API function at training and inference.",
        "numeric_missing_values": "NaN is preserved for model-native missing-value handling.",
        "identifiers_and_label_text": "Never transformed or included as model features.",
    }
    metadata = {
        "benchmark_version": report["benchmark_version"],
        "dataset_status": report["dataset_status"],
        "training_mode": report["mode"],
        "deployment_eligible": report["deployment_eligible"],
        "dataset_sha256": report["data_sha256"],
        "rows": report["rows_after_estimated_resource_screen"],
        "unique_pois": report["unique_pois"],
        "query_contexts": report["query_context_count"],
        "split_key": report["split_key"],
        "selected_model": report["selected_model"],
        "selected_model_bundle": report["selected_model_bundle"],
        "feature_version": FEATURE_VERSION,
        "estimated_columns": report["estimated_columns"],
        "limitations": report["limitations"],
    }
    for filename, payload in (
        ("feature_schema.json", schema),
        ("preprocessing.json", preprocessing),
        ("benchmark_metadata.json", metadata),
    ):
        (out_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def run_benchmark(
    data_path: Path,
    output_dir: Path,
    mode: str = "weak_label",
    models: tuple[str, ...] = ("lightgbm", "xgboost"),
    seed: int = 42,
    minimum_ndcg5_gain: float = MIN_MEANINGFUL_NDCG5_GAIN,
    allow_partial_comparison: bool = False,
) -> dict[str, Any]:
    frame = read_weak_dataset(data_path, mode)
    model_families = set(models)
    if not model_families or not model_families.issubset({"lightgbm", "xgboost"}):
        raise ValueError("Select LightGBM and/or XGBoost.")
    if not allow_partial_comparison and model_families != {"lightgbm", "xgboost"}:
        raise ValueError("The full comparison requires both LightGBM and XGBoost.")
    output_dir.mkdir(parents=True, exist_ok=True)
    data_hash = sha256_file(data_path)
    split = split_by_poi(frame, seed)
    features = build_feature_matrix(frame)
    labels = frame["relevance_grade"].to_numpy(dtype=int)
    baseline = build_baseline_scores(frame)

    train_data = _ordered_split(frame, features, split["train"])
    validation_data = _ordered_split(frame, features, split["validation"])
    validation_frame = frame.iloc[validation_data[4]].reset_index(drop=True)
    baseline_validation = baseline[validation_data[4]]
    validation_rows = _baseline_rows(validation_frame, baseline_validation)
    model_rows: list[dict[str, Any]] = []
    best_by_family: dict[str, tuple[dict[str, Any], dict[str, int]]] = {}

    missing_dependencies = []
    available_models = []
    for family, module in (("lightgbm", "lightgbm"), ("xgboost", "xgboost")):
        if family not in model_families:
            continue
        try:
            __import__(module)
            available_models.append(family)
        except ImportError as error:
            missing_dependencies.append(f"{module}: {error}")
    if missing_dependencies and not allow_partial_comparison:
        raise RuntimeError(
            "Full ranking comparison requires both training dependencies. Install apps/api/requirements-ranking-training.txt. "
            + "; ".join(missing_dependencies)
        )
    if not available_models:
        raise RuntimeError("No requested ranking algorithm is installed.")

    with tempfile.TemporaryDirectory(prefix="localexplorer-ranker-benchmark-") as temp_name:
        temp_dir = Path(temp_name)
        for family in available_models:
            family_runs = []
            for index, params in enumerate(TUNING_CONFIGS):
                model, predictions, metrics = _fit_and_score(
                    family, params, seed, train_data, validation_data, frame
                )
                latency = _model_latency_ms(model, validation_data[0])
                ext = "json" if family == "xgboost" else "txt"
                model_path = temp_dir / f"{family}-{index}.{ext}"
                _save_native_model(model, family, model_path)
                row = {
                    "model": family,
                    "params": json.dumps(params, sort_keys=True),
                    **metrics,
                    "inference_ms_per_128_candidates": latency,
                    "artifact_size_bytes": model_path.stat().st_size,
                    "status": "ok",
                }
                model_rows.append(row)
                family_runs.append((row, params))
            best_run = max(
                family_runs,
                key=lambda item: (
                    item[0]["NDCG@5"], item[0]["NDCG@10"],
                    -item[0]["inference_ms_per_128_candidates"],
                    -item[0]["artifact_size_bytes"],
                ),
            )
            stability_scores = []
            for stability_seed in STABILITY_SEEDS:
                _, _, stability_metrics = _fit_and_score(
                    family, best_run[1], stability_seed, train_data, validation_data, frame
                )
                stability_scores.append(stability_metrics["NDCG@5"])
            best_run[0]["stability_mean_NDCG@5"] = float(np.mean(stability_scores))
            best_run[0]["stability_std_NDCG@5"] = float(np.std(stability_scores, ddof=0))
            best_run[0]["stability_min_NDCG@5"] = float(np.min(stability_scores))
            best_by_family[family] = best_run

    best_ml_row, best_ml_params = max(
        best_by_family.values(),
        key=lambda item: (
            item[0]["NDCG@5"], item[0]["NDCG@10"],
            -item[0].get("stability_std_NDCG@5", math.inf),
            -item[0]["inference_ms_per_128_candidates"],
            -item[0]["artifact_size_bytes"],
        ),
    )
    baseline_ndcg5 = validation_rows[0]["NDCG@5"]
    full_comparison_complete = not missing_dependencies and model_families == {"lightgbm", "xgboost"}
    baseline_is_upper_bound = baseline_ndcg5 >= 1.0 - 1e-12
    meaningful = best_ml_row["NDCG@5"] >= baseline_ndcg5 + minimum_ndcg5_gain
    if meaningful and full_comparison_complete:
        selected_family = best_ml_row["model"]
        selected_params = best_ml_params
    elif full_comparison_complete or baseline_is_upper_bound:
        selected_family = "rule_baseline"
        selected_params = None
    else:
        selected_family = None
        selected_params = None

    selected_bundle: str | None = None
    test_metrics: dict[str, Any] | None = None
    if selected_family is not None:
        # Test is touched only after validation selected the rule or one ML family.
        test_data = _ordered_split(frame, features, split["test"])
        test_frame = frame.iloc[test_data[4]].reset_index(drop=True)
        test_baseline_scores = baseline[test_data[4]]
        test_metrics = {
            "selected_model": selected_family,
            "selection_rule": "validation NDCG@5; ML must exceed rule baseline by at least 0.01",
            "rule_baseline": ranking_metrics(test_frame, test_baseline_scores),
        }
        predictions_out = test_frame[["query_id", "poi_id", "candidate_experience_id", "relevance_grade"]].copy()
        predictions_out["rule_baseline_score"] = test_baseline_scores
        if selected_family == "rule_baseline":
            predictions_out["selected_score"] = test_baseline_scores
            test_metrics["selected_model_metrics"] = test_metrics["rule_baseline"]
            test_metrics["ml_test_evaluation"] = "Not run: no ML candidate meaningfully beat the rule baseline on validation."
        else:
            best_params = selected_params
            combined_indices = np.concatenate([split["train"], split["validation"]])
            final_train = _ordered_split(frame, features, combined_indices)
            final_model = _estimator(selected_family, best_params, seed)
            _fit(final_model, selected_family, final_train[0], final_train[1], final_train[2], final_train[3])
            test_predictions = np.asarray(final_model.predict(test_data[0]), dtype=float)
            test_metrics["selected_model_metrics"] = ranking_metrics(test_frame, test_predictions)
            test_metrics["selected_model_metrics"]["model"] = selected_family
            predictions_out["selected_score"] = test_predictions
            selected_bundle = str(_write_bundle(
                output_dir, final_model, selected_family, best_params,
                best_ml_row, data_hash, frame,
            ))
        predictions_out.to_csv(output_dir / "test_predictions.csv", index=False)
        (output_dir / "test_metrics.json").write_text(json.dumps(test_metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    validation_table = validation_rows + model_rows
    validation_table.sort(key=lambda row: (row["model"], -row["NDCG@5"], -row["NDCG@10"]))
    pd.DataFrame(validation_table).to_csv(output_dir / "validation_comparison.csv", index=False)

    poigroups = {name: int(frame.iloc[indices]["poi_id"].nunique()) for name, indices in split.items()}
    report = {
        "benchmark_version": "ranking-benchmark-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "dataset_status": "weak_label_experiment",
        "deployment_eligible": False,
        "data_path": str(data_path),
        "data_sha256": data_hash,
        "rows_after_estimated_resource_screen": int(len(frame)),
        "unique_pois": int(frame["poi_id"].nunique()),
        "query_context_count": int(frame["query_id"].nunique()),
        "query_contexts_are_assumed": True,
        "human_preference_labels": 0,
        "verified_experiences": 0,
        "verified_slots": 0,
        "verified_planner_feasibility": False,
        "split_key": "poi_id",
        "poi_counts_by_split": poigroups,
        "overlap_between_poi_splits": False,
        "features": FEATURE_NAMES,
        "feature_version": FEATURE_VERSION,
        "forbidden_feature_columns_excluded": sorted(FORBIDDEN_FEATURE_COLUMNS),
        "estimated_columns": sorted({
            part.strip()
            for value in frame["estimated_columns"].fillna("").astype(str)
            for part in value.split(";") if part.strip()
        }),
        "tuning_budget": {
            "configurations_per_ranker": len(TUNING_CONFIGS),
            "stability_seeds_per_ranker": len(STABILITY_SEEDS),
            "same_feature_function_and_splits": True,
            "test_used_for_selection": False,
        },
        "full_algorithm_comparison_complete": full_comparison_complete,
        "requested_model_families": sorted(model_families),
        "available_model_families": sorted(available_models),
        "unavailable_model_dependencies": missing_dependencies,
        "baseline_is_validation_upper_bound": baseline_is_upper_bound,
        "validation_comparison": validation_table,
        "best_ml_candidate": best_ml_row,
        "rule_baseline_validation": validation_rows[0],
        "minimum_meaningful_ndcg5_gain": minimum_ndcg5_gain,
        "selected_model": selected_family,
        "selected_ml_params": selected_params,
        "selected_model_bundle": selected_bundle,
        "test_metrics": test_metrics,
        "existing_model_reference": _read_current_model_reference(),
        "limitations": [
            "The 0/2/3 grades are rule-generated, not human preference labels.",
            "The six query contexts are analyst assumptions; results do not generalize to new intents.",
            "POIs are real OSM records but operational status is unverified; experience and slot IDs are absent.",
            "Duration, ETA, price, indoor state, and relevance grade are estimated or rule-derived as listed in estimated_columns.",
            "Metrics measure imitation of the category rule only and are not real recommendation quality.",
        ],
    }
    (output_dir / "benchmark_metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_experiment_artifacts(output_dir, report)
    _write_model_card(output_dir / "model_card.md", report)
    return report


def _write_model_card(path: Path, report: dict[str, Any]) -> None:
    comparison = report["validation_comparison"]
    lines = [
        "# LocalExplorerAI experience-ranker benchmark",
        "",
        "This is a weak-label pipeline experiment, not a real-user quality evaluation.",
        "",
        f"- Dataset SHA-256: `{report['data_sha256']}`",
        f"- Rows / POIs / query contexts: {report['rows_after_estimated_resource_screen']} / {report['unique_pois']} / {report['query_context_count']}",
        f"- Split: POI-disjoint; counts `{report['poi_counts_by_split']}`; no duplicated query contexts added.",
        f"- Selected by validation NDCG@5: `{report['selected_model']}`.",
        f"- Deployment eligible: `{str(report['deployment_eligible']).lower()}`.",
        "",
        "## Validation comparison",
        "",
        "| Model/config | NDCG@5 | NDCG@10 | Latency ms / 128 | Model bytes |",
        "|---|---:|---:|---:|---:|",
    ]
    for row in comparison:
        lines.append(
            f"| {row['model']} / {row['params']} | {row['NDCG@5']:.4f} | {row['NDCG@10']:.4f} | "
            f"{row['inference_ms_per_128_candidates']:.4f} | {row['artifact_size_bytes']} |"
        )
    lines.extend(["", "## Limits", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.extend([
        "",
        "A model bundle is emitted only if the selected ML candidate beats the tag/category rule baseline by at least 0.01 validation NDCG@5. Weak-label bundles are never marked deployment eligible.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mode", choices=["weak_label"], required=True)
    parser.add_argument("--models", nargs="+", choices=["lightgbm", "xgboost"], default=["lightgbm", "xgboost"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--allow-partial-comparison", action="store_true", help="Diagnostic only; does not select an ML model unless all requested algorithms ran or baseline is already NDCG@5=1.")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory: {args.output}")
    report = run_benchmark(args.data, args.output, args.mode, tuple(args.models), args.seed,
                           allow_partial_comparison=args.allow_partial_comparison)
    print(json.dumps({
        "selected_model": report["selected_model"],
        "full_algorithm_comparison_complete": report["full_algorithm_comparison_complete"],
        "deployment_eligible": report["deployment_eligible"],
        "best_ml_candidate": report["best_ml_candidate"],
        "rule_baseline_validation": report["rule_baseline_validation"],
        "test_metrics": report["test_metrics"],
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
