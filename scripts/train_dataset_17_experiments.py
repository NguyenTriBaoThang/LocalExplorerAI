"""Train offline experiments from the supplied DATA_ngay17 CSVs.

These CSVs are generated simulations. Outputs are deliberately marked ineligible
for production and are not the application's online model bundles. The ranker
does use the same versioned feature builder as the API to make its feature
contract testable; that does not make the synthetic labels real user feedback.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    ndcg_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit


ROOT = Path(__file__).resolve().parents[1]
API_APP = ROOT / "apps" / "api"
if str(API_APP) not in sys.path:
    sys.path.insert(0, str(API_APP))

from app.services.ranker_features import (  # noqa: E402
    FEATURE_NAMES,
    FEATURE_VERSION,
    build_feature_row,
)


SEED = 42
FLOOD_FEATURES = [
    "rainfall_last_1h_mm",
    "rainfall_last_3h_mm",
    "rainfall_last_6h_mm",
    "forecast_rain_next_3h_mm",
    "tide_level_m",
    "elevation_m",
    "slope_deg",
    "distance_to_canal_m",
    "drainage_capacity_score",
    "impervious_surface_ratio",
]
WARNING = (
    "Offline experiment only. The supplied generator creates simulated impressions, "
    "synthetic flood labels, placeholder evidence URLs, and fabricated verification "
    "metadata. Metrics measure imitation of that generator, not real user preference, "
    "real flood risk, or operational readiness. Do not deploy or use for decisions."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.name.encode("utf-8"))
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def require_synthetic_source(dataset_dir: Path) -> None:
    generator = dataset_dir / "generate_datasets.py"
    if not generator.is_file():
        raise FileNotFoundError(
            f"Missing {generator.name}; provenance must be checked before training."
        )
    source = generator.read_text(encoding="utf-8")
    required_markers = (
        "random.random() < click_prob",
        "actual_flooded = (flood_score >= 0.50)",
        "https://flood-evidence.localexplore.ai/records/",
    )
    missing = [marker for marker in required_markers if marker not in source]
    if missing:
        raise ValueError(
            "The expected simulation provenance markers were not found in "
            f"generate_datasets.py: {missing}. Review the source before training."
        )


def _truth(value: Any) -> bool:
    return str(value).strip().casefold() in {"true", "1", "yes", "y"}


def _num(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _ranker_source_rows(dataset_dir: Path) -> pd.DataFrame:
    impressions = pd.read_csv(dataset_dir / "ranker_impressions.csv", dtype=str).fillna("")
    items = pd.read_csv(dataset_dir / "ranker_items.csv", dtype=str).fillna("")
    if impressions["request_id"].eq("").any() or impressions["item_key"].eq("").any():
        raise ValueError("Ranker data has an empty request_id/item_key.")
    if items["item_key"].duplicated().any():
        raise ValueError("ranker_items.csv has duplicate item_key values.")
    merged = impressions.merge(items, on="item_key", how="left", validate="many_to_one", suffixes=("", "_item"))
    if merged["category"].eq("").any():
        raise ValueError("Some impressions do not join to ranker_items.csv.")

    # Unviewed candidates are censored, not negative feedback. The synthetic
    # generator only allows clicks after a view, so train on viewable rows only.
    merged = merged[merged["was_viewable"].map(_truth)].copy()
    for column in ("clicked", "saved", "booking_created"):
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0).astype(int)
    merged["relevance_grade"] = np.select(
        [merged["booking_created"].eq(1), merged["saved"].eq(1), merged["clicked"].eq(1)],
        [3, 2, 1],
        default=0,
    ).astype(int)
    merged["event_time_utc"] = pd.to_datetime(merged["event_time_utc"], utc=True, errors="coerce")
    if merged["event_time_utc"].isna().any():
        raise ValueError("Ranker event_time_utc contains invalid timestamps.")
    return merged


def _ranker_feature_frame(rows: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    feature_rows: list[dict[str, float]] = []
    baseline_pairs: list[dict[str, Any]] = []
    for row in rows.to_dict(orient="records"):
        # DATA_ngay17 has an intent, item category/type, price, duration, party
        # size and optional price ceiling. ETA and live context are absent and
        # remain missing; no values are fabricated for them.
        query = {
            "user_intent_tags": row["context_primary_intent"],
            "group_size": _num(row["party_size"]),
            "budget_remaining_vnd": _num(row["price_max_vnd"]),
        }
        price = _num(row["price_vnd"])
        party_size = _num(row["party_size"])
        basis = row["price_basis"].strip().casefold()
        candidate: dict[str, Any] = {
            "candidate_tags": f"{row['category']}|{row['item_type']}",
            "duration_min": _num(row["duration_min"]),
            "is_hands_on": row["is_hands_on"],
            "is_indoor": row["is_indoor"],
        }
        if price is not None:
            if basis == "per_person":
                candidate["price_vnd_per_person"] = price
            elif basis == "per_item":
                candidate["total_cost_vnd"] = price
            elif basis == "free":
                candidate["total_cost_vnd"] = 0.0
            elif party_size and party_size > 0:
                # Unknown price basis is not treated as a per-person amount.
                candidate["total_cost_vnd"] = price
        feature_rows.append(build_feature_row(query, candidate))
        baseline_pairs.append({"query": query, "candidate": candidate})
    frame = pd.DataFrame(feature_rows, columns=FEATURE_NAMES)
    if list(frame.columns) != FEATURE_NAMES:
        raise AssertionError("Ranker feature builder drifted from the API feature schema.")
    return frame, baseline_pairs


def _ndcg_by_request(rows: pd.DataFrame, scores: np.ndarray, k: int = 5) -> float:
    work = rows[["request_id", "relevance_grade"]].copy()
    work["score"] = np.asarray(scores, dtype=float)
    values: list[float] = []
    for _, group in work.groupby("request_id", sort=False):
        labels = group["relevance_grade"].to_numpy(dtype=float)
        predictions = group["score"].to_numpy(dtype=float)
        # sklearn's ndcg_score handles all-zero relevance groups as zero.
        values.append(float(ndcg_score([labels], [predictions], k=min(k, len(labels)))))
    return float(np.mean(values)) if values else 0.0


def train_ranker(dataset_dir: Path, output_dir: Path, dataset_hash: str) -> dict[str, Any]:
    rows = _ranker_source_rows(dataset_dir)
    features, baseline_pairs = _ranker_feature_frame(rows)
    labels = rows["relevance_grade"].to_numpy(dtype=int)

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED)
    train_idx, test_idx = next(splitter.split(features, labels, groups=rows["request_id"]))
    train = rows.iloc[train_idx].copy()
    test = rows.iloc[test_idx].copy()
    x_train, x_test = features.iloc[train_idx], features.iloc[test_idx]
    y_train = labels[train_idx]
    train_groups = train.groupby("request_id", sort=False).size().to_list()
    if len(train_groups) < 2 or len(set(y_train)) < 2:
        raise ValueError("Ranker split is too small or has no label variation.")

    model = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=15,
        min_child_samples=10,
        random_state=SEED,
        n_jobs=1,
        verbosity=-1,
    )
    model.fit(x_train, y_train, group=train_groups)
    predictions = model.predict(x_test)
    baseline_scores: list[float] = []
    from app.services.ranker_baseline import rule_baseline_score

    for idx in test_idx:
        pair = baseline_pairs[int(idx)]
        baseline_scores.append(rule_baseline_score(pair["query"], pair["candidate"]))

    metrics = {
        "dataset_status": "synthetic_simulated",
        "warning": WARNING,
        "split_method": "GroupShuffleSplit by request_id; 25% held out",
        "seed": SEED,
        "train_requests": int(train["request_id"].nunique()),
        "test_requests": int(test["request_id"].nunique()),
        "train_viewable_impressions": int(len(train)),
        "test_viewable_impressions": int(len(test)),
        "label_distribution_train": {
            str(k): int(v) for k, v in train["relevance_grade"].value_counts().sort_index().items()
        },
        "label_distribution_test": {
            str(k): int(v) for k, v in test["relevance_grade"].value_counts().sort_index().items()
        },
        "test_ndcg_at_5": {
            "lightgbm_ranker": _ndcg_by_request(test, predictions, 5),
            "rule_baseline": _ndcg_by_request(test, np.asarray(baseline_scores), 5),
        },
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "position_used_as_feature": False,
        "only_viewable_impressions_used": True,
        "limitations": [
            "The generator creates synthetic clicks/saves/bookings with random probabilities.",
            "The outcome labels are not real traveler feedback.",
            "The CSV omits live ETA, remaining time, weather and AQI; their features stay missing.",
            "Some item prices are per item and others per person; unknown price basis is not normalized.",
            "The held-out metric only measures this generator's weak-label process.",
        ],
    }

    # Metrics above stay on the untouched request holdout. The exported
    # experiment artifact is refit on all rows after that evaluation.
    all_groups = rows.groupby("request_id", sort=False).size().to_list()
    final_model = lgb.LGBMRanker(
        objective="lambdarank",
        metric="ndcg",
        n_estimators=100,
        learning_rate=0.05,
        num_leaves=15,
        min_child_samples=10,
        random_state=SEED,
        n_jobs=1,
        verbosity=-1,
    )
    final_model.fit(features, labels, group=all_groups)
    model_file = "ranker_model.txt"
    final_model.booster_.save_model(str(output_dir / model_file))
    joblib.dump(final_model, output_dir / "ranker_model.pkl", compress=3)
    write_json(output_dir / "ranker_metrics.json", metrics)
    write_json(output_dir / "feature_schema.json", {
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "feature_builder": "apps/api/app/services/ranker_features.py::build_feature_row",
        "input_mapping": "DATA_ngay17 offline mapping; absent ETA/time/weather values remain missing",
        "target": "synthetic relevance grade from generated click/save/booking fields",
    })
    ranker_metadata = {
        "model_version": "localexplorer-dataset17-ranker-experiment-v1",
        "model_family": "lightgbm",
        "model_file": model_file,
        "model_sha256": sha256_file(output_dir / model_file),
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "dataset_status": "synthetic_simulated",
        "model_mode": "offline_experiment",
        "deployment_eligible": False,
        "production_eligible": False,
        "pilot_runtime_eligible": False,
        "source_dataset_sha256": dataset_hash,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "warning": WARNING,
    }
    write_json(output_dir / "model_metadata.json", ranker_metadata)
    return metrics


def _flood_training_data(dataset_dir: Path) -> tuple[pd.DataFrame, pd.Series]:
    observations = pd.read_csv(dataset_dir / "flood_observations.csv", dtype=str).fillna("")
    features = pd.read_csv(dataset_dir / "flood_features.csv", dtype=str).fillna("")
    if observations["observation_id"].duplicated().any() or features["observation_id"].duplicated().any():
        raise ValueError("Flood observation_id must be unique in both files.")
    merged = observations.merge(features, on="observation_id", how="inner", validate="one_to_one", suffixes=("", "_feature"))
    if len(merged) != len(observations):
        raise ValueError("Some flood observations do not join to flood_features.csv.")

    # Never infer unknown/disputed labels. Note: the generator fabricates the
    # 'verified' status too, so this is only a simulation subset.
    eligible = merged["label_status"].isin(["verified_positive", "verified_negative"])
    data = merged.loc[eligible].copy()
    data["target"] = pd.to_numeric(data["label_flooded"], errors="coerce")
    if data["target"].isna().any() or not set(data["target"].astype(int).unique()).issubset({0, 1}):
        raise ValueError("Flood labels must be binary for the two selected statuses.")
    expected = data["label_status"].map({"verified_positive": 1, "verified_negative": 0}).astype(int)
    if not data["target"].astype(int).eq(expected).all():
        raise ValueError("Flood label/status mismatch.")
    data["target_start_utc"] = pd.to_datetime(data["target_start_utc"], utc=True, errors="coerce")
    if data["target_start_utc"].isna().any():
        raise ValueError("Flood target_start_utc contains invalid timestamps.")
    for column in FLOOD_FEATURES:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if data[FLOOD_FEATURES].isna().all(axis=1).any():
        raise ValueError("Flood rows with all feature values missing are not trainable.")
    return data, data["target"].astype(int)


def train_flood(dataset_dir: Path, output_dir: Path, dataset_hash: str) -> dict[str, Any]:
    data, target = _flood_training_data(dataset_dir)
    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=SEED)
    train_idx, test_idx = next(splitter.split(data[FLOOD_FEATURES], target, groups=data["group_id"]))
    train = data.iloc[train_idx]
    test = data.iloc[test_idx]
    y_train = target.iloc[train_idx].to_numpy(dtype=int)
    y_test = target.iloc[test_idx].to_numpy(dtype=int)
    if len(set(y_train)) < 2 or len(set(y_test)) < 2:
        raise ValueError("Flood group split must contain both classes in train and test.")

    preprocessor = SimpleImputer(strategy="median", add_indicator=True)
    x_train = preprocessor.fit_transform(train[FLOOD_FEATURES])
    x_test = preprocessor.transform(test[FLOOD_FEATURES])
    model = HistGradientBoostingClassifier(
        learning_rate=0.07,
        max_iter=100,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=SEED,
    )
    model.fit(x_train, y_train)
    probability = model.predict_proba(x_test)[:, 1]
    threshold = 0.40  # Same exploratory threshold used by the supplied baseline.
    prediction = (probability >= threshold).astype(int)
    metrics = {
        "dataset_status": "synthetic_simulated",
        "warning": WARNING,
        "split_method": "GroupShuffleSplit by group_id; 25% held out",
        "seed": SEED,
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "train_groups": int(train["group_id"].nunique()),
        "test_groups": int(test["group_id"].nunique()),
        "train_class_counts": {str(k): int(v) for k, v in train["target"].value_counts().sort_index().items()},
        "test_class_counts": {str(k): int(v) for k, v in test["target"].value_counts().sort_index().items()},
        "test": {
            "average_precision": float(average_precision_score(y_test, probability)),
            "brier_score": float(brier_score_loss(y_test, probability)),
            "recall_at_threshold": float(recall_score(y_test, prediction, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_test, probability)),
            "threshold": threshold,
        },
        "feature_names": FLOOD_FEATURES,
        "limitations": [
            "The generator computes labels from a hard-coded flood_score formula using these predictors.",
            "The evidence URLs and verification metadata are placeholders generated by the script.",
            "This metric is simulator-rule imitation, not measured flood-risk performance.",
            "Group holdout is spatial only; the few synthetic weather events are shared across groups.",
            "The CSV schema does not match the production flood API feature contract.",
        ],
    }

    # Save a standalone offline model and a bundle layout recognized by the API
    # loader. The explicit demo_mode=true flag makes the API refuse inference.
    # Evaluate the held-out group split above, then export a final artifact
    # refit on the full synthetic dataset.
    final_preprocessor = SimpleImputer(strategy="median", add_indicator=True)
    final_x = final_preprocessor.fit_transform(data[FLOOD_FEATURES])
    final_model = HistGradientBoostingClassifier(
        learning_rate=0.07,
        max_iter=100,
        max_leaf_nodes=15,
        l2_regularization=1.0,
        random_state=SEED,
    )
    final_model.fit(final_x, target.to_numpy(dtype=int))
    joblib.dump(final_model, output_dir / "flood_model.pkl", compress=3)
    joblib.dump(final_model, output_dir / "model.joblib", compress=3)
    joblib.dump(final_preprocessor, output_dir / "preprocessor.joblib", compress=3)
    write_json(output_dir / "flood_metrics.json", metrics)
    # The runtime reads feature_schema.json. It will reject the bundle before
    # loading these fields because metadata marks this as a simulated demo.
    write_json(output_dir / "feature_schema.json", {
        "schema_version": 1,
        "numeric_features": FLOOD_FEATURES,
        "categorical_features": [],
        "source": "DATA_ngay17 flood_features.csv",
    })
    write_json(output_dir / "calibration.json", {
        "method": "sigmoid",
        "coef": 1.0,
        "intercept": 0.0,
        "status": "identity placeholder; not calibrated",
    })
    write_json(output_dir / "threshold.json", {
        "threshold": threshold,
        "status": "exploratory only; not an operational alert threshold",
    })
    counts = data["label_status"].value_counts().to_dict()
    flood_metadata = {
        "model_version": "localexplorer-dataset17-flood-experiment-v1",
        "demo_mode": True,
        "dataset_status": "synthetic_simulated",
        "deployment_eligible": False,
        "source_dataset_sha256": dataset_hash,
        "observation_rows_used": int(len(data)),
        "simulated_status_counts": {str(k): int(v) for k, v in counts.items()},
        "metrics": {"test": metrics["test"]},
        "created_at_utc": datetime.now(UTC).isoformat(),
        "warning": WARNING,
    }
    write_json(output_dir / "metadata.json", flood_metadata)
    return metrics


def run(dataset_dir: Path, output_dir: Path) -> dict[str, Any]:
    dataset_dir = dataset_dir.resolve()
    output_dir = output_dir.resolve()
    required = [
        "dataset_manifest.json",
        "ranker_impressions.csv",
        "ranker_items.csv",
        "flood_observations.csv",
        "flood_features.csv",
    ]
    missing = [name for name in required if not (dataset_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing dataset files: {missing}")
    require_synthetic_source(dataset_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    ranker_dir = output_dir / "ranker"
    flood_dir = output_dir / "flood-risk"
    ranker_dir.mkdir(exist_ok=True)
    flood_dir.mkdir(exist_ok=True)
    dataset_paths = [dataset_dir / name for name in required if name.endswith(".csv")]
    dataset_hash = sha256_files(dataset_paths)
    report = {
        "report_version": 1,
        "dataset_dir": str(dataset_dir),
        "output_dir": str(output_dir),
        "dataset_sha256": dataset_hash,
        "created_at_utc": datetime.now(UTC).isoformat(),
        "synthetic_source_confirmed": True,
        "python_version": sys.version.split()[0],
        "numpy_version": np.__version__,
        "pandas_version": pd.__version__,
        "scikit_learn_version": sklearn.__version__,
        "lightgbm_version": lgb.__version__,
        "warning": WARNING,
    }
    report["ranker"] = train_ranker(dataset_dir, ranker_dir, dataset_hash)
    report["flood"] = train_flood(dataset_dir, flood_dir, dataset_hash)
    write_json(output_dir / "experiment_report.json", report)
    (output_dir / "MODEL_CARD.md").write_text(_model_card(report), encoding="utf-8")
    return report


def _model_card(report: dict[str, Any]) -> str:
    ranker = report["ranker"]
    flood = report["flood"]
    return f"""# DATA_ngay17 offline model experiments

