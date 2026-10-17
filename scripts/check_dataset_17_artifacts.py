"""Smoke-check offline DATA_ngay17 artifacts and the production API gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import joblib
import lightgbm as lgb
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "scripts"))

import train_dataset_17_experiments as trainer  # noqa: E402
from app.services.flood_model_service import FloodModelService, FloodModelUnavailable  # noqa: E402
from app.services.ml_ranker_service import MLRankerService  # noqa: E402


def check(artifact_dir: Path) -> dict:
    ranker_dir = artifact_dir / "ranker"
    flood_dir = artifact_dir / "flood-risk"
    if not (ranker_dir / "ranker_model.pkl").is_file():
        raise FileNotFoundError("Missing ranker/ranker_model.pkl; run the training script first.")
    if not (flood_dir / "flood_model.pkl").is_file():
        raise FileNotFoundError("Missing flood-risk/flood_model.pkl; run the training script first.")

    dataset_dir = ROOT / "data" / "dataset"
    ranker_rows = trainer._ranker_source_rows(dataset_dir)
    ranker_features, _ = trainer._ranker_feature_frame(ranker_rows)
    ranker_model = joblib.load(ranker_dir / "ranker_model.pkl")
    ranker_scores = np.asarray(ranker_model.predict(ranker_features.iloc[:8]), dtype=float)
    assert ranker_scores.shape == (min(8, len(ranker_features)),)
    assert np.isfinite(ranker_scores).all()

    # The native text model is the format consumed by the API's LightGBM path.
    native_model = lgb.Booster(model_file=str(ranker_dir / "ranker_model.txt"))
    assert native_model.num_feature() == len(trainer.FEATURE_NAMES)

    flood_data, _ = trainer._flood_training_data(dataset_dir)
    flood_model = joblib.load(flood_dir / "flood_model.pkl")
    preprocessor = joblib.load(flood_dir / "preprocessor.joblib")
    flood_x = preprocessor.transform(flood_data[trainer.FLOOD_FEATURES].iloc[:8])
    flood_scores = np.asarray(flood_model.predict_proba(flood_x)[:, 1], dtype=float)
    assert flood_scores.shape == (min(8, len(flood_data)),)
    assert np.isfinite(flood_scores).all()
    assert ((flood_scores >= 0) & (flood_scores <= 1)).all()

    ranker_service = MLRankerService(str(ranker_dir.resolve()))
    ranker_status = ranker_service.status()
    assert ranker_status["configured"] is True, ranker_status
    assert ranker_status["deployment_allowed"] is False, ranker_status
    assert ranker_status["pilot_runtime_eligible"] is False, ranker_status
    ranked, rejected, rank_result = ranker_service.rank(
        {"user_intent_tags": "coffee"},
        [{"candidate_experience_id": "smoke-test", "candidate_tags": "specialty_coffee"}],
    )
    assert not rejected and ranked
    assert rank_result["ranking_source"] == "rule_baseline", rank_result

    flood_service = FloodModelService(str(flood_dir.resolve()))
    flood_status = flood_service.status()
    assert flood_status["configured"] is True, flood_status
    assert flood_status["deployment_allowed"] is False, flood_status
    assert "demo/simulated" in str(flood_status["block_reason"]), flood_status
    try:
        flood_service.predict([{
            "edge_id": "smoke-test",
            "decision_time": "2026-10-17T12:00:00Z",
            "horizon_min": 60,
            "coverage_ratio": None,
        }])
    except FloodModelUnavailable:
        pass
    else:
        raise AssertionError("The Flood API loaded a demo artifact instead of blocking it.")

    return {
        "ranker_pkl_prediction_rows": int(len(ranker_scores)),
        "ranker_api_active_source": rank_result["ranking_source"],
        "ranker_api_deployment_allowed": ranker_status["deployment_allowed"],
        "flood_pkl_prediction_rows": int(len(flood_scores)),
        "flood_api_deployment_allowed": flood_status["deployment_allowed"],
        "flood_api_block_reason": flood_status["block_reason"],
        "result": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=ROOT / "models" / "dataset-17-experiment",
    )
    args = parser.parse_args()
    print(json.dumps(check(args.artifact_dir.resolve()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
