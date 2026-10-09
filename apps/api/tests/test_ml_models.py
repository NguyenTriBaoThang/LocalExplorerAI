import hashlib
import io
import json
from types import SimpleNamespace

from app.services.ranker_features import build_feature_row, is_hard_feasible
from app.services.ml_ranker_service import MLRankerService


def test_ranker_features_use_csv_contract_and_preserve_missing_weather():
    query = {
        "user_intent_tags": "thủ_công; workshop; indoor",
        "remaining_time_min": 180,
        "group_size": 2,
        "budget_remaining_vnd": 800_000,
    }
    candidate = {
        "candidate_tags": "Thủ công thực hành; indoor",
        "duration_min": 75,
        "price_vnd_per_person": 280_000,
        "is_hands_on": True,
        "is_indoor": True,
        "eta_min": 25,
    }
    features = build_feature_row(query, candidate)
    assert features["tag_jaccard"] > 0
    assert features["intent_match"] == 1
    assert features["total_time_ratio"] == 100 / 180
    assert features["group_cost_ratio"] == 560_000 / 800_000
    assert features["rain_mm"] != features["rain_mm"]  # NaN means unknown, not dry.
    assert is_hard_feasible(query, candidate)


def test_ranker_features_reject_over_budget_or_over_time_candidate():
    query = {"remaining_time_min": 90, "group_size": 2, "budget_remaining_vnd": 100_000}
    candidate = {"duration_min": 60, "eta_min": 40, "price_vnd_per_person": 100_000}
    assert not is_hard_feasible(query, candidate)


def test_model_routes_use_rule_baseline_when_ml_artifacts_are_missing(client, monkeypatch):
    from app.services.ml_ranker_service import ranker_service

    monkeypatch.setattr(ranker_service, "artifact_dir", None)
    monkeypatch.setattr(ranker_service, "_model", None)
    monkeypatch.setattr(ranker_service, "_error", None)
    monkeypatch.setattr(ranker_service, "_load_failed", False)
    status = client.get("/api/ml/status")
    assert status.status_code == 200
    assert status.json()["experience_ranker"]["configured"] is False
    assert status.json()["experience_ranker"]["active_ranker"] == "rule_baseline"
    assert status.json()["experience_ranker"]["fallback_active"] is True
    assert status.json()["flood_risk_model"]["configured"] is False

    ranking = client.post("/api/ml/rank-experiences", json={
        "query": {
            "user_intent_text": "workshop thủ công indoor",
            "user_intent_tags": ["thủ_công", "indoor"],
            "remaining_time_min": 180,
            "group_size": 2,
            "budget_remaining_vnd": 800000,
        },
        "candidates": [{
            "candidate_experience_id": "candidate-1",
            "candidate_name": "Tranh trúc chỉ",
            "candidate_tags": ["Thủ công thực hành", "indoor"],
            "duration_min": 75,
            "price_vnd_per_person": 280000,
            "is_hands_on": True,
            "is_indoor": True,
            "eta_min": 25,
            "hard_feasible": True,
        }],
    })
    assert ranking.status_code == 200, ranking.text
    assert ranking.json()["ranking_source"] == "rule_baseline"
    assert ranking.json()["model_version"] == "rule-baseline-v1"
    assert [row["candidate_experience_id"] for row in ranking.json()["ranked_candidates"]] == ["candidate-1"]

    flood = client.post("/api/ml/flood-risk", json={"samples": [{
        "edge_id": "edge-1",
        "decision_time": "2026-10-02T10:00:00+07:00",
        "horizon_min": 30,
    }]})
    assert flood.status_code == 503
    assert flood.json()["error"]["code"] == "FLOOD_MODEL_NOT_READY"


def test_ranker_baseline_orders_intent_matches_and_filters_infeasible():
    service = MLRankerService(__file__)
    query = {
        "user_intent_text": "handicraft",
        "user_intent_tags": ["handicraft"],
        "remaining_time_min": 180,
        "group_size": 2,
        "budget_remaining_vnd": 800_000,
    }
    candidates = [
        {
            "candidate_experience_id": "culture",
            "candidate_name": "Museum",
            "candidate_tags": ["culture"],
            "duration_min": 60,
            "price_vnd_per_person": 50_000,
            "is_hands_on": False,
            "is_indoor": True,
            "eta_min": 15,
        },
        {
            "candidate_experience_id": "craft",
            "candidate_name": "Workshop",
            "candidate_tags": ["handicraft"],
            "duration_min": 75,
            "price_vnd_per_person": 100_000,
            "is_hands_on": True,
            "is_indoor": True,
            "eta_min": 20,
        },
        {
            "candidate_experience_id": "infeasible",
            "candidate_name": "Over budget workshop",
            "candidate_tags": ["handicraft"],
            "duration_min": 75,
            "price_vnd_per_person": 500_000,
            "is_hands_on": True,
            "is_indoor": True,
            "eta_min": 20,
        },
    ]

    ranked, filtered, status = service.rank(query, candidates)

    assert [candidate["candidate_experience_id"] for candidate in ranked] == ["craft", "culture"]
    assert filtered == ["infeasible"]
    assert status["ranking_source"] == "rule_baseline"
    assert status["model_version"] == "rule-baseline-v1"


def test_ranker_status_rejects_corrupt_model_checksum():
    metadata = {
        "model_version": "test-human-model",
        "model_family": "xgboost",
        "model_file": "ranker.json",
        "model_sha256": "0" * 64,
        "feature_version": "ranker-features-v2",
        "feature_names": [
            "tag_jaccard", "intent_match", "is_hands_on", "is_indoor", "duration_ratio",
            "eta_ratio", "total_time_ratio", "group_cost_ratio", "rain_mm", "outdoor_rain_mm",
            "temperature_c", "pm2_5", "european_aqi", "is_hands_on_known", "is_indoor_known",
        ],
        "dataset_status": "verified_human_labeled",
        "deployment_eligible": True,
    }
    model_bytes = b"not-a-valid-model"

    class FakeArtifact:
        def is_file(self):
            return True

        def resolve(self):
            return self

        def __str__(self):
            return "ranker.json"

        def stat(self):
            return SimpleNamespace(st_mtime_ns=1, st_size=len(model_bytes))

        def open(self, _mode):
            return io.BytesIO(model_bytes)

    class FakeRankerService(MLRankerService):
        def __init__(self):
            super().__init__(artifact_dir=None)

        @property
        def configured(self):
            return self._integrity_error(metadata) is None

        def _read_metadata(self):
            return metadata

        def _artifact_path(self, _metadata):
            return FakeArtifact()

    status = FakeRankerService().status()
    assert status["configured"] is False
    assert status["deployment_allowed"] is False
    assert "SHA-256 does not match" in status["artifact_integrity_error"]
    assert hashlib.sha256(model_bytes).hexdigest() != metadata["model_sha256"]