**Status: synthetic experiment only. Not production eligible.**

{WARNING}

## Ranker

- Algorithm: LightGBM LambdaMART.
- Split: held-out `request_id` groups; only viewable impressions; `position` excluded as a feature.
- Test NDCG@5: model `{ranker['test_ndcg_at_5']['lightgbm_ranker']:.4f}`, rule baseline `{ranker['test_ndcg_at_5']['rule_baseline']:.4f}`.
- Input mapping: uses the project's `ranker-features-v2` builder. Missing ETA, remaining time, weather and AQI remain missing.
- Labels: simulated clicks, saves and bookings from `generate_datasets.py`, not real behavior.

## Flood risk

- Algorithm: scikit-learn HistGradientBoostingClassifier.
- Split: held-out `group_id` groups.
- Test Average Precision: `{flood['test']['average_precision']:.4f}`; Brier: `{flood['test']['brier_score']:.4f}`; recall at 0.40: `{flood['test']['recall_at_threshold']:.4f}`.
- The generator defines the label using a hard-coded score made from these same weather/terrain predictors. The evidence URLs and `verified_*` status are generated placeholders.
- The data schema is not the production Flood API schema.

## Runtime gate

The ranker metadata sets `deployment_eligible=false` and `pilot_runtime_eligible=false`. The flood metadata sets `demo_mode=true` and `deployment_eligible=false`. The application's existing services must refuse both artifacts. Keep the rule-based ranker and existing flood behavior active.

