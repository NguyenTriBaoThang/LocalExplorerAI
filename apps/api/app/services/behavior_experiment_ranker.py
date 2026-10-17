"""Local-only inference for the separately trained behavior ranking experiment.

The imported model was trained on generated demo data. Keep it isolated from the
production experience ranker and require both development mode and user consent.
"""

from __future__ import annotations

import json
import math
import unicodedata
from pathlib import Path
from typing import Any

from app.core.config import settings


FEATURE_NAMES = [
    "feat_tag_jaccard",
    "feat_tag_overlap",
    "feat_target_budget",
    "feat_price_ratio",
    "feat_price_abs_diff",
    "feat_log_price",
    "feat_history_tag_affinity",
    "feat_history_price_affinity",
    "feat_history_count_log",
    "feat_distance_or_eta",
    "feat_duration_min",
    "feat_group_size",
    "feat_is_indoor",
    "feat_is_verified",
    "feat_is_available",
    "feat_hard_feasible",
    "feat_budget_band_code",
]

BUDGET_FEATURES = {
    "under_500k": (150_000.0, 0),
    "500k_1m": (450_000.0, 1),
    "1m_2m": (1_200_000.0, 2),
    "over_2m": (3_000_000.0, 3),
}


class BehaviorExperimentUnavailable(RuntimeError):
    pass


def _fold(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char)).strip()


def _tags(values: Any) -> set[str]:
    if isinstance(values, str):
        values = values.replace(";", ",").split(",")
    if not isinstance(values, (list, tuple, set)):
        return set()
    return {_fold(value) for value in values if _fold(value)}


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return radius_km * 2 * math.asin(math.sqrt(min(1.0, a)))


