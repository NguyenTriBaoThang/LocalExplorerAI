import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.models.trip_entities import TripDestination, TripPlace
from scripts.import_trip_places import convert, import_file

REPO = Path(__file__).resolve().parents[4]


def raw(**over):
    base = {"id": "x", "name": "X", "kind": "an-uong", "lat": 10.77, "lon": 106.7, "price_vnd": 50_000,
            "open_hours": '{"open":"08:00","close":"17:00","days":"T2-CN"}', "outdoor": False,
            "tags": [], "description": "Mô tả.", "address": "Q1"}
    return {**base, **over}


def test_open_hours_conversion():
    hours = lambda days: convert(raw(open_hours=json.dumps({"open": "20:30", "close": "01:30", "days": days})))["open_hours"]
    night = ["20:30", "01:30"]
    assert hours("T4,T6,T7") == {"mon": None, "tue": None, "wed": night, "thu": None, "fri": night, "sat": night, "sun": None}
    h = hours("T3-CN")
    assert h["mon"] is None and all(h[d] == night for d in ("tue", "wed", "thu", "fri", "sat", "sun"))
    with pytest.raises(ValueError, match="x"):
        hours("abc")


def test_tags_are_normalised():
    out = convert(raw(tags=["chay", "rooftop", "kien-truc-phap"]))
    assert out["tags"] == ["an-chay", "view-dep"]
    assert out["raw_tags"] == ["chay", "rooftop", "kien-truc-phap"]


def test_import_upserts_by_ext_id(db_session, tmp_path):
    path = tmp_path / "p.json"
    embed = lambda t: [[1.0] + [0.0] * 767] * len(t)
    path.write_text(json.dumps([raw(id="a"), raw(id="b")]), encoding="utf-8")
    assert import_file(db_session, path, embed) == 2
    dest = db_session.get(TripDestination, "tp-hcm")
    assert set(dest.hubs) == {"may-bay", "tau", "xe-khach"}
    path.write_text(json.dumps([raw(id="a", price_vnd=99_000), raw(id="b")]), encoding="utf-8")
    import_file(db_session, path, embed)
    rows = {p.ext_id: p for p in db_session.scalars(select(TripPlace))}
    assert len(rows) == 2 and rows["a"].price == 99_000 and len(rows["a"].embedding) == 768


def test_real_dataset_imports(db_session):
    assert import_file(db_session, REPO / "data" / "sai_gon_places.json", lambda t: None) == 177
    assert db_session.scalar(select(TripPlace).where(TripPlace.embedding.is_not(None)).limit(1)) is None
