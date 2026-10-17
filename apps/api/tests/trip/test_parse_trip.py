import datetime as dt

import pytest

from app.prompts.registry import catalog
from app.services.trip.agent import TripParseError, UnsupportedDestination, parse_trip
from tests.trip.conftest import FakeClient, reply

DESTS = {"tp-hcm": "TP. Hồ Chí Minh"}
TODAY = dt.date(2026, 9, 25)


def run(args):
    return parse_trip(FakeClient([reply(("record_trip", args))]), "m", "...", DESTS, TODAY)


def test_parses_trip():
    t = run({"destination": "tp-hcm", "days": 3, "budget": 3_000_000, "required_tags": ["cafe-chill"]})
    assert (t.destination, t.days, t.budget, t.required_tags) == ("tp-hcm", 3, 3_000_000, ["cafe-chill"])


def test_unsupported_destination_message():
    with pytest.raises(UnsupportedDestination, match="TP. Hồ Chí Minh"):
        run({"destination": "ha-noi", "days": 3, "budget": 1})


def test_unsupported_marker_is_rejected():
    with pytest.raises(UnsupportedDestination, match="Hiện mình chỉ hỗ trợ lịch trình ở TP. Hồ Chí Minh."):
        run({"destination": "unsupported", "days": 3, "budget": 1})


def test_too_many_days():
    with pytest.raises(TripParseError, match="1–7 ngày"):
        run({"destination": "tp-hcm", "days": 10, "budget": 1})


def test_broken_json():
    with pytest.raises(TripParseError):
        run("{not json")


def test_prompt_lists_destinations_and_today():
    client = FakeClient([reply(("record_trip", {"destination": "tp-hcm", "days": 1, "budget": 1}))])
    parse_trip(client, "m", "...", DESTS, TODAY)
    system = client.calls[0]["messages"][0]["content"]
    assert "2026-09-25" in system and "tp-hcm" in system


def test_parses_arrival_and_own_car():
    t = run({"destination": "tp-hcm", "days": 2, "budget": 1, "travel_mode": "o-to-rieng",
             "origin_city": "Hà Nội", "arrival_mode": "may-bay", "arrival_time": "14:00", "departure_time": "16:00"})
    assert (t.travel_mode, t.origin_city, t.arrival_mode, t.arrival_time, t.departure_time) == (
        "o-to-rieng", "Hà Nội", "may-bay", "14:00", "16:00")


def test_unstated_travel_mode_stays_none():
    assert run({"destination": "tp-hcm", "days": 2, "budget": 1}).travel_mode is None


def test_malformed_time_from_llm_is_dropped():
    t = run({"destination": "tp-hcm", "days": 2, "budget": 1, "arrival_time": "2pm", "departure_time": "14h"})
    assert (t.arrival_time, t.departure_time) == (None, None)


def test_prompts_load_from_catalog():
    assert catalog.get("TRIP_PLANNER").version == "3.2.0"
    assert "search_places" in catalog.get("TRIP_PLANNER").system_prompt


def test_every_trip_prompt_formats_like_the_code_does():
    # only TRIP_PARSER is .format()ed; the rest are sent verbatim, so a stray brace must not appear in them
    catalog.get("TRIP_PARSER").system_prompt.format(today="2026-09-25", dests="tp-hcm (TP. Hồ Chí Minh)")
    for pid in ("TRIP_PLANNER", "TRIP_FOLLOWUP", "TRIP_GROUP_REVIEW"):
        text = catalog.get(pid).system_prompt
        assert text and text.format() == text
