"""Optional local XGBoost/LightGBM ranker; missing artifacts fall back safely."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.ranker_features import (
    FEATURE_VERSION,
    LEGACY_FEATURE_VERSION,
    build_feature_row,
    build_feature_row_v1,
    feature_names_for_version,
    is_hard_feasible,
)


class MLRankerUnavailable(RuntimeError):
    pass


class MLRankerService:
    def __init__(self, artifact_dir: str | None = None):
        configured = artifact_dir if artifact_dir is not None else settings.ranker_model_dir
        self.artifact_dir = Path(configured).expanduser() if configured else None
        self._model = None
        self._metadata: dict[str, Any] = {}
        self._feature_version = LEGACY_FEATURE_VERSION
        self._error: str | None = None

    def _read_metadata(self) -> dict[str, Any]:
        if not self.artifact_dir:
            return {}
        path = self.artifact_dir / "model_metadata.json"
        try:
            return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def _artifact_path(self, metadata: dict[str, Any]) -> Path | None:
        if not self.artifact_dir:
            return None
        filename = metadata.get("model_file", "local_explorer_ranker.json")
        if not isinstance(filename, str) or Path(filename).name != filename:
            return None
        return self.artifact_dir / filename

    @property
    def configured(self) -> bool:
        metadata = self._read_metadata()
        artifact = self._artifact_path(metadata)
        return bool(
            self.artifact_dir
            and artifact
            and artifact.is_file()
            and (self.artifact_dir / "model_metadata.json").is_file()
            and (self.artifact_dir / "feature_schema.json").is_file()
        )

    def status(self) -> dict[str, Any]:
        metadata = self._read_metadata()
        dataset_status = metadata.get("dataset_status", "unknown")
        explicitly_non_deployable = (
            dataset_status == "weak_label_experiment"
            or metadata.get("deployment_eligible") is False
        )
        production_eligible = (
            dataset_status == "verified_human_labeled"
            and not explicitly_non_deployable
        )
        blocked_for_provenance = (
            explicitly_non_deployable
            or (
                not production_eligible
                and settings.app_env.lower() not in {"development", "test"}
                and not settings.allow_unverified_ranker
            )
        )
        return {
            "configured": self.configured,
            "loaded": self._model is not None,
            "model_version": metadata.get("model_version"),
            "model_family": metadata.get("model_family", "xgboost"),
            "feature_version": metadata.get("feature_version", LEGACY_FEATURE_VERSION),
            "dataset_status": dataset_status,
            "production_eligible": production_eligible,
            "deployment_allowed": self.configured and not blocked_for_provenance,
            "block_reason": (
                "Ranker artifact files are missing or incomplete." if not self.configured
                else "Weak-label experiment artifacts are never deployable." if dataset_status == "weak_label_experiment"
                else "Ranker metadata marks this artifact non-deployable." if metadata.get("deployment_eligible") is False
                else "Unverified ranking labels are disabled in production." if blocked_for_provenance
                else None
            ),
            "warning": metadata.get("warning"),
            "error": self._error,
        }

    def _load(self):
        if self._model is not None:
            return self._model
        if not self.configured or self.artifact_dir is None:
            raise MLRankerUnavailable("Ranker artifact is not configured. Put the trained bundle in RANKER_MODEL_DIR.")
        try:
            self._metadata = json.loads((self.artifact_dir / "model_metadata.json").read_text(encoding="utf-8"))
            schema = json.loads((self.artifact_dir / "feature_schema.json").read_text(encoding="utf-8"))
            self._feature_version = self._metadata.get("feature_version", LEGACY_FEATURE_VERSION)
            expected_features = feature_names_for_version(self._feature_version)
            if self._metadata.get("feature_names") != expected_features:
                raise ValueError("Ranker feature schema does not match this API version.")
            if schema.get("feature_names") != expected_features:
                raise ValueError("Ranker feature schema file does not match this API version.")
            schema_version = schema.get("feature_version")
            if schema_version and schema_version != self._feature_version:
                raise ValueError("Ranker feature version metadata is inconsistent.")
            dataset_status = self._metadata.get("dataset_status", "unknown")
            explicitly_non_deployable = (
                dataset_status == "weak_label_experiment"
                or self._metadata.get("deployment_eligible") is False
            )
            production_eligible = dataset_status == "verified_human_labeled" and not explicitly_non_deployable
            if explicitly_non_deployable:
                raise ValueError("Weak-label or explicitly non-deployable ranker artifacts are never loaded by the API.")
            if (not production_eligible
                    and settings.app_env.lower() not in {"development", "test"}
                    and not settings.allow_unverified_ranker):
                raise ValueError("Production requires dataset_status=verified_human_labeled or ALLOW_UNVERIFIED_RANKER=true.")
            artifact = self._artifact_path(self._metadata)
            if artifact is None or not artifact.is_file():
                raise ValueError("Ranker model_file is missing or invalid.")
            family = self._metadata.get("model_family", "xgboost")
            if family == "xgboost":
                import xgboost as xgb

                model = xgb.XGBRanker()
                model.load_model(str(artifact))
            elif family == "lightgbm":
                import lightgbm as lgb

                model = lgb.Booster(model_file=str(artifact))
            else:
                raise ValueError(f"Unsupported ranker model_family: {family}")
            self._model = model
            return model
        except Exception as error:
            self._error = f"{type(error).__name__}: {error}"
            raise MLRankerUnavailable("Unable to load the local ranker artifact.") from error

    def rank(self, query: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
        model = self._load()
        feasible: list[dict[str, Any]] = []
        rejected_ids: list[str] = []
        for candidate in candidates:
            if is_hard_feasible(query, candidate):
                feasible.append(candidate)
            else:
                rejected_ids.append(str(candidate.get("candidate_experience_id", "")))
        if not feasible:
            return [], rejected_ids, self.status()

        import pandas as pd

        row_builder = build_feature_row if self._feature_version == FEATURE_VERSION else build_feature_row_v1
        feature_names = feature_names_for_version(self._feature_version)
        matrix = pd.DataFrame([row_builder(query, candidate) for candidate in feasible], columns=feature_names)
        try:
            scores = model.predict(matrix)
        except Exception as error:
            self._error = f"{type(error).__name__}: {error}"
            raise MLRankerUnavailable("The local ranker could not score this feature batch.") from error
        ranked = [{**candidate, "rank_score": float(score)} for candidate, score in zip(feasible, scores, strict=True)]
        ranked.sort(key=lambda item: item["rank_score"], reverse=True)
        return ranked, rejected_ids, self.status()


ranker_service = MLRankerService()
