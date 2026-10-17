from app.services.trip.domain import Draft, DraftDay, DraftStop, Itinerary


def to_draft(itin: Itinerary) -> Draft:
    return Draft(stay_place_id=itin.stay_place_id, summary=itin.summary, days=[
        DraftDay(stops=[DraftStop(**s.model_dump(exclude={"est_cost"})) for s in d.stops]) for d in itin.days])
