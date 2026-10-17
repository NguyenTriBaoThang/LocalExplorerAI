"""Pinned Stop, lịch sử chat, quay lại version cũ (spec revision-day-du §3.5)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth import current_user, get_shard
from app.agent import itinerary_event
from app.domain import Trip
from app.places_client import get_places, list_destinations
from app.replan import to_draft
from app.rules import InvalidDraft, build_itinerary
from app.trips import hub_for, itinerary_places, latest_itinerary, load_itinerary, log_message, save_itinerary

router = APIRouter()


def _own(conn, trip_id: int, user_id: int) -> dict:
    row = conn.execute("SELECT id, spec, pinned_place_ids FROM trips WHERE id = %s AND user_id = %s",
                       (trip_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    return row


class PinIn(BaseModel):
    place_id: int
    pinned: bool


@router.patch("/trips/{trip_id}/pins")
def set_pin(trip_id: int, body: PinIn, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    _own(conn, trip_id, user_id)
    if body.pinned:
        latest = latest_itinerary(conn, trip_id)
        if not latest or body.place_id not in {s.place_id for d in latest[1].days for s in d.stops}:
            raise HTTPException(422, "Chỉ ghim được Stop đang có trong lịch trình mới nhất")
        sql = "array_append(array_remove(pinned_place_ids, %(p)s), %(p)s)"
    else:
        sql = "array_remove(pinned_place_ids, %(p)s)"
    row = conn.execute(f"UPDATE trips SET pinned_place_ids = {sql} WHERE id = %(t)s RETURNING pinned_place_ids",
                       {"p": body.place_id, "t": trip_id}).fetchone()
    return {"pinned_place_ids": row["pinned_place_ids"]}


@router.get("/trips/{trip_id}/messages")
def get_messages(trip_id: int, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    _own(conn, trip_id, user_id)
    return conn.execute("SELECT role, text, version, created_at FROM messages WHERE trip_id = %s ORDER BY id",
                        (trip_id,)).fetchall()


@router.post("/trips/{trip_id}/restore/{version}")
def restore(trip_id: int, version: int, user_id: int = Depends(current_user), conn=Depends(get_shard)):
    """Chép bản cũ thành bản mới, tính lại tiền + Conflict theo Trip hiện tại (spec §2 D3–D5)."""
    row = _own(conn, trip_id, user_id)
    old = load_itinerary(conn, trip_id, version)
    if not old:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    trip, itin = Trip.model_validate(row["spec"]), old[1]
    if len(itin.days) != trip.days:
        raise HTTPException(422, f"Bản {version} có {len(itin.days)} ngày nhưng chuyến đi hiện là {trip.days} ngày "
                                 "— hãy đổi lại số ngày trước khi quay lại bản này.")
    places = itinerary_places(conn, itin)
    used = {s.place_id for d in itin.days for s in d.stops}
    pins = [p for p in row["pinned_place_ids"] if p in used]
    dropped = get_places(conn, [p for p in row["pinned_place_ids"] if p not in used])
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip.destination)
    try:
        new = build_itinerary(trip, to_draft(itin), places, [d.rain_chance for d in itin.days], hub_for(dest, trip))
    except InvalidDraft as e:  # vd Place trong bản cũ đã bị xoá khỏi dữ liệu
        raise HTTPException(422, f"Không quay lại được bản {version}: {e}") from None
    ev = itinerary_event(new, places)
    with conn.transaction():
        conn.execute("UPDATE trips SET pinned_place_ids = %s WHERE id = %s", (pins, trip_id))
        n = save_itinerary(conn, trip_id, ev["itinerary"], ev["places"])
        text = f"Đã quay lại bản {version} (thành bản {n})."
        if dropped:
            text += " Bỏ ghim: " + ", ".join(p.name for p in dropped.values()) + "."
        log_message(conn, trip_id, "ai", text, n)
    return {**ev, "trip_id": trip_id, "version": n, "pinned_place_ids": pins}
