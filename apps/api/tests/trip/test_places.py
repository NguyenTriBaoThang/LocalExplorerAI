from app.models.trip_entities import TripPlace
from app.services.trip import places

none_embed = lambda t: None


def test_search_filters_kind_and_tags(db_session, trip_places):
    trip_places["an-pho"].tags = ["an-dia-phuong", "gia-re"]
    trip_places["an-com"].tags = ["an-dia-phuong"]
    trip_places["an-toi"].tags = ["an-dia-phuong", "dem"]
    db_session.commit()
    found = places.search_places(db_session, "tp-hcm", "ăn", none_embed, kind="an-uong",
                                 required_tags=["an-dia-phuong"], avoided_tags=["dem"])
    assert {p.ext_id for p in found} == {"an-pho", "an-com"}
    assert all(p.kind == "an-uong" for p in found)
    assert places.search_places(db_session, "tp-hcm", "ăn", none_embed, kind="an-uong", limit=1).__len__() == 1
    assert places.search_places(db_session, "ha-noi", "ăn", none_embed) == []


def test_search_ranks_by_embedding(db_session, trip_places):
    trip_places["cf-1"].embedding = [1.0, 0.0]
    trip_places["cf-2"].embedding = [0.0, 1.0]
    db_session.commit()
    found = places.search_places(db_session, "tp-hcm", "q", lambda t: [[0.1, 0.9]] * len(t), kind="cafe")
    assert [p.ext_id for p in found] == ["cf-2", "cf-1"]


def test_search_falls_back_to_keywords(db_session, trip_places):
    found = places.search_places(db_session, "tp-hcm", "phở bò", none_embed)
    assert found[0].ext_id == "an-pho"
    assert all(isinstance(p, TripPlace) for p in found)


def test_unmapped_tags_still_searchable(db_session, trip_places):
    trip_places["cf-1"].raw_tags = ["speakeasy"]
    db_session.commit()
    found = places.search_places(db_session, "tp-hcm", "speakeasy", none_embed)
    assert found[0].ext_id == "cf-1"


def test_similar_places_by_embedding_and_fallback(db_session, trip_places):
    cf1, cf2 = trip_places["cf-1"], trip_places["cf-2"]
    assert [p.ext_id for p in places.similar_places(db_session, cf1.id, "cafe")] == ["cf-2"]
    cf1.embedding, cf2.embedding = [1.0, 0.0], [0.9, 0.1]
    db_session.commit()
    assert [p.ext_id for p in places.similar_places(db_session, cf1.id, "cafe", exclude_ids=[cf2.id])] == []
    assert [p.ext_id for p in places.similar_places(db_session, cf1.id, "cafe")] == ["cf-2"]


def test_get_places_and_destinations(db_session, trip_places):
    got = places.get_places(db_session, [trip_places["cf-1"].id])
    assert got[trip_places["cf-1"].id].name == "Cà Phê Chung Cư"
    assert places.list_destinations(db_session)[0]["slug"] == "tp-hcm"
