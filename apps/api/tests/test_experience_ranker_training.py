from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

from train_experience_ranker import (  # noqa: E402
    DatasetContractError,
    _query_and_candidate,
    build_baseline_scores,
    build_feature_matrix,
    ranking_metrics,
    read_weak_dataset,
    split_by_poi,
    split_by_query_id,
)
from app.services.ranker_features import (  # noqa: E402
    FEATURE_NAMES,
    FEATURE_VERSION,
    LEGACY_FEATURE_NAMES,
    LEGACY_FEATURE_VERSION,
    build_feature_row,
    build_feature_row_v1,
)


DATA = ROOT / "data" / "experimental" / "ranking" / "ranking_candidates_labeled.csv"


def test_weak_dataset_provenance_and_rule_baseline_are_explicit():
    frame = read_weak_dataset(DATA, "weak_label")
    assert len(frame) == 3828
    assert frame["poi_id"].nunique() == 638
    assert frame["query_id"].nunique() == 6
    assert set(frame["label_method"]) == {"category_rule_weak_label"}
    assert not frame["training_eligible"].astype(str).str.lower().eq("true").any()
    assert frame["candidate_slot_id"].fillna("").eq("").all()
    assert frame["hard_feasible"].fillna("").eq("").all()

    metrics = ranking_metrics(frame, build_baseline_scores(frame))
    assert metrics["NDCG@5"] == pytest.approx(1.0)
    assert metrics["NDCG@10"] == pytest.approx(1.0)


def test_weak_split_keeps_every_poi_in_one_partition_and_keeps_six_contexts():
    frame = read_weak_dataset(DATA, "weak_label")
    splits = split_by_poi(frame, seed=42)
    poi_sets = {name: set(frame.iloc[idx]["poi_id"]) for name, idx in splits.items()}
    assert not (poi_sets["train"] & poi_sets["validation"])
    assert not (poi_sets["train"] & poi_sets["test"])
    assert not (poi_sets["validation"] & poi_sets["test"])
    for indices in splits.values():
        assert set(frame.iloc[indices]["query_id"]) == set(frame["query_id"])
    assert {name: len(values) for name, values in poi_sets.items()} == {
        "train": 446,
        "validation": 95,
        "test": 97,
    }


def test_real_feedback_split_keeps_each_query_in_one_partition():
    future_feedback = pd.DataFrame({
        "query_id": [f"real-query-{index // 2:02d}" for index in range(40)],
        "candidate": list(range(40)),
    })
    splits = split_by_query_id(future_feedback, seed=42)
    query_sets = {name: set(future_feedback.iloc[idx]["query_id"]) for name, idx in splits.items()}
    assert not (query_sets["train"] & query_sets["validation"])
    assert not (query_sets["train"] & query_sets["test"])
    assert not (query_sets["validation"] & query_sets["test"])
    assert sum(map(len, query_sets.values())) == 20


def test_training_features_are_exactly_shared_with_api_and_exclude_label_columns():
    frame = read_weak_dataset(DATA, "weak_label").head(20).copy()
    matrix = build_feature_matrix(frame)
    query, candidate = _query_and_candidate(frame.iloc[0].to_dict())
    inference_row = build_feature_row(query, candidate)
    assert list(matrix.columns) == FEATURE_NAMES
    np.testing.assert_allclose(
        matrix.iloc[0].to_numpy(dtype=float),
        np.asarray([inference_row[name] for name in FEATURE_NAMES]),
        equal_nan=True,
    )
    changed = frame.copy()
    changed["relevance_grade"] = 3 - changed["relevance_grade"]
    changed["label_rationale"] = "modified target explanation"
    changed["poi_id"] = "same fake ID"
    changed["candidate_experience_id"] = "same fake experience ID"
    changed["estimated_columns"] = "pretend exact"
    pd_matrix = build_feature_matrix(changed)
    np.testing.assert_allclose(matrix.to_numpy(), pd_matrix.to_numpy(), equal_nan=True)


def test_unknown_operational_flags_remain_missing_and_v1_contract_is_preserved():
    query = {"user_intent_tags": ["handicraft"], "remaining_time_min": 180}
    candidate = {"candidate_tags": ["craft"], "duration_min": 60, "eta_min": 15}
    row = build_feature_row(query, candidate)
    assert np.isnan(row["is_hands_on"])
    assert row["is_hands_on_known"] == 0.0
    assert np.isnan(row["is_indoor"])
    assert row["is_indoor_known"] == 0.0
    assert list(build_feature_row_v1(query, candidate)) == LEGACY_FEATURE_NAMES
    assert LEGACY_FEATURE_VERSION == "ranker-features-v1"


def test_weak_data_cannot_be_silently_promoted_to_verified_mode():
    with pytest.raises(DatasetContractError):
        read_weak_dataset(DATA, "verified_human_labeled")


def test_api_adapter_never_loads_a_weak_label_bundle(tmp_path):
    pytest.importorskip("pydantic_settings")
    from app.services.ml_ranker_service import MLRankerService, MLRankerUnavailable

    metadata = {
        "model_version": "test-weak-bundle",
        "model_family": "xgboost",
        "model_file": "ranker.json",
        "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES,
        "dataset_status": "weak_label_experiment",
        "deployment_eligible": False,
    }
    schema = {"feature_version": FEATURE_VERSION, "feature_names": FEATURE_NAMES}
    (tmp_path / "model_metadata.json").write_text(__import__("json").dumps(metadata), encoding="utf-8")
    (tmp_path / "feature_schema.json").write_text(__import__("json").dumps(schema), encoding="utf-8")
    (tmp_path / "ranker.json").write_text("{}", encoding="utf-8")

    service = MLRankerService(str(tmp_path))
    status = service.status()
    assert status["configured"] is True
    assert status["production_eligible"] is False
    assert status["deployment_allowed"] is False
    assert "never deployable" in status["block_reason"]
    with pytest.raises(MLRankerUnavailable):
        service._load()
