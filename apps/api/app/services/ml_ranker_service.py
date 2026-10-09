"""Optional local XGBoost/LightGBM ranker; missing artifacts fall back safely."""

from __future__ import annotations

import hashlib
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
from app.services.ranker_baseline import RULE_BASELINE_VERSION, rule_baseline_score


RULE_BASELINE_WARNING = (
    "Deterministic intent/category rules are active. This is not a trained model or "
    "human-preference validation; current weak-label metrics only measure rule imitation."
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
        self._load_failed = False
        self._integrity_signature: tuple[str, str, int, int] | None = None
        self._integrity_result: str | None = None

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

    def _integrity_error(self, metadata: dict[str, Any]) -> str | None:
        expected = metadata.get("model_sha256")
        if expected is None:
            return None  # Backward-compatible with older, already provenance-gated bundles.
        if not isinstance(expected, str) or len(expected) != 64 or any(char not in "0123456789abcdefABCDEF" for char in expected):
            return "Ranker metadata contains an invalid model SHA-256."
        artifact = self._artifact_path(metadata)
        if artifact is None or not artifact.is_file():
            return "Ranker model file is missing; bundle integrity could not be checked."
        try:
            stat = artifact.stat()
        except OSError as error:
            return f"Unable to inspect ranker model for integrity check: {error}"
        signature = (str(artifact.resolve()), expected.casefold(), stat.st_mtime_ns, stat.st_size)
        if signature == self._integrity_signature:
            return self._integrity_result
        digest = hashlib.sha256()
        try:
            with artifact.open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
        except OSError as error:
            result = f"Unable to read ranker model for integrity check: {error}"
            self._integrity_signature = signature
            self._integrity_result = result
            return result
        if digest.hexdigest().casefold() != expected.casefold():
            result = "Ranker model SHA-256 does not match metadata; refusing to load the artifact."
        else:
            result = None
        self._integrity_signature = signature
        self._integrity_result = result
        return result

    @property
    def configured(self) -> bool:
        metadata = self._read_metadata()
        artifact = self._artifact_path(metadata)
        complete = bool(
            self.artifact_dir
            and artifact
            and artifact.is_file()
            and (self.artifact_dir / "model_metadata.json").is_file()
            and (self.artifact_dir / "feature_schema.json").is_file()
        )
        return complete and self._integrity_error(metadata) is None

    @property
    def available(self) -> bool:
        """A ranker is always available because the versioned rule baseline is built in."""
        return True

    @staticmethod
    def _metadata_is_deployable(metadata: dict[str, Any]) -> bool:
        """Require explicit human-label provenance and an explicit promotion decision."""
        dataset_status = metadata.get("dataset_status")
        explicitly_blocked = (
            dataset_status == "weak_label_experiment"
            or metadata.get("deployment_eligible") is False
        )
        return (
            not explicitly_blocked
            and dataset_status == "verified_human_labeled"
            and metadata.get("deployment_eligible") is True
        )

    def status(self) -> dict[str, Any]:
        metadata = self._read_metadata()
        artifact_dataset_status = metadata.get("dataset_status", "unknown")
        production_eligible = self._metadata_is_deployable(metadata)
        configured = self.configured
        ml_allowed = configured and production_eligible and not self._load_failed
        integrity_error = self._integrity_error(metadata)
        if artifact_dataset_status == "weak_label_experiment":
            block_reason = "Weak-label experiment artifacts are never deployable."
        elif metadata.get("deployment_eligible") is False:
            block_reason = "Ranker metadata explicitly marks this artifact non-deployable."
        elif integrity_error:
            block_reason = integrity_error
        elif not configured:
            block_reason = "No complete ML bundle is installed; the built-in rule baseline is active."
        elif not production_eligible:
            block_reason = "ML requires dataset_status=verified_human_labeled and deployment_eligible=true."
        elif self._load_failed:
            block_reason = self._error or "The ML bundle failed to load; the built-in rule baseline is active."
        else:
            block_reason = None
        active_ranker = "ml_ranker" if ml_allowed else "rule_baseline"
        active_version = metadata.get("model_version") if ml_allowed else RULE_BASELINE_VERSION
        active_family = metadata.get("model_family", "xgboost") if ml_allowed else "rule_baseline"
        return {
            "configured": configured,
            "loaded": self._model is not None,
            "available": True,
            "active_ranker": active_ranker,
            "active_version": active_version,
            "model_version": active_version,
            "model_family": active_family,
            "fallback_active": active_ranker == "rule_baseline",
            "fallback_version": RULE_BASELINE_VERSION,
            "feature_version": metadata.get("feature_version", LEGACY_FEATURE_VERSION) if ml_allowed else None,
            "dataset_status": artifact_dataset_status if ml_allowed else "rule_based_no_training_labels",
            "artifact_dataset_status": artifact_dataset_status,
            "production_eligible": production_eligible,
            "deployment_allowed": ml_allowed,
            "artifact_integrity_error": integrity_error,
            "block_reason": block_reason,
            "warning": metadata.get("warning") if ml_allowed else RULE_BASELINE_WARNING,
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
            if not self._metadata_is_deployable(self._metadata):
                raise ValueError(
                    "ML requires dataset_status=verified_human_labeled and deployment_eligible=true; "
                    "weak-label artifacts are never loaded."
                )
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
            self._load_failed = True
            raise MLRankerUnavailable("Unable to load the local ranker artifact.") from error

    def rank(self, query: dict[str, Any], candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
        feasible: list[dict[str, Any]] = []
        rejected_ids: list[str] = []
        for candidate in candidates:
            if is_hard_feasible(query, candidate):
                feasible.append(candidate)
            else:
                rejected_ids.append(str(candidate.get("candidate_experience_id", "")))
        if not feasible:
            return [], rejected_ids, {**self.status(), "ranking_source": "none"}

        status = self.status()
        if status["deployment_allowed"]:
            try:
                model = self._load()
                import pandas as pd

                row_builder = build_feature_row if self._feature_version == FEATURE_VERSION else build_feature_row_v1
                feature_names = feature_names_for_version(self._feature_version)
                matrix = pd.DataFrame([row_builder(query, candidate) for candidate in feasible], columns=feature_names)
                scores = model.predict(matrix)
                ranked = [
                    {**candidate, "rank_score": float(score)}
                    for candidate, score in zip(feasible, scores, strict=True)
                ]
                ranked.sort(key=lambda item: item["rank_score"], reverse=True)
                return ranked, rejected_ids, {**self.status(), "ranking_source": "ml_model"}
            except Exception as error:
                self._error = f"{type(error).__name__}: {error}"
                self._load_failed = True

        ranked = [
            {**candidate, "rank_score": rule_baseline_score(query, candidate)}
            for candidate in feasible
        ]
        ranked.sort(key=lambda item: item["rank_score"], reverse=True)
        return ranked, rejected_ids, {
            **self.status(),
            "active_ranker": "rule_baseline",
            "active_version": RULE_BASELINE_VERSION,
            "model_version": RULE_BASELINE_VERSION,
            "model_family": "rule_baseline",
            "fallback_active": True,
            "ranking_source": "rule_baseline",
            "warning": RULE_BASELINE_WARNING,
        }


ranker_service = MLRankerService()
