import json
from pathlib import Path

import pytest
from sqlalchemy import select, func

from app.models.entities import POI, Provider, ExperienceSlot
from app.models.trip_entities import TripPlace
from scripts.portable_catalog import import_catalog


def catalog():
    return json.loads((Path(__file__).resolve().parents[3] / "data/portable/catalog.json").read_text(encoding="utf-8"))


def test_snapshot_import_is_idempotent_and_not_bookable(db_session):
    engine = db_session.get_bind()
    data = catalog()
    counts = import_catalog(engine, data)
    assert counts["pois"] == 202
    assert counts["trip_places"] == 177
    assert not any(import_catalog(engine, data).values())
    assert db_session.scalar(select(func.count()).select_from(POI)) == 202
    assert db_session.scalar(select(func.count()).select_from(TripPlace)) == 177
    assert all(not p.is_active and p.portal_access_key is None for p in db_session.scalars(select(Provider)))
    assert all(s.status == "tentative" and s.available_reported == 0 and s.confirmed_at is None
               for s in db_session.scalars(select(ExperienceSlot)))


def test_unexpected_fields_roll_back_entire_import(db_session):
    data = catalog()
    data["tables"]["pois"][0]["submitted_by_provider_id"] = "not-allowed"
    with pytest.raises(ValueError, match="Unexpected fields"):
        import_catalog(db_session.get_bind(), data)
    assert db_session.scalar(select(func.count()).select_from(Provider)) == 0
