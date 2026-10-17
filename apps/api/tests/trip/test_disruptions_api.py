"""Sự cố → phương án → áp dụng (port of Travility test_disruptions_api; the FOR UPDATE race test needs Postgres)."""
import pytest

from app.models.trip_entities import Trip as TripRow, TripItinerary, TripMessage, TripPlace, TripProposal
from app.services.trip import store
from app.services.trip.agent import itinerary_event
from app.services.trip.domain import WEEKDAYS, Draft, Trip
from app.services.trip.places import get_places
from app.services.trip.rules import build_itinerary
from tests.helpers import bearer_for, make_user
from tests.trip.test_trips_api import no_meal_rule, offline  # noqa: F401 (autouse fixtures)

TRIP = Trip(destination="tp-hcm", days=1, budget=5_000_000, travel_mode="grab", preferred_tags=["cafe-chill"])


def add_place(db, ext_id, name, kind="cafe", tags=(), outdoor=False):
    p = TripPlace(ext_id=ext_id, destination="tp-hcm", name=name, kind=kind, lat=10.7745, lon=106.6990, price=0,
                  open_hours={d: ["06:00", "22:00"] for d in WEEKDAYS}, outdoor=outdoor, tags=list(tags),
                  raw_tags=[], description="", address="")
    db.add(p)
    db.commit()
    return p.id


def seed(db, trip_places, pinned=False):
    """Trip 1 ngày: Cà Phê Chung Cư 09:00 → Dinh Độc Lập 11:00. Ứng viên: cafe B (cùng mục đích), cafe C."""
    trip_places["cf-1"].tags = ["cafe-chill"]
    trip_places["tq-dinh"].tags = ["lich-su"]
    add_place(db, "cf-b", "Cafe B", tags=["cafe-chill"])
    add_place(db, "cf-c", "Cafe C", tags=["check-in"])
    user = make_user(db, "traveler")
    row = TripRow(user_id=user.id, spec=TRIP.model_dump(mode="json"), user_messages=[])
    db.add(row)
    db.commit()
    cafe, museum = trip_places["cf-1"].id, trip_places["tq-dinh"].id
    places = get_places(db, [cafe, museum])
    draft = Draft.model_validate({"summary": "", "days": [{"stops": [
        {"place_id": cafe, "start_time": "09:00", "duration_min": 60},
        {"place_id": museum, "start_time": "11:00", "duration_min": 60}]}]})
    ev = itinerary_event(build_itinerary(TRIP, draft, places), places)
    store.save_itinerary(db, row.id, ev["itinerary"], ev["places"])
    if pinned:
        row.pinned_place_ids = [cafe]
        db.commit()
    return bearer_for(user), row.id


def disrupt(client, h, tid, version=1, stop=0, kind="closed"):
    return client.post(f"/api/trips/{tid}/disruptions", headers=h,
                       json={"version": version, "kind": kind, "day_index": 0, "stop_index": stop})


def apply(client, h, tid, pid, option=0):
    return client.post(f"/api/trips/{tid}/proposals/{pid}/apply", headers=h, json={"option": option})


def first_stop_name(opt):
    return opt["places"][str(opt["itinerary"]["days"][0]["stops"][0]["place_id"])]["name"]


