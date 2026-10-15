import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "apps" / "api" / "scripts"))

from crawl_district1_places import normalize_elements  # noqa: E402
from import_place_candidates import candidate_flags, read_json_places  # noqa: E402


def test_osm_crawler_keeps_only_named_places_inside_pilot_and_does_not_invent_fields():
    elements = [
        {
            "type": "node", "id": 101, "lat": 10.775, "lon": 106.700,
            "version": 4, "timestamp": "2026-10-01T10:00:00Z",
            "tags": {
                "name": "Public Museum", "tourism": "museum",
                "opening_hours": "Mo-Su 08:00-17:00", "phone": "+84 28 1234 5678",
            },
        },
        {
            "type": "way", "id": 202, "center": {"lat": 10.7755, "lon": 106.7005},
            "tags": {"name": "Coffee place", "amenity": "cafe", "addr:street": "Example Street"},
        },
        {
            "type": "node", "id": 303, "lat": 10.800, "lon": 106.700,
            "tags": {"name": "Outside pilot", "tourism": "museum"},
        },
        {"type": "node", "id": 404, "lat": 10.775, "lon": 106.700, "tags": {"tourism": "museum"}},
    ]

    places = normalize_elements(elements)

    assert [place["ext_id"] for place in places] == ["node/101", "way/202"]
    assert places[0]["open_hours"] == "Mo-Su 08:00-17:00"
    assert places[0]["details"]["contact_phone"] == "+84 28 1234 5678"
    assert places[0]["details"]["osm_timestamp"] == "2026-10-01T10:00:00Z"
    assert places[0]["price_vnd"] is None
    assert places[0]["verified"] is False
    assert places[0]["photo_url"] is None
    assert places[0]["source"] == "https://www.openstreetmap.org/node/101"
    assert places[1]["address"] == "Example Street"


def test_crawled_json_is_importable_as_unverified_source_candidates(monkeypatch):
    path = Path("district1-test-fixture.json")
    document = (
        '{"metadata":{"source":"OpenStreetMap"},"places":[{"ext_id":"node/1",'
        '"name":"Museum","kind":"tourism:museum","lat":10.775,"lon":106.7,'
        '"address":"1 Example Road","open_hours":"Mo-Su 08:00-17:00",'
        '"price_vnd":null,"photo_url":"https://upload.wikimedia.org/example.jpg",'
        '"source":"https://www.openstreetmap.org/node/1","verified":false,'
        '"tags":{"name":"Museum","tourism":"museum"}}]}'
    )
    original_read_text = Path.read_text

    def read_fixture(self, *args, **kwargs):
        if self == path:
            return document
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", read_fixture)
    records, row_count = read_json_places(path)

    assert row_count == 1
    assert records[0][0]["ext_id"] == "node/1"
    assert records[0][0]["tags"] == ["name=Museum", "tourism=museum"]
    assert records[0][0]["verified"] is False
    assert "photo_missing" not in candidate_flags(records[0][0], set())
