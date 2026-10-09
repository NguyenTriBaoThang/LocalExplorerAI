"""Train and package a human-labeled LocalExplorerAI experience ranker.

This is intentionally separate from the weak-label benchmark. It refuses
estimated, simulated, unverified, or planner-unchecked rows. A deployable ZIP
is created only after a query_id holdout, a material validation gain over the
rule baseline, and non-degradation on the untouched test set.
"""

from __future__ import annotations

import argparse
from importlib.metadata import PackageNotFoundError, version as package_version
import json
import platform
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from app.services.ranker_features import FEATURE_NAMES, FEATURE_VERSION  # noqa: E402
from train_experience_ranker import (  # noqa: E402
    FORBIDDEN_FEATURE_COLUMNS,
    MIN_MEANINGFUL_NDCG5_GAIN,
    STABILITY_SEEDS,
    TUNING_CONFIGS,
    DatasetContractError,
    _estimator,
    _fit,
    _model_latency_ms,
    _ordered_split,
    _save_native_model,
    build_baseline_scores,
    build_feature_matrix,
    ranking_metrics,
    sha256_file,
    split_by_query_id,
)


DEFAULT_DATA = ROOT / "data" / "training" / "experience_ranker_verified.csv"
DEFAULT_OUTPUT = ROOT / "models" / "ai-ranker" / "verified-training-run"
MIN_QUERY_GROUPS = 20
REQUIRED_COLUMNS = {
    "query_id", "poi_id", "candidate_experience_id", "candidate_slot_id",
    "user_intent_tags", "travel_mode", "remaining_time_min", "group_size", "budget_remaining_vnd",
    "candidate_tags", "duration_min", "price_vnd_per_person", "total_cost_vnd",
    "is_hands_on", "is_indoor", "eta_min", "hard_feasible", "relevance_grade",
    "poi_name", "poi_address", "poi_lat", "poi_lon", "coordinates_source_ref",
    "coordinates_confirmed_at", "coordinates_valid_until", "poi_valid_until", "experience_valid_until",
    "price_valid_until", "duration_valid_until", "eta_valid_until", "return_eta_valid_until",
    "slot_valid_until", "capacity_valid_until",
    "slot_start_at", "slot_end_at",
    "slot_status", "available_capacity", "query_snapshot_at", "return_deadline_at", "return_eta_min",
    "label_status", "label_method", "label_source_ref", "labelled_at", "trip_completed_at",
    "rubric_version", "labeler_ref", "poi_source_url", "poi_source_ref", "poi_confirmed_at",
    "experience_source_url", "experience_source_ref", "experience_confirmed_at",
    "price_source_ref", "price_confirmed_at", "duration_source_ref", "duration_confirmed_at",
    "eta_source_ref", "eta_confirmed_at", "slot_source_ref", "slot_confirmed_at",
    "capacity_source_ref", "capacity_confirmed_at", "planner_source_ref", "planner_checked_at",
    "return_route_source_ref", "return_route_checked_at", "estimated_columns", "training_eligible",
}
PROVENANCE_REFERENCE_COLUMNS = {
    "label_source_ref", "labeler_ref", "poi_source_url", "poi_source_ref",
    "coordinates_source_ref", "experience_source_url", "experience_source_ref", "price_source_ref",
    "duration_source_ref", "eta_source_ref", "slot_source_ref", "capacity_source_ref",
    "planner_source_ref", "return_route_source_ref",
}
TIMESTAMP_COLUMNS = [
    "query_snapshot_at", "return_deadline_at", "slot_start_at", "slot_end_at", "trip_completed_at", "labelled_at",
    "poi_confirmed_at", "poi_valid_until", "coordinates_confirmed_at", "coordinates_valid_until",
    "experience_confirmed_at", "experience_valid_until", "price_confirmed_at", "price_valid_until",
    "duration_confirmed_at", "duration_valid_until",
    "eta_confirmed_at", "slot_confirmed_at", "capacity_confirmed_at", "planner_checked_at",
    "eta_valid_until", "return_eta_valid_until", "slot_valid_until", "capacity_valid_until", "return_route_checked_at",
]
FEATURE_INPUT_COLUMNS = {
    "user_intent_tags", "remaining_time_min", "group_size", "budget_remaining_vnd",
    "rain_mm", "temperature_c", "pm2_5", "european_aqi", "candidate_tags",
    "duration_min", "price_vnd_per_person", "total_cost_vnd", "is_hands_on", "is_indoor", "eta_min",
}