def test_closed_returns_options_and_logs(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    r = disrupt(client, h, tid)
    assert r.status_code == 200
    body = r.json()
    names = [first_stop_name(o) for o in body["options"]]  # the fixture's own cafe cf-2 is a third candidate
    assert names[0] == "Cafe B" and sorted(names) == ["Cafe B", "Cafe C", "The Workshop"]
    assert body["options"][0]["reason_codes"][0] == "INTENT_MATCH"
    row = db_session.get(TripProposal, body["proposal_id"])
    assert (row.base_version, row.disruption["kind"], row.chosen_index) == (1, "closed", None)


def test_apply_is_idempotent(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    first, again = apply(client, h, tid, pid).json(), apply(client, h, tid, pid).json()
    assert first["version"] == again["version"] == 2
    assert first["type"] == "itinerary" and first_stop_name(first) == "Cafe B"
    assert db_session.query(TripItinerary).filter_by(trip_id=tid).count() == 2
    assert db_session.get(TripProposal, pid).chosen_index == 0


def test_apply_other_option_after_applied_409(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    apply(client, h, tid, pid)
    assert apply(client, h, tid, pid, 1).status_code == 409


def test_apply_unknown_option_or_proposal(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    assert apply(client, h, tid, pid, 9).status_code == 422
    assert apply(client, h, tid, 999).status_code == 404


def test_stale_version_409(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    old = disrupt(client, h, tid).json()["proposal_id"]
    pid = disrupt(client, h, tid).json()["proposal_id"]
    apply(client, h, tid, pid)  # → version 2
    r = disrupt(client, h, tid, version=1)
    assert r.status_code == 409 and r.json()["error"]["message"] == "Lịch trình đã có bản mới hơn, hãy mở bản mới nhất rồi thử lại."
    assert apply(client, h, tid, old).status_code == 409


def test_other_user_404(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    other = bearer_for(make_user(db_session, "traveler"))
    assert disrupt(client, other, tid).status_code == 404
    assert apply(client, other, tid, pid).status_code == 404


def test_pinned_or_bad_stop_422(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places, pinned=True)
    assert disrupt(client, h, tid).status_code == 422
    assert disrupt(client, h, tid, stop=9).status_code == 422


def test_no_feasible_when_no_same_kind_place(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    db_session.delete(trip_places["tq-cong-vien"])
    db_session.commit()
    body = disrupt(client, h, tid, stop=1).json()  # Dinh Độc Lập: không có tham-quan nào khác
    assert body["no_feasible"] == ["NO_CANDIDATE"]
    assert "options" not in body


def test_apply_logs_message(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    apply(client, h, tid, pid)
    apply(client, h, tid, pid)  # idempotent: không ghi lần 2
    rows = db_session.query(TripMessage).filter_by(trip_id=tid).all()
    assert [(r.role, r.version) for r in rows] == [("ai", 2)]
    assert "bản 2" in rows[0].text


def test_apply_old_proposal_after_restore_is_409(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    pid = disrupt(client, h, tid).json()["proposal_id"]
    assert client.post(f"/api/trips/{tid}/restore/1", headers=h).json()["version"] == 2
    assert apply(client, h, tid, pid).status_code == 409


def test_apply_after_pinning_the_replaced_stop_is_409(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    pid = disrupt(client, h, tid).json()["proposal_id"]  # Proposal thay Cà Phê Chung Cư
    cafe = trip_places["cf-1"].id
    assert client.patch(f"/api/trips/{tid}/pins", headers=h, json={"place_id": cafe, "pinned": True}).status_code == 200
    r = apply(client, h, tid, pid)
    assert r.status_code == 409 and "ghim" in r.json()["error"]["message"]
    assert db_session.query(TripItinerary).filter_by(trip_id=tid).count() == 1


def test_options_carry_title_and_added(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    o = disrupt(client, h, tid).json()["options"][0]
    assert o["title"] == "Cafe B"
    assert [o["places"][str(i)]["name"] for i in o["added"]] == ["Cafe B"]


def post(client, h, tid, **body):
    return client.post(f"/api/trips/{tid}/disruptions", headers=h, json={"version": 1, "day_index": 0, **body})


def test_rain_round_trip_creates_version(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    trip_places["tq-dinh"].outdoor = True
    db_session.commit()
    body = post(client, h, tid, kind="rain").json()
    assert [o["title"] for o in body["options"]] == ["Bỏ Dinh Độc Lập"]  # chỉ còn Tao Đàn, ngoài trời
    r = apply(client, h, tid, body["proposal_id"])
    assert r.status_code == 200 and r.json()["version"] == 2
    assert [s["place_id"] for s in r.json()["itinerary"]["days"][0]["stops"]] == [trip_places["cf-1"].id]


def test_rain_swaps_in_indoor_tham_quan(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    trip_places["tq-dinh"].outdoor = True
    indoor = add_place(db_session, "tq-bt", "Bảo tàng Chiến tranh", kind="tham-quan", tags=["lich-su"])
    body = post(client, h, tid, kind="rain").json()
    assert body["options"][0]["title"] == "Bảo tàng Chiến tranh" and body["options"][0]["added"] == [indoor]
    assert "INDOOR_FOR_RAIN" in body["options"][0]["reason_codes"]


def test_late_shift_only(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    o = post(client, h, tid, kind="late", stop_index=0, minutes=30).json()["options"][0]
    assert o["reason_codes"] == ["LATE_SHIFT"]
    assert [s["start_time"] for s in o["itinerary"]["days"][0]["stops"]] == ["09:30", "11:30"]


def test_bad_rain_or_late_shape_422(client, db_session, trip_places):
    h, tid = seed(db_session, trip_places)
    assert post(client, h, tid, kind="rain", stop_index=0).status_code == 422
    assert post(client, h, tid, kind="late", stop_index=0).status_code == 422
    assert post(client, h, tid, kind="late", stop_index=0, minutes=300).status_code == 422
    assert post(client, h, tid, kind="rain", day_index=5).status_code == 422
