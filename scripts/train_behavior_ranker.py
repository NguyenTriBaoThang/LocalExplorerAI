"""Compare a behavior-aware XGBoost ranker with rule-based baselines.

This experiment accepts only datasets produced by
build_behavior_ranking_dataset.py. It writes a local research artifact and
does not modify the API's active ranker bundle.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "apps" / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.services.ranker_baseline import rule_baseline_score  # noqa: E402
from app.services.ranker_features import FEATURE_NAMES, build_feature_row  # noqa: E402


DEFAULT_DATA = ROOT / "data" / "derived" / "behavior-ranking" / "training_dataset.csv"
DEFAULT_OUTPUT = ROOT / "models" / "ai-ranker" / "behavior-experiment"
PERSONAL_FEATURES = [
    "user_has_history",
    "user_history_count_90d",
    "user_candidate_tag_affinity",
    "user_price_affinity",
    "user_indoor_affinity",
]
FEATURE_COLUMNS = [*FEATURE_NAMES, *PERSONAL_FEATURES]
FORBIDDEN_FEATURES = {
    "query_id", "user_key", "candidate_experience_id", "display_position",
    "event_time", "label_grade", "label_reason", "outcome_time", "consent_version",
}
BUDGET_MIDPOINTS = {
    "under_500k": 250_000,
    "500k_1m": 750_000,
    "1m_2m": 1_500_000,
    "over_2m": 2_500_000,
}


class BehaviorDatasetError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tags(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(";") if part.strip()]


def _number(value: Any, default: float = math.nan) -> float:
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else default
    except (TypeError, ValueError):
        return default


def read_behavior_dataset(path: Path) -> pd.DataFrame:
    metadata_path = path.with_suffix(".metadata.json")
    if not path.is_file() or not metadata_path.is_file():
        raise BehaviorDatasetError("Expected the CSV and its .metadata.json from build_behavior_ranking_dataset.py.")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("dataset_kind") != "consented_user_behavior":
        raise BehaviorDatasetError("Dataset provenance is not consented user behavior.")
    frame = pd.read_csv(path, encoding="utf-8-sig")
    required = {
        "query_id", "user_key", "event_time", "candidate_experience_id", "display_position",
        "user_intent_tags", "budget_band", "group_size", "candidate_tags", "candidate_price_vnd",
        "candidate_price_basis", "duration_min", "is_hands_on", "is_indoor", "user_has_history",
        "user_history_count_90d", "user_candidate_tag_affinity", "user_price_affinity",
        "user_indoor_affinity", "label_grade", "label_reason", "consent_version",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise BehaviorDatasetError(f"Missing columns: {missing}")
    if frame.empty:
        raise BehaviorDatasetError("Dataset is empty.")
    if frame[list(required)].isna().all(axis=1).any():
        raise BehaviorDatasetError("Dataset contains a completely empty row.")
    grades = pd.to_numeric(frame["label_grade"], errors="raise")
    if not grades.isin([0, 1, 2, 3]).all() or not np.equal(grades.to_numpy(), np.floor(grades.to_numpy())).all():
        raise BehaviorDatasetError("label_grade must be an integer from 0 to 3.")
    if frame.duplicated(["query_id", "candidate_experience_id"]).any():
        raise BehaviorDatasetError("Duplicate candidate within a recommendation request.")
    frame["label_grade"] = grades.astype(int)
    frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True, errors="raise")
    return frame


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, float]] = []
    for row in frame.to_dict(orient="records"):
        user_tags = _tags(row.get("user_intent_tags"))
        candidate_tags = _tags(row.get("candidate_tags"))
        group_size = _number(row.get("group_size"))
        price = _number(row.get("candidate_price_vnd"))
        price_basis = row.get("candidate_price_basis")
        total_cost = price * group_size if price_basis == "per_person" else price
        query = {
            "user_intent_tags": user_tags,
            "remaining_time_min": None,
            "group_size": group_size,
            "budget_remaining_vnd": BUDGET_MIDPOINTS.get(str(row.get("budget_band")), None),
        }
        candidate = {
            "candidate_tags": candidate_tags,
            "duration_min": row.get("duration_min"),
            "price_vnd_per_person": price if price_basis == "per_person" else None,
            "total_cost_vnd": total_cost,
            "is_hands_on": row.get("is_hands_on"),
            "is_indoor": row.get("is_indoor"),
            "eta_min": None,
        }
        features = build_feature_row(query, candidate)
        features.update({
            "user_has_history": _number(row.get("user_has_history"), 0.0),
            "user_history_count_90d": math.log1p(max(0.0, _number(row.get("user_history_count_90d"), 0.0))),
            "user_candidate_tag_affinity": _number(row.get("user_candidate_tag_affinity"), 0.0),
            "user_price_affinity": _number(row.get("user_price_affinity"), 0.0),
            "user_indoor_affinity": _number(row.get("user_indoor_affinity"), 0.0),
        })
        rows.append(features)
    matrix = pd.DataFrame(rows, columns=FEATURE_COLUMNS, dtype=float)
    if list(matrix.columns) != FEATURE_COLUMNS or FORBIDDEN_FEATURES.intersection(matrix.columns):
        raise BehaviorDatasetError("Feature contract contains a forbidden or misordered column.")
    return matrix


def rankable_groups(frame: pd.DataFrame) -> pd.DataFrame:
    valid_ids = []
    for query_id, group in frame.groupby("query_id", sort=False):
        if len(group) >= 2 and (group["label_grade"] > 0).any():
            valid_ids.append(query_id)
    return frame.loc[frame["query_id"].isin(valid_ids)].copy()


def temporal_split(frame: pd.DataFrame) -> dict[str, set[str]]:
    grouped = frame.groupby("query_id", as_index=False)["event_time"].min().sort_values(["event_time", "query_id"])
    query_ids = grouped["query_id"].astype(str).tolist()
    if len(query_ids) < 20:
        raise BehaviorDatasetError(
            f"Only {len(query_ids)} useful request groups; at least 20 are required for a cautious comparison."
        )
    train_end = max(1, int(len(query_ids) * 0.70))
    validation_end = max(train_end + 1, int(len(query_ids) * 0.85))
    validation_end = min(validation_end, len(query_ids) - 1)
    return {
        "train": set(query_ids[:train_end]),
        "validation": set(query_ids[train_end:validation_end]),
        "test": set(query_ids[validation_end:]),
    }


def ndcg_at_k(labels: np.ndarray, scores: np.ndarray, k: int = 5) -> float:
    order = np.argsort(-scores, kind="stable")[:k]
    ideal = np.argsort(-labels, kind="stable")[:k]
    discounts = np.log2(np.arange(2, len(order) + 2))
    ideal_discounts = np.log2(np.arange(2, len(ideal) + 2))
    gains = np.exp2(labels.astype(float)) - 1.0
    dcg = float(np.sum(gains[order] / discounts))
    idcg = float(np.sum(gains[ideal] / ideal_discounts))
    return dcg / idcg if idcg else math.nan


def recall_at_k(labels: np.ndarray, scores: np.ndarray, k: int = 5) -> float:
    relevant = labels > 0
    total = int(relevant.sum())
    if total == 0:
        return math.nan
    top = np.argsort(-scores, kind="stable")[:k]
    return float(relevant[top].sum() / total)


def grouped_metrics(frame: pd.DataFrame, scores: np.ndarray) -> dict[str, float | int]:
    ndcgs, recalls = [], []
    offset = 0
    for _, group in frame.groupby("query_id", sort=False):
        count = len(group)
        labels = group["label_grade"].to_numpy(dtype=int)
        group_scores = scores[offset:offset + count]
        offset += count
        ndcgs.append(ndcg_at_k(labels, group_scores))
        recalls.append(recall_at_k(labels, group_scores))
    return {
        "request_count": len(ndcgs),
        "ndcg_at_5": float(np.nanmean(ndcgs)) if ndcgs else math.nan,
        "recall_at_5": float(np.nanmean(recalls)) if recalls else math.nan,
    }


def baseline_scores(frame: pd.DataFrame, personalized: bool) -> np.ndarray:
    scores = []
    for row in frame.to_dict(orient="records"):
        query = {"user_intent_tags": _tags(row.get("user_intent_tags"))}
        candidate = {"candidate_tags": _tags(row.get("candidate_tags"))}
        score = rule_baseline_score(query, candidate)
        if personalized:
            score += (
                2.0 * _number(row.get("user_candidate_tag_affinity"), 0.0)
                + 0.5 * _number(row.get("user_price_affinity"), 0.0)
                + 0.5 * _number(row.get("user_indoor_affinity"), 0.0)
            )
        scores.append(score)
    return np.asarray(scores, dtype=float)


def ordered_subset(frame: pd.DataFrame, query_ids: set[str]) -> pd.DataFrame:
    subset = frame.loc[frame["query_id"].astype(str).isin(query_ids)].copy()
    query_order = subset.groupby("query_id")["event_time"].min().sort_values(kind="stable")
    order_map = {query_id: index for index, query_id in enumerate(query_order.index)}
    subset["_query_order"] = subset["query_id"].map(order_map)
    return subset.sort_values(["_query_order", "display_position"], kind="stable").drop(columns="_query_order").reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    if args.output.exists() and any(args.output.iterdir()) and not args.overwrite:
        raise SystemExit(f"Refusing to overwrite a non-empty output directory: {args.output}")

    try:
        frame = rankable_groups(read_behavior_dataset(args.data))
        splits = temporal_split(frame)
    except (BehaviorDatasetError, OSError, json.JSONDecodeError) as error:
        raise SystemExit(str(error)) from error

    train_frame = ordered_subset(frame, splits["train"])
    validation_frame = ordered_subset(frame, splits["validation"])
    test_frame = ordered_subset(frame, splits["test"])
    train_x = build_features(train_frame)
    train_y = train_frame["label_grade"].to_numpy(dtype=int)
    train_groups = train_frame.groupby("query_id", sort=False).size().tolist()

    try:
        from xgboost import XGBRanker
    except ImportError as error:
        raise SystemExit("Install apps/api/requirements-ranking-training.txt to run the behavior ranker experiment.") from error

    model = XGBRanker(
        objective="rank:ndcg",
        eval_metric="ndcg@5",
        n_estimators=120,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        reg_lambda=2.0,
        random_state=42,
        n_jobs=2,
        tree_method="hist",
    )
    model.fit(train_x, train_y, group=train_groups, verbose=False)

    test_x = build_features(test_frame)
    model_test_scores = model.predict(test_x)
    test_metrics = {
        "context_rule_baseline": grouped_metrics(test_frame, baseline_scores(test_frame, personalized=False)),
        "history_rule_baseline": grouped_metrics(test_frame, baseline_scores(test_frame, personalized=True)),
        "xgboost_ranker": grouped_metrics(test_frame, model_test_scores),
    }
    validation_scores = model.predict(build_features(validation_frame))
    validation_metrics = {
        "context_rule_baseline": grouped_metrics(validation_frame, baseline_scores(validation_frame, personalized=False)),
        "history_rule_baseline": grouped_metrics(validation_frame, baseline_scores(validation_frame, personalized=True)),
        "xgboost_ranker": grouped_metrics(validation_frame, validation_scores),
    }

    args.output.mkdir(parents=True, exist_ok=True)
    model_path = args.output / "behavior_ranker_research.json"
    model.save_model(model_path)
    report = {
        "dataset_kind": "consented_user_behavior",
        "dataset_sha256": sha256_file(args.data),
        "row_count": len(frame),
        "rankable_request_count": int(frame["query_id"].nunique()),
        "feature_names": FEATURE_COLUMNS,
        "label_counts": {str(label): int((frame["label_grade"] == label).sum()) for label in range(4)},
        "split": {name: len(query_ids) for name, query_ids in splits.items()},
        "validation_metrics": validation_metrics,
        "test_metrics": test_metrics,
        "artifact": str(model_path),
        "deployment_eligible": False,
        "limitations": [
            "Offline research artifact only; not loaded by the Local Explorer API.",
            "No-action impressions are weak implicit negatives and can reflect display-position bias.",
            "Itinerary-level star ratings are not assigned to individual stops.",
            "Temporal request holdout evaluates future requests; it does not measure unseen-user cold start separately.",
            "Use a later prospective or randomized evaluation before product rollout.",
        ],
    }
    (args.output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
