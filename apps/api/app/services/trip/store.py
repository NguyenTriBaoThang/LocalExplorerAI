"""Trip persistence (the SQL half of Travility's trips.py)."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.trip_entities import Trip as TripRow, TripGroupReview, TripItinerary, TripMessage, TripProposal
from app.services.trip.domain import Hub, Itinerary, Trip
from app.services.trip.places import get_places, list_destinations


def trip_row(db: Session, user_id: str, trip_id: int) -> TripRow | None:
    return db.scalar(select(TripRow).where(TripRow.id == trip_id, TripRow.user_id == user_id))


def hub_for(dest: dict, trip: Trip) -> Hub | None:
    h = dest["hubs"].get(trip.arrival_mode) if trip.arrival_mode else None
    return Hub.model_validate(h) if h else None


def save_itinerary(db: Session, trip_id: int, itinerary: dict, places: dict, commit: bool = True) -> int:
    """Lưu một version Itinerary mới (bất biến) và trả số version."""
    # Row lock serialises concurrent saves on Postgres; SQLite ignores FOR UPDATE (it locks the whole file).
    db.execute(select(TripRow.id).where(TripRow.id == trip_id).with_for_update())
    version = (db.scalar(select(func.max(TripItinerary.version)).where(TripItinerary.trip_id == trip_id)) or 0) + 1
    db.add(TripItinerary(trip_id=trip_id, version=version, data={"itinerary": itinerary, "places": places}))
    db.commit() if commit else db.flush()
    return version


def log_message(db: Session, trip_id: int, role: str, text: str, version: int | None = None,
                commit: bool = True) -> None:
    db.add(TripMessage(trip_id=trip_id, role=role, text=text, version=version))
    db.commit() if commit else db.flush()


def load_itinerary(db: Session, trip_id: int, version: int | None = None) -> tuple[int, Itinerary, dict] | None:
    """Đọc một version (mặc định bản mới nhất); stop.pinned lấy từ trips.pinned_place_ids, không từ data đã lưu."""
    stmt = select(TripItinerary).where(TripItinerary.trip_id == trip_id)
    if version is not None:
        stmt = stmt.where(TripItinerary.version == version)
    row = db.scalar(stmt.order_by(TripItinerary.version.desc()).limit(1))
    if not row:
        return None
    itin = Itinerary.model_validate(row.data["itinerary"])
    pins = set(db.get(TripRow, trip_id).pinned_place_ids or [])
    for d in itin.days:
        for s in d.stops:
            s.pinned = s.place_id in pins
    return row.version, itin, row.data["places"]


def latest_itinerary(db: Session, trip_id: int) -> tuple[int, Itinerary] | None:
    r = load_itinerary(db, trip_id)
    return (r[0], r[1]) if r else None


def itinerary_places(db: Session, itin: Itinerary) -> dict:
    ids = {s.place_id for d in itin.days for s in d.stops} | ({itin.stay_place_id} - {None})
    return get_places(db, list(ids))


def versions(db: Session, trip_id: int) -> list[int]:
    return list(db.scalars(select(TripItinerary.version).where(TripItinerary.trip_id == trip_id)
                           .order_by(TripItinerary.version)))


def list_trips(db: Session, user_id: str) -> list[dict]:
    names = {d["slug"]: d["name"] for d in list_destinations(db)}
    rows = db.scalars(select(TripRow).where(TripRow.user_id == user_id).order_by(TripRow.id.desc()))
    return [{"id": r.id, "spec": r.spec, "created_at": r.created_at, "destination_name": names.get(r.spec.get("destination"))}
            for r in rows]


def set_pin(db: Session, row: TripRow, place_id: int, pinned: bool) -> list[int]:
    # Reassign (not mutate) so the JSON column registers the change.
    row.pinned_place_ids = [p for p in row.pinned_place_ids or [] if p != place_id] + ([place_id] if pinned else [])
    db.commit()
    return row.pinned_place_ids


def messages(db: Session, trip_id: int) -> list[dict]:
    return [{"role": m.role, "text": m.text, "version": m.version, "created_at": m.created_at}
            for m in db.scalars(select(TripMessage).where(TripMessage.trip_id == trip_id).order_by(TripMessage.id))]


def locked_proposal(db: Session, trip_id: int, proposal_id: int) -> TripProposal | None:
    return db.scalar(select(TripProposal).where(TripProposal.id == proposal_id, TripProposal.trip_id == trip_id)
                     .with_for_update())


def locked_review(db: Session, trip_id: int, review_id: int) -> TripGroupReview | None:
    return db.scalar(select(TripGroupReview).where(TripGroupReview.id == review_id, TripGroupReview.trip_id == trip_id)
                     .with_for_update())


def add_group_review(db: Session, trip_id: int, source_version: int, base_version: int, feedback: str,
                     candidate: dict) -> TripGroupReview | str:
    """Stage a pending review and the feedback message (the caller commits); returns an error code instead when the
    base is no longer the latest version ("stale_base") or the trip already has a pending review ("review_pending").
    The trip row lock plays the part of Travility's partial unique index (one pending review per trip)."""
    db.execute(select(TripRow.id).where(TripRow.id == trip_id).with_for_update())
    latest = db.scalar(select(func.max(TripItinerary.version)).where(TripItinerary.trip_id == trip_id))
    pending = list(db.scalars(select(TripGroupReview).where(TripGroupReview.trip_id == trip_id,
                                                            TripGroupReview.status == "pending")))
    if latest != base_version:
        db.rollback()
        return "stale_base"
    if any(r.base_version == base_version for r in pending):
        db.rollback()
        return "review_pending"
    for r in pending:  # built on an older version, so it can never be applied: don't let it block new feedback
        r.status = "cancelled"
    review = TripGroupReview(trip_id=trip_id, source_version=source_version, base_version=base_version,
                             feedback=feedback, candidate=candidate)
    db.add(review)
    db.flush()
    log_message(db, trip_id, "user", feedback, source_version, commit=False)
    return review
