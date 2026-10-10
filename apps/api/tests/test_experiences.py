from geoalchemy2.elements import WKTElement
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.entities import POI, Experience
from scripts.seed_db import seed
from tests.conftest import add_slot


def test_experiences_returns_seed_shape(client, db_session, sample_experience):
    add_slot(db_session, sample_experience)
    response = client.get("/api/experiences")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["name"] == "Paper workshop"
    assert body[0]["poi"]["verification_status"] == "simulated"
    assert body[0]["slots"][0]["available_reported"] == 4
    assert body[0]["slots"][0]["start_at"].endswith("Z") or "+00:00" in body[0]["slots"][0]["start_at"]


def test_seed_populates_simulated_experiences(client, db_session):
    seed(sessionmaker(bind=db_session.get_bind(), expire_on_commit=False))
    response = client.get("/api/experiences")
    assert response.status_code == 200
    items = response.json()
    # The seed has ten city-wide demo records; the public catalog only exposes
    # those whose coordinates fall inside the legacy District 1 pilot boundary.
    assert len(items) == 9
    assert all(item["verification_status"] == "simulated" for item in items)
    assert all(item["slots"] for item in items)
    assert all(item["data_mode"] == "simulated" for item in items)


def test_real_data_only_hides_simulated_catalog(client, db_session, sample_experience, monkeypatch):
    monkeypatch.setattr(settings, "real_data_only", True)

    assert client.get("/api/pois").json() == []
    assert client.get("/api/experiences").json() == []
    assert client.get(f"/api/pois/{sample_experience.poi_id}").status_code == 404


def test_explore_catalog_scopes_to_district_one_and_only_loads_requested_day(client, db_session, sample_experience):
    add_slot(db_session, sample_experience, start="2030-10-01T02:00:00+00:00")
    add_slot(db_session, sample_experience, start="2030-10-02T02:00:00+00:00")

    outside_poi = POI(
        name="Outside pilot area", description="Fixture", district="Quận 10",
        latitude=10.75, longitude=106.63,
        geom=WKTElement("POINT(106.63 10.75)", srid=4326),
        category="culture", address="District 10", verification_status="simulated",
    )
    outside_experience = Experience(
        poi=outside_poi, provider=sample_experience.provider, name="Outside workshop",
        title="Outside workshop", description="Fixture", intent_tags=["handicraft"],
        duration_min=60, price_basis="per_person", price_vnd=100_000,
        verification_status="simulated",
    )
    db_session.add(outside_experience)
    db_session.flush()
    add_slot(db_session, outside_experience, start="2030-10-01T02:00:00+00:00")

    query_count = 0

    def count_query(*_args, **_kwargs):
        nonlocal query_count
        query_count += 1

    engine = db_session.get_bind()
    event.listen(engine, "before_cursor_execute", count_query)
    try:
        response = client.get("/api/experiences", params={
            "start_at": "2030-10-01T02:00:00+00:00",
            "end_at": "2030-10-01T04:00:00+00:00",
            "group_size": 2,
        })
    finally:
        event.remove(engine, "before_cursor_execute", count_query)

    assert response.status_code == 200, response.text
    records = response.json()
    assert [row["id"] for row in records] == [sample_experience.id]
    assert [slot["start_at"] for slot in records[0]["slots"]] == ["2030-10-01T02:00:00Z"]
    assert query_count <= 12, f"date-scoped catalog used {query_count} SQL statements"


def test_explore_catalog_uses_coordinates_not_imported_district_label(client, db_session, sample_experience):
    outside_poi = POI(
        name="Mislabelled Landmark 81", description="Outside legacy District 1", district="Quận 1, TP.HCM",
        latitude=10.7950, longitude=106.7219,
        geom=WKTElement("POINT(106.7219 10.7950)", srid=4326),
        category="culture", address="Bình Thạnh", verification_status="simulated",
    )
    outside_experience = Experience(
        poi=outside_poi, provider=sample_experience.provider, name="Mislabelled experience",
        title="Mislabelled experience", description="Fixture", intent_tags=["culture"],
        duration_min=60, price_basis="per_person", price_vnd=100_000,
        verification_status="simulated",
    )
    db_session.add(outside_experience)
    db_session.commit()

    listed_pois = client.get("/api/pois").json()
    listed_experiences = client.get("/api/experiences").json()
    assert outside_poi.id not in {poi["id"] for poi in listed_pois}
    assert outside_experience.id not in {item["id"] for item in listed_experiences}
    assert client.get(f"/api/pois/{outside_poi.id}").status_code == 404
    assert client.get(f"/api/experiences/{outside_experience.id}").status_code == 404
