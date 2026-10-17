import json

import pytest

from app.places import list_destinations
from scripts.import_places import expand_hours, import_file
from tests.helpers import unit_vec


def fake_embed(texts):
    return [unit_vec(0) for _ in texts]


def write(tmp_path, places, hubs=None):
    p = tmp_path / "x.json"
    dest = {"slug": "da-lat", "name": "Đà Lạt", "lat": 11.94, "lon": 108.44}
    if hubs is not None:
        dest["hubs"] = hubs
    p.write_text(json.dumps({"destination": dest, "places": places}), encoding="utf-8")
    return p


PLACE = {"ext_id": "a", "name": "Hồ Xuân Hương", "kind": "tham-quan", "lat": 11.94, "lon": 108.44,
         "price": 0, "open_hours": {"daily": ["00:00", "24:00"]}, "outdoor": True,
         "tags": ["thien-nhien"], "description": "Hồ trung tâm"}


def test_import_is_idempotent(conn, tmp_path):
    assert import_file(conn, write(tmp_path, [PLACE]), fake_embed) == 1
    import_file(conn, write(tmp_path, [{**PLACE, "name": "Hồ Xuân Hương (mới)"}]), fake_embed)
    rows = conn.execute("SELECT name FROM places").fetchall()
    assert [r["name"] for r in rows] == ["Hồ Xuân Hương (mới)"]


def test_import_rejects_unknown_tag(conn, tmp_path):
    with pytest.raises(ValueError, match="tag lạ"):
        import_file(conn, write(tmp_path, [{**PLACE, "tags": ["bay-lac"]}]), fake_embed)


def test_import_saves_hubs(conn, tmp_path):
    hubs = {"may-bay": {"name": "Sân bay Liên Khương", "lat": 11.75, "lon": 108.37}}
    import_file(conn, write(tmp_path, [PLACE], hubs), fake_embed)
    assert list_destinations(conn)[0]["hubs"] == hubs


def test_destination_without_hubs_gets_empty(conn, tmp_path):
    import_file(conn, write(tmp_path, [PLACE]), fake_embed)
    assert list_destinations(conn)[0]["hubs"] == {}


def test_import_rejects_unknown_hub(conn, tmp_path):
    with pytest.raises(ValueError, match="hub lạ"):
        import_file(conn, write(tmp_path, [PLACE], {"tau-ngam": {"name": "x", "lat": 1, "lon": 1}}), fake_embed)


def test_expand_daily_hours():
    assert expand_hours({"daily": ["07:00", "22:00"]})["sun"] == ["07:00", "22:00"]
    assert expand_hours({"daily": ["07:00", "22:00"], "mon": None})["mon"] is None
