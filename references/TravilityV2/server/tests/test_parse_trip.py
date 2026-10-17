import datetime as dt

import pytest

from app.agent import TripParseError, UnsupportedDestination, parse_trip
from tests.fakes import FakeClient, reply

DESTS = {"da-lat": "Đà Lạt", "hoi-an": "Đà Nẵng – Hội An"}
TODAY = dt.date(2026, 9, 25)


def run(args):
    return parse_trip(FakeClient([reply(("record_trip", args))]), "m", "...", DESTS, TODAY)


def test_parses_trip():
    t = run({"destination": "da-lat", "days": 3, "budget": 3_000_000, "required_tags": ["cafe-chill"]})
    assert (t.destination, t.days, t.budget, t.required_tags) == ("da-lat", 3, 3_000_000, ["cafe-chill"])


def test_unsupported_destination_lists_supported():
    with pytest.raises(UnsupportedDestination, match="Đà Lạt"):
        run({"destination": "unsupported", "days": 3, "budget": 1})


def test_too_many_days():
    with pytest.raises(TripParseError, match="1–7 ngày"):
        run({"destination": "da-lat", "days": 10, "budget": 1})


def test_broken_json():
    with pytest.raises(TripParseError):
        run("{not json")


def test_prompt_lists_destinations_and_today():
    client = FakeClient([reply(("record_trip", {"destination": "da-lat", "days": 1, "budget": 1}))])
    parse_trip(client, "m", "...", DESTS, TODAY)
    system = client.calls[0]["messages"][0]["content"]
    assert "2026-09-25" in system and "hoi-an" in system


def test_parses_arrival_and_own_car():
    t = run({"destination": "da-lat", "days": 2, "budget": 1, "travel_mode": "o-to-rieng",
             "origin_city": "TP.HCM", "arrival_mode": "tu-lai", "arrival_time": "14:00", "departure_time": "16:00"})
    assert (t.travel_mode, t.origin_city, t.arrival_mode, t.arrival_time, t.departure_time) == (
        "o-to-rieng", "TP.HCM", "tu-lai", "14:00", "16:00")


def test_unstated_travel_mode_stays_none():
    assert run({"destination": "da-lat", "days": 2, "budget": 1}).travel_mode is None


def test_malformed_time_from_llm_is_dropped():
    t = run({"destination": "da-lat", "days": 2, "budget": 1, "arrival_time": "2pm", "departure_time": "14h"})
    assert (t.arrival_time, t.departure_time) == (None, None)