def _runtime_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__}
    for distribution in ("xgboost", "lightgbm"):
        try:
            versions[distribution] = package_version(distribution)
        except PackageNotFoundError:
            versions[distribution] = None
    return versions


def _truth_values(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip().str.casefold().isin({"true", "1", "yes", "y"})


def _require_timezone_offsets(frame: pd.DataFrame, column: str) -> None:
    values = frame[column].fillna("").astype(str).str.strip()
    has_offset = values.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", case=False, regex=True)
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    if not has_offset.all() or parsed.isna().any():
        raise DatasetContractError(f"{column} must contain valid ISO-8601 timestamps with timezone offsets.")


def _parsed_utc(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_datetime(frame[column], errors="coerce", utc=True)


def _require_http_urls(frame: pd.DataFrame, column: str) -> None:
    values = frame[column].fillna("").astype(str).str.strip()
    valid = values.map(lambda value: urlparse(value).scheme in {"http", "https"} and bool(urlparse(value).netloc))
    if not valid.all():
        raise DatasetContractError(f"{column} must contain a directly auditable http(s) source URL.")


def read_verified_dataset(path: Path) -> pd.DataFrame:
    """Validate a real human-labeled CSV without inferring missing provenance."""
    frame = pd.read_csv(path, encoding="utf-8-sig", keep_default_na=True)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise DatasetContractError(f"Missing required verified-data columns: {missing}")
    if frame.empty:
        raise DatasetContractError("The verified ranking CSV is empty.")

    for column in ("query_id", "poi_id", "candidate_experience_id", "candidate_slot_id"):
        if frame[column].isna().any() or frame[column].astype(str).str.strip().eq("").any():
            raise DatasetContractError(f"{column} must be populated with real, stable, non-personal identifiers.")
    if frame.duplicated(["query_id", "candidate_experience_id", "candidate_slot_id"]).any():
        raise DatasetContractError("Duplicate candidate experience/slot rows exist within a query_id.")

    if not frame["label_status"].fillna("").astype(str).str.strip().eq("verified_human_labeled").all():
        raise DatasetContractError("Every row must declare label_status=verified_human_labeled.")
    allowed_label_methods = {"consented_feedback_reviewed", "independent_human_review"}
    if not frame["label_method"].fillna("").astype(str).str.strip().isin(allowed_label_methods).all():
        raise DatasetContractError(
            "label_method must be consented_feedback_reviewed or independent_human_review; "
            "weak, heuristic, synthetic, and LLM-generated labels are not accepted."
        )
    if not _truth_values(frame["training_eligible"]).all():
        raise DatasetContractError("Every row must be explicitly marked training_eligible=true.")
    if not _truth_values(frame["hard_feasible"]).all():
        raise DatasetContractError("Only planner-verified feasible candidates may be used for ranking training.")
    if frame["estimated_columns"].fillna("").astype(str).str.strip().ne("").any():
        raise DatasetContractError("Estimated columns are present; this file cannot be declared verified training data.")

    for column in PROVENANCE_REFERENCE_COLUMNS:
        values = frame[column].fillna("").astype(str).str.strip()
        if values.eq("").any():
            raise DatasetContractError(f"{column} must link to auditable, non-personal source evidence.")
    for column in ("poi_source_url", "experience_source_url"):
        _require_http_urls(frame, column)
    for column in TIMESTAMP_COLUMNS:
        _require_timezone_offsets(frame, column)

    if not frame["poi_name"].fillna("").astype(str).str.strip().ne("").all():
        raise DatasetContractError("poi_name must be populated from the verified catalog.")
    if not frame["poi_address"].fillna("").astype(str).str.strip().ne("").all():
        raise DatasetContractError("poi_address must be a verified address, not a geocoder guess without confirmation.")
    if not frame["user_intent_tags"].fillna("").astype(str).str.strip().ne("").all():
        raise DatasetContractError("user_intent_tags must include the actual trip intent used for this query.")
    if not frame["travel_mode"].fillna("").astype(str).str.strip().str.casefold().isin(
        {"motorcycle", "walking", "car", "transit"}
    ).all():
        raise DatasetContractError("travel_mode must be motorcycle, walking, car, or transit as used by the planner.")
    if not frame["candidate_tags"].fillna("").astype(str).str.strip().ne("").all():
        raise DatasetContractError("candidate_tags must be assigned from the reviewed experience catalog.")
    if not frame["rubric_version"].fillna("").astype(str).str.strip().ne("").all():
        raise DatasetContractError("rubric_version is required for every human label.")

    query_snapshot = _parsed_utc(frame, "query_snapshot_at")
    slot_start = _parsed_utc(frame, "slot_start_at")
    slot_end = _parsed_utc(frame, "slot_end_at")
    return_deadline = _parsed_utc(frame, "return_deadline_at")
    completed_at = _parsed_utc(frame, "trip_completed_at")
    for column in (
        "poi_valid_until", "coordinates_valid_until", "experience_valid_until", "price_valid_until",
        "duration_valid_until", "eta_valid_until", "return_eta_valid_until", "slot_valid_until", "capacity_valid_until",
    ):
        if (_parsed_utc(frame, column) <= query_snapshot).any():
            raise DatasetContractError(f"{column} must be after query_snapshot_at; expired evidence cannot be used.")
    if (_parsed_utc(frame, "labelled_at") < completed_at).any():
        raise DatasetContractError("Human relevance labels must be created after the completed-trip outcome.")
    if (completed_at < slot_end).any():
        raise DatasetContractError("trip_completed_at cannot be before the verified experience slot has ended.")
    if (slot_end <= slot_start).any():
        raise DatasetContractError("slot_end_at must be after slot_start_at.")
    if (return_deadline <= query_snapshot).any():
        raise DatasetContractError("return_deadline_at must be after query_snapshot_at.")
    if (slot_end <= query_snapshot).any():
        raise DatasetContractError("Only slots that were still upcoming at query_snapshot_at may be used.")
    if not frame["slot_status"].fillna("").astype(str).str.strip().str.casefold().eq("open").all():
        raise DatasetContractError("Only slots recorded as open at the candidate snapshot may be used.")

    numeric_ranges = {
        "remaining_time_min": (0, None),
        "group_size": (1, None),
        "budget_remaining_vnd": (0, None),
        "duration_min": (0, None),
        "price_vnd_per_person": (0, None),
        "total_cost_vnd": (0, None),
        "eta_min": (0, None),
        "return_eta_min": (0, None),
        "available_capacity": (1, None),
        "poi_lat": (-90, 90),
        "poi_lon": (-180, 180),
    }
    for column, (minimum, maximum) in numeric_ranges.items():
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.isna().any() or not np.isfinite(values.to_numpy(dtype=float)).all() or (values < minimum).any():
            raise DatasetContractError(f"{column} must contain finite numeric values in the permitted range.")
        if maximum is not None and (values > maximum).any():
            raise DatasetContractError(f"{column} must contain finite numeric values in the permitted range.")
        if column in {"remaining_time_min", "duration_min", "group_size"} and (values <= 0).any():
            raise DatasetContractError(f"{column} must be greater than zero.")
        frame[column] = values

    capacity = pd.to_numeric(frame["available_capacity"], errors="raise")
    group_sizes = pd.to_numeric(frame["group_size"], errors="raise")
    if (capacity < group_sizes).any():
        raise DatasetContractError("available_capacity must cover the actual group_size for every feasible candidate.")
    return_eta = pd.to_numeric(frame["return_eta_min"], errors="raise")
    if (slot_end + pd.to_timedelta(return_eta, unit="min") > return_deadline).any():
        raise DatasetContractError("The slot end plus verified return-route ETA must meet the user's return deadline.")
    for column in ("rain_mm", "temperature_c", "pm2_5", "european_aqi"):
        if column in frame.columns:
            values = pd.to_numeric(frame[column], errors="coerce")
            present = frame[column].notna()
            if not np.isfinite(values.loc[present].to_numpy(dtype=float)).all():
                raise DatasetContractError(f"Optional context field {column} contains a non-finite value.")
            frame[column] = values
    for column in ("rain_mm", "pm2_5", "european_aqi"):
        if column in frame.columns and (frame[column].dropna() < 0).any():
            raise DatasetContractError(f"{column} cannot be negative.")
    duration = pd.to_numeric(frame["duration_min"], errors="raise")
    outbound_eta = pd.to_numeric(frame["eta_min"], errors="raise")
    remaining = pd.to_numeric(frame["remaining_time_min"], errors="raise")
    budget = pd.to_numeric(frame["budget_remaining_vnd"], errors="raise")
    cost = pd.to_numeric(frame["total_cost_vnd"], errors="raise")
    if (duration + outbound_eta + return_eta > remaining).any():
        raise DatasetContractError("Duration plus outbound and return ETAs must fit remaining_time_min.")
    if (cost > budget).any():
        raise DatasetContractError("total_cost_vnd must fit budget_remaining_vnd for each hard-feasible candidate.")
    if ((slot_end - slot_start).dt.total_seconds() / 60 < duration).any():
        raise DatasetContractError("The verified slot window must be long enough for duration_min.")
    if (slot_start < query_snapshot + pd.to_timedelta(outbound_eta, unit="min")).any():
        raise DatasetContractError("The candidate slot must start after the verified outbound ETA from the query snapshot.")

    confirmation_columns = [
        "poi_confirmed_at", "coordinates_confirmed_at", "experience_confirmed_at", "price_confirmed_at", "duration_confirmed_at",
        "eta_confirmed_at", "slot_confirmed_at", "capacity_confirmed_at", "planner_checked_at",
        "return_route_checked_at",
    ]
    for column in confirmation_columns:
        if (_parsed_utc(frame, column) > query_snapshot).any():
            raise DatasetContractError(f"{column} cannot be later than query_snapshot_at; future evidence would leak into training.")

    grades = pd.to_numeric(frame["relevance_grade"], errors="coerce")
    if grades.isna().any() or not grades.isin([0, 1, 2, 3]).all() or not np.equal(grades, np.floor(grades)).all():
        raise DatasetContractError("relevance_grade must be a human-assigned integer in [0, 3].")
    frame["relevance_grade"] = grades.astype(int)
    for column in ("is_hands_on", "is_indoor"):
        if frame[column].isna().any():
            raise DatasetContractError(f"{column} must be explicitly confirmed true or false; unknown is not false.")
        normalized = frame[column].astype(str).str.strip().str.casefold()
        if not normalized.isin({"true", "false", "1", "0", "yes", "no", "y", "n"}).all():
            raise DatasetContractError(f"{column} must contain explicit boolean values.")

    query_counts = frame.groupby("query_id", dropna=False).size()
    if len(query_counts) < MIN_QUERY_GROUPS:
        raise DatasetContractError(
            f"At least {MIN_QUERY_GROUPS} distinct query_id groups are required for the 70/15/15 split; "
            "more real queries are strongly recommended. Do not duplicate contexts to reach the minimum."
        )
    if (query_counts < 2).any():
        raise DatasetContractError("Every query_id must have at least two planner-feasible candidate rows.")
    for column in ("user_intent_tags", "travel_mode", "remaining_time_min", "group_size", "budget_remaining_vnd", "query_snapshot_at", "return_deadline_at"):
        if frame.groupby("query_id")[column].nunique(dropna=False).gt(1).any():
            raise DatasetContractError(f"{column} must be constant within each query_id.")
    varied_groups = frame.groupby("query_id")["relevance_grade"].nunique()
    if not varied_groups.gt(1).any():
        raise DatasetContractError("No query has differing human relevance grades; there is no ranking signal to learn.")

    # Prove at the CSV level that IDs, labels, and provenance are not accepted as
    # feature inputs. The shared builder itself uses a fixed inference whitelist.
    if FEATURE_INPUT_COLUMNS.intersection(FORBIDDEN_FEATURE_COLUMNS):
        raise AssertionError("Training feature allowlist overlaps the forbidden leakage list.")
    return frame.reset_index(drop=True)


def _require_rank_signal(frame: pd.DataFrame, indices: np.ndarray, split_name: str) -> None:
    subset = frame.iloc[indices]
    useful = subset.groupby("query_id")["relevance_grade"].nunique().gt(1)
    if int(useful.sum()) < 2:
        raise DatasetContractError(
            f"The {split_name} split needs at least two queries with different human relevance grades; "
            "collect more independent real query/feedback examples or change the seed."
        )


def _write_model_bundle(
    output_dir: Path,
    model: Any,
    family: str,
    params: dict[str, int],
    dataset: pd.DataFrame,
    dataset_hash: str,
    validation_metrics: dict[str, Any],
    test_metrics: dict[str, Any],
    deployment_eligible: bool,
    seed: int,
) -> Path:
    selected_dir = output_dir / "selected_model"
    selected_dir.mkdir(parents=True, exist_ok=True)
    extension = "json" if family == "xgboost" else "txt"
    model_file = f"{family}_ranker.{extension}"
    model_path = selected_dir / model_file
    _save_native_model(model, family, model_path)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    metadata = {
        "model_version": f"local-explorer-{family}-human-{timestamp}",
        "model_family": family,
        "model_file": model_file,
        "model_sha256": sha256_file(model_path),
        "model_type": "XGBRanker" if family == "xgboost" else "LGBMRanker",
        "objective": "rank:ndcg" if family == "xgboost" else "lambdarank",
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "dataset_status": "verified_human_labeled",
        "training_mode": "verified_human_labeled",
        "deployment_eligible": bool(deployment_eligible),
        "dataset_sha256": dataset_hash,
        "rows": int(len(dataset)),
        "unique_pois": int(dataset["poi_id"].nunique()),
        "unique_experiences": int(dataset["candidate_experience_id"].nunique()),
        "unique_slots": int(dataset["candidate_slot_id"].nunique()),
        "query_contexts": int(dataset["query_id"].nunique()),
        "split_key": "query_id",
        "human_preference_labels": True,
        "verified_experiences": True,
        "verified_slots": True,
        "verified_planner_feasibility": True,
        "estimated_columns": [],
        "label_methods": sorted(dataset["label_method"].astype(str).unique().tolist()),
        "rubric_versions": sorted(dataset["rubric_version"].astype(str).unique().tolist()),
        "selected_params": params,
        "split_seed": seed,
        "split_ratio": {"train": 0.70, "validation": 0.15, "test": 0.15},
        "runtime_versions": _runtime_versions(),
        "inference_ms_per_128_candidates": validation_metrics.get("inference_ms_per_128_candidates"),
        "model_size_bytes": model_path.stat().st_size,
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "warning": None if deployment_eligible else (
            "Research candidate only: provenance was declared human-reviewed, but the validation/test deployment gate failed."
        ),
    }
    schema = {
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "label": "relevance_grade",
        "group_key": "query_id",
        "split_key": "query_id",
        "forbidden_features": sorted(FORBIDDEN_FEATURE_COLUMNS),
        "training_feature_function": "apps/api/app/services/ranker_features.py::build_feature_row",
        "missing_value_policy": "Unknown optional weather inputs remain NaN; required operational facts must be present.",
        "planner_contract": "Only planner-verified hard_feasible=true rows are accepted; inference still applies live hard constraints before ranking.",
    }
    preprocessing = {
        "type": "deterministic_shared_feature_builder",
        "module": "app.services.ranker_features.build_feature_row",
        "feature_version": FEATURE_VERSION,
        "fitted_transformer": None,
        "fit_scope": "No learned preprocessing; training and inference call the same API feature builder.",
        "missing_values": "Optional context NaNs remain missing for native tree handling.",
    }
    for filename, payload in (
        ("model_metadata.json", metadata),
        ("feature_schema.json", schema),
        ("preprocessing.json", preprocessing),
        ("validation_metrics.json", validation_metrics),
        ("test_metrics.json", test_metrics),
    ):
        (selected_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    archive = output_dir / (
        "local_explorer_ranker_bundle.zip" if deployment_eligible
        else "research_candidate_bundle_NON_DEPLOYABLE.zip"
    )
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for artifact in sorted(selected_dir.iterdir()):
            bundle.write(artifact, arcname=artifact.name)
    return archive


def run_verified_benchmark(
    data_path: Path,
    output_dir: Path,
    seed: int = 42,
    minimum_ndcg5_gain: float = MIN_MEANINGFUL_NDCG5_GAIN,
) -> dict[str, Any]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise DatasetContractError(f"Refusing to overwrite non-empty output directory: {output_dir}")
    frame = read_verified_dataset(data_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    data_hash = sha256_file(data_path)
    split = split_by_query_id(frame, seed=seed)
    for split_name, indices in split.items():
        _require_rank_signal(frame, indices, split_name)
    features = build_feature_matrix(frame)
    baseline_scores = build_baseline_scores(frame)
    train_data = _ordered_split(frame, features, split["train"])
    validation_data = _ordered_split(frame, features, split["validation"])
    val_indices = validation_data[4]
    validation_frame = frame.iloc[val_indices].reset_index(drop=True)
    baseline_val = ranking_metrics(validation_frame, baseline_scores[val_indices])

    model_rows: list[dict[str, Any]] = []
    best_models: dict[str, tuple[dict[str, Any], dict[str, int]]] = {}
    with tempfile.TemporaryDirectory(prefix="verified-ranker-validation-") as temp_name:
        temp_dir = Path(temp_name)
        for family in ("lightgbm", "xgboost"):
            family_runs: list[tuple[dict[str, Any], dict[str, int]]] = []
            for config_index, params in enumerate(TUNING_CONFIGS):
                model = _estimator(family, params, seed)
                _fit(model, family, train_data[0], train_data[1], train_data[2], train_data[3])
                scores = np.asarray(model.predict(validation_data[0]), dtype=float)
                metrics = ranking_metrics(validation_frame, scores)
                model_path = temp_dir / f"{family}-{config_index}.{'json' if family == 'xgboost' else 'txt'}"
                _save_native_model(model, family, model_path)
                row = {
                    "model": family,
                    "params": json.dumps(params, sort_keys=True),
                    **metrics,
                    "inference_ms_per_128_candidates": _model_latency_ms(model, validation_data[0]),
                    "model_size_bytes": model_path.stat().st_size,
                }
                model_rows.append(row)
                family_runs.append((row, params))
            best_run = max(
                family_runs,
                key=lambda item: (
                    item[0]["NDCG@5"], item[0]["NDCG@10"],
                    -item[0]["inference_ms_per_128_candidates"],
                    -item[0]["model_size_bytes"],
                ),
            )
            stability_scores = []
            for stability_seed in STABILITY_SEEDS:
                stability_model = _estimator(family, best_run[1], stability_seed)
                _fit(stability_model, family, train_data[0], train_data[1], train_data[2], train_data[3])
                stable_predictions = np.asarray(stability_model.predict(validation_data[0]), dtype=float)
                stability_scores.append(ranking_metrics(validation_frame, stable_predictions)["NDCG@5"])
            best_run[0]["stability_mean_NDCG@5"] = float(np.mean(stability_scores))
            best_run[0]["stability_std_NDCG@5"] = float(np.std(stability_scores, ddof=0))
            best_run[0]["stability_min_NDCG@5"] = float(np.min(stability_scores))
            best_models[family] = best_run

    best_ml_row, best_ml_params = max(
        best_models.values(),
        key=lambda item: (
            item[0]["NDCG@5"], item[0]["NDCG@10"],
            -item[0]["stability_std_NDCG@5"],
            -item[0]["inference_ms_per_128_candidates"],
        ),
    )
    selected_family = (
        best_ml_row["model"]
        if best_ml_row["NDCG@5"] >= baseline_val["NDCG@5"] + minimum_ndcg5_gain
        else "rule_baseline"
    )

    # The test partition is evaluated only after validation chooses the family.
    test_data = _ordered_split(frame, features, split["test"])
    test_indices = test_data[4]
    test_frame = frame.iloc[test_indices].reset_index(drop=True)
    baseline_test = ranking_metrics(test_frame, baseline_scores[test_indices])
    test_metrics: dict[str, Any] = {
        "selected_model": selected_family,
        "selection_rule": "validation NDCG@5; ML must exceed baseline by configured minimum",
        "rule_baseline": baseline_test,
    }
    predictions = test_frame[["query_id", "poi_id", "candidate_experience_id", "candidate_slot_id", "relevance_grade"]].copy()
    predictions["rule_baseline_score"] = baseline_scores[test_indices]
    selected_model = None
    deployment_eligible = False
    bundle_path = None
    if selected_family == "rule_baseline":
        predictions["selected_score"] = baseline_scores[test_indices]
        test_metrics["selected_model_metrics"] = baseline_test
        test_metrics["ml_test_evaluation"] = "Not run: no ML candidate meaningfully beat baseline on validation."
    else:
        combined = np.concatenate([split["train"], split["validation"]])
        final_train = _ordered_split(frame, features, combined)
        selected_model = _estimator(selected_family, best_ml_params, seed)
        _fit(selected_model, selected_family, final_train[0], final_train[1], final_train[2], final_train[3])
        test_predictions = np.asarray(selected_model.predict(test_data[0]), dtype=float)
        selected_test_metrics = ranking_metrics(test_frame, test_predictions)
        test_metrics["selected_model_metrics"] = selected_test_metrics
        test_metrics["selected_model_metrics"]["model"] = selected_family
        test_metrics["deployment_non_degradation_vs_baseline"] = all(
            selected_test_metrics[key] >= baseline_test[key]
            for key in ("NDCG@5", "NDCG@10")
        )
        test_metrics["deployment_non_degradation_metrics"] = ["NDCG@5", "NDCG@10"]
        predictions["selected_score"] = test_predictions
        deployment_eligible = bool(test_metrics["deployment_non_degradation_vs_baseline"])
        bundle_path = _write_model_bundle(
            output_dir, selected_model, selected_family, best_ml_params,
            frame, data_hash, best_ml_row, selected_test_metrics, deployment_eligible,
            seed,
        )

    predictions.to_csv(output_dir / "test_predictions.csv", index=False)
    (output_dir / "test_metrics.json").write_text(json.dumps(test_metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    comparison = [{"model": "rule_baseline", "params": "tags/category only", **baseline_val}]
    comparison.extend(model_rows)
    comparison.sort(key=lambda row: (row["model"], -row["NDCG@5"], -row["NDCG@10"]))
    pd.DataFrame(comparison).to_csv(output_dir / "validation_comparison.csv", index=False)
    split_counts = {name: int(frame.iloc[indices]["query_id"].nunique()) for name, indices in split.items()}
    report = {
        "benchmark_version": "verified-experience-ranker-v1",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "runtime_versions": _runtime_versions(),
        "split_seed": seed,
        "dataset_status": "verified_human_labeled",
        "deployment_eligible": deployment_eligible,
        "data_sha256": data_hash,
        "rows": int(len(frame)),
        "unique_pois": int(frame["poi_id"].nunique()),
        "unique_experiences": int(frame["candidate_experience_id"].nunique()),
        "unique_slots": int(frame["candidate_slot_id"].nunique()),
        "query_context_count": int(frame["query_id"].nunique()),
        "split_key": "query_id",
        "query_counts_by_split": split_counts,
        "query_overlap_between_splits": False,
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "forbidden_feature_columns_excluded": sorted(FORBIDDEN_FEATURE_COLUMNS),
        "estimated_columns": [],
        "models_compared": ["rule_baseline", "lightgbm", "xgboost"],
        "tuning_configs_per_ml_family": len(TUNING_CONFIGS),
        "stability_seeds_per_ml_family": len(STABILITY_SEEDS),
        "test_used_for_selection": False,
        "minimum_validation_ndcg5_gain": minimum_ndcg5_gain,
        "validation_baseline": baseline_val,
        "best_ml_validation": best_ml_row,
        "selected_model": selected_family,
        "test_metrics": test_metrics,
        "bundle": str(bundle_path) if bundle_path else None,
        "limitations": [
            "The script validates required fields and provenance references but cannot independently authenticate source truth, reviewer identity, consent, or provider operation; a human data steward must audit them.",
            "Deployment depends on the truthfulness and auditability of supplied human-label and source-evidence references.",
            "A query_id holdout estimates generalization to new requests only within represented users, intents, providers, and catalog coverage.",
            "Review label counts and query-level uncertainty before pilot use; aggregate NDCG alone is not a safety/feasibility guarantee.",
        ],
    }
    (output_dir / "benchmark_metrics.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "benchmark_metadata.json").write_text(json.dumps({
        key: report[key] for key in (
            "benchmark_version", "dataset_status", "deployment_eligible", "data_sha256",
            "rows", "unique_pois", "unique_experiences", "unique_slots", "query_context_count",
            "split_key", "query_counts_by_split", "selected_model", "bundle", "feature_version",
        )
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    model_card = [
        "# Verified experience-ranker training run", "",
        f"- Dataset SHA-256: `{data_hash}`",
        f"- Rows / POIs / experiences / slots / queries: {len(frame)} / {frame['poi_id'].nunique()} / {frame['candidate_experience_id'].nunique()} / {frame['candidate_slot_id'].nunique()} / {frame['query_id'].nunique()}",
        f"- Query-disjoint split: `{split_counts}`",
        f"- Validation baseline NDCG@5: `{baseline_val['NDCG@5']:.4f}`",
        f"- Best ML: `{best_ml_row['model']}` NDCG@5 `{best_ml_row['NDCG@5']:.4f}`",
        f"- Selected: `{selected_family}`",
        f"- Deployment eligible: `{str(deployment_eligible).lower()}`",
        "", "A false deployment_eligible value means the API will reject this candidate and keep the rule baseline active.",
    ]
    (output_dir / "model_card.md").write_text("\n".join(model_card) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--minimum-ndcg5-gain", type=float, default=MIN_MEANINGFUL_NDCG5_GAIN)
    args = parser.parse_args()
    report = run_verified_benchmark(args.data, args.output, args.seed, args.minimum_ndcg5_gain)
    print(json.dumps({
        "selected_model": report["selected_model"],
        "deployment_eligible": report["deployment_eligible"],
        "bundle": report["bundle"],
        "validation_baseline": report["validation_baseline"],
        "best_ml_validation": report["best_ml_validation"],
        "test_metrics": report["test_metrics"],
        "output": str(args.output),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