## Files

- `ranker/ranker_model.pkl`, `ranker/ranker_model.txt`, `ranker/model_metadata.json`, `ranker/feature_schema.json`, `ranker/ranker_metrics.json`
- `flood-risk/flood_model.pkl`, `flood-risk/model.joblib`, `flood-risk/preprocessor.joblib`, `flood-risk/metadata.json`, `flood-risk/feature_schema.json`, `flood-risk/calibration.json`, `flood-risk/threshold.json`, `flood-risk/flood_metrics.json`
- `experiment_report.json`, `MODEL_CARD.md`

## Promotion requirements

Replace these simulations with consented, real impression outcomes and audited source-backed flood observations; align flood features to the API contract; use time and spatially separated evaluation; independently review provenance, calibration, thresholds, and model card. Do not promote by changing metadata flags.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-dir", type=Path, default=ROOT / "data" / "dataset")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "models" / "dataset-17-experiment")
    args = parser.parse_args()
    report = run(args.dataset_dir, args.output_dir)
    print(json.dumps({
        "output_dir": str(args.output_dir.resolve()),
        "ranker_ndcg_at_5": report["ranker"]["test_ndcg_at_5"],
        "flood_test": report["flood"]["test"],
        "deployment_eligible": False,
        "warning": WARNING,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
