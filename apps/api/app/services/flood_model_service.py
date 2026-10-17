"""Optional local inference for the bundle exported by the flood Colab."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings


class FloodModelUnavailable(RuntimeError):
    pass


def _deployment_block_reason(metadata: dict[str, Any]) -> str | None:
    if metadata.get("demo_mode") is not False:
        return "Flood bundle was trained in demo/simulated mode."
    if metadata.get("dataset_status") != "verified_human_labeled":
        return "Flood bundle does not declare verified human-labeled observations."
    counts = metadata.get("verified_observations")
    try:
        enough_observations = int(counts["verified_no_flood"]) >= 200 and int(counts["verified_flood"]) >= 100
    except (KeyError, TypeError, ValueError):
        enough_observations = False
    if not enough_observations:
        return "Flood bundle lacks the minimum verified positive and negative observation counts."
    metrics_data = metadata.get("metrics")
    metrics = metrics_data.get("test", {}) if isinstance(metrics_data, dict) else {}
    try:
        quality_passed = (
            float(metrics["average_precision"]) >= 0.50
            and float(metrics["brier_score"]) <= 0.20
            and float(metrics["recall_at_threshold"]) >= 0.80
        )
    except (KeyError, TypeError, ValueError):
        quality_passed = False
    if not quality_passed:
        return "Flood bundle did not pass the held-out chronological quality gate."
    if metadata.get("deployment_eligible") is not True:
        return "Flood bundle requires explicit deployment approval after validation."
    return None


class FloodModelService:
    def __init__(self, artifact_dir: str | None = None):
        configured = artifact_dir if artifact_dir is not None else settings.flood_model_dir
        self.artifact_dir = Path(configured).expanduser() if configured else None
        self._model = None
        self._preprocessor = None
        self._metadata: dict[str, Any] = {}
        self._calibrator: dict[str, Any] = {}
        self._threshold = 0.5
        self._error: str | None = None

    @property
    def configured(self) -> bool:
        if not self.artifact_dir:
            return False
        return all((self.artifact_dir / filename).is_file() for filename in (
            "model.joblib", "preprocessor.joblib", "metadata.json", "feature_schema.json",
            "calibration.json", "threshold.json"
        ))

    def status(self) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        if self.artifact_dir and (self.artifact_dir / "metadata.json").is_file():
            try:
                metadata = json.loads((self.artifact_dir / "metadata.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        return {
            "configured": self.configured,
            "loaded": self._model is not None,
            "model_version": metadata.get("model_version"),
            "demo_mode": metadata.get("demo_mode"),
            "deployment_allowed": self.configured and _deployment_block_reason(metadata) is None,
            "block_reason": (
                "Flood artifact files are missing or incomplete." if not self.configured
                else _deployment_block_reason(metadata)
            ),
            "error": self._error,
        }

    def _load(self):
        if self._model is not None:
            return self._model, self._preprocessor
        if not self.configured or self.artifact_dir is None:
            raise FloodModelUnavailable("Flood artifact is not configured. Put a verified bundle in FLOOD_MODEL_DIR.")
        try:
            import joblib

            self._metadata = json.loads((self.artifact_dir / "metadata.json").read_text(encoding="utf-8"))
            block_reason = _deployment_block_reason(self._metadata)
            if block_reason:
                raise ValueError(block_reason)
            self._calibrator = json.loads((self.artifact_dir / "calibration.json").read_text(encoding="utf-8"))
            threshold_data = json.loads((self.artifact_dir / "threshold.json").read_text(encoding="utf-8"))
            self._threshold = float(threshold_data["threshold"])
            self._model = joblib.load(self.artifact_dir / "model.joblib")
            self._preprocessor = joblib.load(self.artifact_dir / "preprocessor.joblib")
            return self._model, self._preprocessor
        except Exception as error:
            self._error = f"{type(error).__name__}: {error}"
            raise FloodModelUnavailable("Unable to load the local flood-model artifact.") from error

    def predict(self, samples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        model, preprocessor = self._load()
        import numpy as np
        import pandas as pd

        frame = pd.DataFrame(samples)
        frame["decision_time"] = pd.to_datetime(frame["decision_time"], errors="coerce", utc=True)
        if frame["decision_time"].isna().any():
            raise ValueError("One or more decision_time values could not be parsed.")
        hour = frame["decision_time"].dt.hour + frame["decision_time"].dt.minute / 60
        month = frame["decision_time"].dt.month
        frame["hour_sin"] = np.sin(2 * np.pi * hour / 24)
        frame["hour_cos"] = np.cos(2 * np.pi * hour / 24)
        frame["month_sin"] = np.sin(2 * np.pi * (month - 1) / 12)
        frame["month_cos"] = np.cos(2 * np.pi * (month - 1) / 12)
        frame["is_weekend"] = (frame["decision_time"].dt.dayofweek >= 5).astype(int)
        schema_path = self.artifact_dir / "feature_schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8")) if schema_path.is_file() else {}
        numeric = schema.get("numeric_features", [])
        categorical = schema.get("categorical_features", [])
        for column in numeric:
            if column not in frame:
                frame[column] = np.nan
        for column in categorical:
            if column not in frame:
                frame[column] = "unknown"
        transformed = preprocessor.transform(frame[numeric + categorical])
        raw = model.predict_proba(transformed)[:, 1]
        probability = self._apply_calibrator(self._calibrator, raw)
        version = self._metadata.get("model_version", "unknown")
        results = []
        for sample, score in zip(samples, probability, strict=True):
            coverage = sample.get("coverage_ratio")
            state = "unknown" if coverage is None else (
                "predicted_high_risk" if score >= self._threshold else "predicted_lower_risk"
            )
            results.append({
                "edge_id": sample["edge_id"],
                "decision_time": sample["decision_time"],
                "horizon_min": sample["horizon_min"],
                "probability": float(score),
                "risk_state": state,
                "coverage_ratio": coverage,
                "model_version": version,
                "is_verified_observation": False,
            })
        return results, self.status()

    @staticmethod
    def _apply_calibrator(calibrator: dict[str, Any], raw_probability):
        import numpy as np

        raw = np.asarray(raw_probability, dtype=float)
        if calibrator.get("method") == "isotonic":
            x = np.asarray(calibrator["x_thresholds"], dtype=float)
            y = np.asarray(calibrator["y_thresholds"], dtype=float)
            return np.interp(raw, x, y, left=y[0], right=y[-1])
        if calibrator.get("method") == "sigmoid":
            clipped = np.clip(raw, 1e-6, 1 - 1e-6)
            logit = np.log(clipped / (1 - clipped))
            score = float(calibrator["coef"]) * logit + float(calibrator["intercept"])
            return 1 / (1 + np.exp(-score))
        raise ValueError("Unknown calibration method in flood artifact.")


flood_model_service = FloodModelService()
