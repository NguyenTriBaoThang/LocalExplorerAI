"""Disruption → Proposal → áp dụng (spec revision-giu-muc-dich §5). Không gọi LLM (ADR-0006)."""
from fastapi import APIRouter, Depends, HTTPException
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from app.agent import itinerary_event
from app.auth import current_user, get_shard
from app.domain import Disruption, Trip
from app.places_client import get_places, list_destinations, similar_places
from app.replan import InvalidDisruption, NoFeasible, propose
from app.trips import hub_for, load_itinerary, log_message, save_itinerary

router = APIRouter()
STALE = "Lịch trình đã có bản mới hơn, hãy mở bản mới nhất rồi thử lại."


class DisruptionIn(Disruption):
    version: int


class ApplyIn(BaseModel):
    option: int = Field(ge=0)


def _trip(conn, trip_id: int, user_id: int) -> Trip:
    row = conn.execute("SELECT spec FROM trips WHERE id = %s AND user_id = %s", (trip_id, user_id)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy chuyến đi")
    return Trip.model_validate(row["spec"])


def _latest_version(conn, trip_id: int) -> int | None:
    return conn.execute("SELECT MAX(version) AS v FROM itineraries WHERE trip_id = %s", (trip_id,)).fetchone()["v"]


@router.post("/trips/{trip_id}/disruptions")
def create_disruption(trip_id: int, body: DisruptionIn, user_id: int = Depends(current_user),
                      conn=Depends(get_shard)):
    trip = _trip(conn, trip_id, user_id)
    loaded = load_itinerary(conn, trip_id, body.version)
    if not loaded:
        raise HTTPException(404, "Không tìm thấy phiên bản lịch trình")
    if body.version != _latest_version(conn, trip_id):
        raise HTTPException(409, STALE)
    itin = loaded[1]
    ids = {s.place_id for d in itin.days for s in d.stops}
    if itin.stay_place_id is not None:
        ids.add(itin.stay_place_id)
    places = get_places(conn, list(ids))
    dest = next(d for d in list_destinations(conn) if d["slug"] == trip.destination)
    try:
        result = propose(trip, itin, places, body,
                         lambda lost, used: similar_places(conn, lost.id, lost.kind, used, trip.avoided_tags),
                         hub_for(dest, trip))
    except InvalidDisruption as e:
        raise HTTPException(422, str(e)) from None

    disruption = Jsonb(body.model_dump(exclude={"version"}))
    if isinstance(result, NoFeasible):
        pid = conn.execute(
            """INSERT INTO proposals(trip_id, base_version, disruption, options, no_feasible)
               VALUES (%s, %s, %s, '[]', %s) RETURNING id""",
            (trip_id, body.version, disruption, result.reason_codes)).fetchone()["id"]
        return {"proposal_id": pid, "no_feasible": result.reason_codes}

    options = []
    for o in result:
        ev = itinerary_event(o.itinerary, places | {p.id: p for p in o.added})
        options.append({"itinerary": ev["itinerary"], "places": ev["places"], "changed": o.changed,
                        "metrics": o.metrics, "reason_codes": o.reason_codes, "explanation": o.explanation,
                        "title": o.title, "added": [p.id for p in o.added]})
    pid = conn.execute(
        "INSERT INTO proposals(trip_id, base_version, disruption, options) VALUES (%s, %s, %s, %s) RETURNING id",
        (trip_id, body.version, disruption, Jsonb(options))).fetchone()["id"]
    return {"proposal_id": pid, "options": options}


@router.post("/trips/{trip_id}/proposals/{proposal_id}/apply")
def apply_proposal(trip_id: int, proposal_id: int, body: ApplyIn, user_id: int = Depends(current_user),
                   conn=Depends(get_shard)):
    _trip(conn, trip_id, user_id)
    with conn.transaction():
        p = conn.execute("SELECT * FROM proposals WHERE id = %s AND trip_id = %s FOR UPDATE",
                         (proposal_id, trip_id)).fetchone()
        if not p:
            raise HTTPException(404, "Không tìm thấy phương án")
        if p["applied_version"] is not None:  # áp dụng lại cùng phương án → trả version cũ (idempotent)
            if p["chosen_index"] != body.option:
                raise HTTPException(409, "Đã áp dụng một phương án khác cho sự cố này")
            version = p["applied_version"]
        else:
            if body.option >= len(p["options"]):
                raise HTTPException(422, "Không có phương án này")
            trip = conn.execute("SELECT pinned_place_ids FROM trips WHERE id = %s FOR UPDATE", (trip_id,)).fetchone()
            if p["base_version"] != _latest_version(conn, trip_id):
                raise HTTPException(409, STALE)
            opt = p["options"][body.option]
            pins = set(trip["pinned_place_ids"])
            if pins - {st["place_id"] for d in opt["itinerary"]["days"] for st in d["stops"]}:
                raise HTTPException(409, "Stop này vừa được ghim — bỏ ghim rồi báo sự cố lại nếu vẫn muốn đổi.")
            try:
                version = save_itinerary(conn, trip_id, opt["itinerary"], opt["places"])
            except UniqueViolation:  # lần lưu khác (phương án khác / chat) vừa chiếm số version này
                raise HTTPException(409, STALE) from None
            conn.execute("UPDATE proposals SET chosen_index = %s, applied_version = %s WHERE id = %s",
                         (body.option, version, proposal_id))
            log_message(conn, trip_id, "ai", f"Đã áp dụng phương án — lịch trình bản {version}.", version)
    opt = p["options"][body.option]
    return {"type": "itinerary", "itinerary": opt["itinerary"], "places": opt["places"],
            "trip_id": trip_id, "version": version}