class BehaviorExperimentRanker:
    """A dev-only adapter from catalog records to the downloaded model schema."""

    def __init__(self, artifact_dir: Path | None = None):
        repo_root = Path(__file__).resolve().parents[4]
        self.artifact_dir = artifact_dir or repo_root / "models" / "behavior-ranker-experiment"
        self._metadata: dict[str, Any] | None = None
        self._model = None

    def status(self) -> dict[str, Any]:
        local_environment = settings.app_env.lower() in {"development", "dev", "test"}
        metadata_path = self.artifact_dir / "model_metadata.json"
        model_path = self.artifact_dir / "xgb_ranker.json"
        metadata: dict[str, Any] = {}
        try:
            if metadata_path.is_file():
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
        artifact_present = model_path.is_file() and metadata.get("model_family") == "xgboost"
        available = local_environment and artifact_present and metadata.get("dataset_status") == "synthetic_demo"
        return {
            "available": available,
            "model_version": metadata.get("model_version"),
            "dataset_status": metadata.get("dataset_status", "unknown"),
            "deployment_eligible": False,
            "warning": metadata.get("warning", "Demo model trained on generated data; results are for local evaluation only."),
        }

    def _load(self):
        if self._model is not None:
            return self._model
        status = self.status()
        if not status["available"]:
            raise BehaviorExperimentUnavailable("Behavior ranker is available only in local development with its demo artifact installed.")

        metadata_path = self.artifact_dir / "model_metadata.json"
        model_path = self.artifact_dir / "xgb_ranker.json"
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("feature_names", metadata.get("features")) != FEATURE_NAMES:
            raise BehaviorExperimentUnavailable("The behavior ranker feature schema does not match this API adapter.")
        if metadata.get("deployment_eligible") is not False:
            raise BehaviorExperimentUnavailable("This experiment must remain marked as non-deployable.")

        try:
            from xgboost import XGBRanker

            model = XGBRanker()
            # Loading from bytes avoids XGBoost's Windows path canonicalization
            # failing for a workspace-backed artifact in some sandboxed setups.
            model.load_model(bytearray(model_path.read_bytes()))
            if model.get_booster().num_features() != len(FEATURE_NAMES):
                raise ValueError("The model has an unexpected number of features.")
        except Exception as error:
            raise BehaviorExperimentUnavailable(f"Unable to load the behavior model: {type(error).__name__}.") from error

        self._metadata = metadata
        self._model = model
        return model

    def _feature_row(
        self,
        experience,
        query: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> dict[str, float]:
        budget_midpoint, budget_code = BUDGET_FEATURES[query["budget_band"]]
        group_size = max(1, int(query["group_size"]))
        price = float(experience.price_vnd or 0)
        if experience.price_basis == "per_group":
            price /= group_size

        candidate_tags = _tags(experience.intent_tags or [])
        intent_tags = _tags(query.get("intent_tags", []))
        union = candidate_tags | intent_tags
        overlap = len(candidate_tags & intent_tags)

        positive_history: list[tuple[set[str], float]] = []
        for event in history:
            snapshot = event.get("candidate_snapshot") or {}
            event_tags = _tags(snapshot.get("intent_tags") or [snapshot.get("primary_intent")])
            event_price = snapshot.get("price_vnd")
            if snapshot.get("price_basis") == "per_group" and event_price is not None:
                event_price = float(event_price) / group_size
            try:
                parsed_price = float(event_price)
            except (TypeError, ValueError):
                parsed_price = math.nan
            positive_history.append((event_tags, parsed_price))

        tag_weight = sum(1.0 for tags, _ in positive_history if tags & candidate_tags)
        history_count = len(positive_history)
        history_prices = [price_value for _, price_value in positive_history if math.isfinite(price_value) and price_value >= 0]
        average_history_price = sum(history_prices) / len(history_prices) if history_prices else budget_midpoint
        tag_affinity = tag_weight / max(history_count * 2 + 1, 1)
        price_affinity = 1.0 / (1.0 + abs(price - average_history_price) / 500_000.0)

        poi = experience.poi
        distance_km = _haversine_km(
            float(query.get("center_latitude", 10.7769)),
            float(query.get("center_longitude", 106.7009)),
            float(poi.latitude),
            float(poi.longitude),
        )
        available = any(
            slot.status not in {"full", "unavailable", "cancelled"} and slot.available_reported != 0
            for slot in (experience.slots or [])
        )
        if not experience.slots:
            available = True

        return {
            "feat_tag_jaccard": overlap / len(union) if union else 0.0,
            "feat_tag_overlap": float(overlap),
            "feat_target_budget": budget_midpoint,
            "feat_price_ratio": price / budget_midpoint if budget_midpoint else 0.0,
            "feat_price_abs_diff": abs(price - budget_midpoint),
            "feat_log_price": math.log1p(max(price, 0.0)),
            "feat_history_tag_affinity": tag_affinity,
            "feat_history_price_affinity": price_affinity,
            "feat_history_count_log": math.log1p(history_count),
            "feat_distance_or_eta": distance_km,
            "feat_duration_min": float(experience.duration_min or 0),
            "feat_group_size": float(group_size),
            "feat_is_indoor": float(bool(experience.is_indoor)),
            "feat_is_verified": float(experience.verification_status == "verified"),
            "feat_is_available": float(available),
            # The candidates came from the existing, already filtered Explore list.
            # This score is only a reranker and cannot make an excluded item appear.
            "feat_hard_feasible": 1.0,
            "feat_budget_band_code": float(budget_code),
        }

    def rank(
        self,
        experiences: list[Any],
        query: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        if not experiences:
            return []
        model = self._load()
        import pandas as pd

        matrix = pd.DataFrame(
            [self._feature_row(experience, query, history) for experience in experiences],
            columns=FEATURE_NAMES,
        )
        scores = model.predict(matrix)
        ranked = [
            {"experience_id": experience.id, "score": float(score)}
            for experience, score in zip(experiences, scores, strict=True)
        ]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked


behavior_experiment_ranker = BehaviorExperimentRanker()
