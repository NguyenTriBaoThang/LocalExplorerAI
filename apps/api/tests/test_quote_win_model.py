import json
import shutil

import pytest

from app.services.quote import win_model
from app.services.quote.win_model import FEATURE_NAMES, WinModel, build_features, predict_p_win

CTX = {"pax": 25, "days": 1, "lead_days": 30, "segment": "school", "destination": "cu_chi", "weekend": 0, "holiday": 0,
       "tet": 0, "month": 6, "competitor_price_index": 1.0, "rain_prob": 0.7, "response_time_h": 3.0}


def p_at(model, price_pp):
    return model.predict(build_features(CTX, 25 * 1_000_000, price_pp))["p_win"]


def test_missing_bundle_falls_back_to_monotone_heuristic(tmp_path):
    m = WinModel(tmp_path / "nope")
    assert m.source == "heuristic" and m.error
    ps = [p_at(m, p) for p in (1_100_000, 1_300_000, 1_600_000)]
    assert ps[0] > ps[1] > ps[2] and all(0 < p < 1 for p in ps)
    assert predict_p_win(build_features(CTX, 25_000_000, 1_250_000), m)["source"] == "heuristic"


def test_bundle_predicts_monotone_in_price_and_accepts_list():
    pytest.importorskip("xgboost")
    m = WinModel()
    assert m.source == "model", m.error
    assert m.metadata["dataset_status"] == "synthetic" and m.metadata["deployment_eligible"] is False
    ps = [p_at(m, 1_000_000 * r / 100) for r in range(105, 181, 5)]
    assert all(a >= b for a, b in zip(ps, ps[1:])) and ps[0] > ps[-1]
    row = build_features(CTX, 25_000_000, 1_250_000)
    assert m.predict([row[n] for n in FEATURE_NAMES])["p_win"] == m.predict(row)["p_win"]


def test_hash_mismatch_is_rejected(tmp_path):
    shutil.copytree(win_model.DEFAULT_DIR, tmp_path / "b")
    f = tmp_path / "b" / "xgboost_win.json"
    f.write_bytes(f.read_bytes() + b" ")
    m = WinModel(tmp_path / "b")
    assert m.source == "heuristic" and "SHA-256" in m.error


def test_feature_list_mismatch_is_rejected(tmp_path):
    shutil.copytree(win_model.DEFAULT_DIR, tmp_path / "b")
    meta = tmp_path / "b" / "model_metadata.json"
    d = json.loads(meta.read_text())
    d["feature_names"] = d["feature_names"][:-1]
    meta.write_text(json.dumps(d))
    assert "feature" in WinModel(tmp_path / "b").error
