import datetime as dt

import pytest
from pydantic import ValidationError

from app.agent import apply_answers, merge_trip, missing_questions
from app.domain import Trip, TripAnswers

BASE = {"destination": "da-lat", "days": 2, "budget": 1}
DATE = dt.date(2026, 10, 3)


def fields(trip):
    return [q["field"] for q in missing_questions(trip)]


def test_asks_travel_mode_when_unstated():
    qs = missing_questions(Trip(**BASE))
    assert [q["field"] for q in qs] == ["travel_mode"]
    assert {o["value"] for o in qs[0]["options"]} == {"xe-may", "grab", "xe-may-rieng", "o-to-rieng"}


def test_asks_arrival_only_with_start_date():
    assert fields(Trip(**BASE, travel_mode="grab")) == []
    assert fields(Trip(**BASE, travel_mode="grab", start_date=DATE)) == ["arrival"]


def test_known_arrival_is_not_asked():
    assert fields(Trip(**BASE, travel_mode="grab", start_date=DATE, arrival_time="14:00")) == []


def test_apply_answers_fills_and_defaults_travel_mode():
    t = apply_answers(Trip(**BASE), TripAnswers(arrival_time="14:00", arrival_mode="may-bay"))
    assert (t.travel_mode, t.arrival_time, t.arrival_mode) == ("xe-may", "14:00", "may-bay")


def test_apply_answers_sets_chosen_mode():
    assert apply_answers(Trip(**BASE), TripAnswers(travel_mode="o-to-rieng")).travel_mode == "o-to-rieng"


def test_apply_answers_revalidates_times():
    with pytest.raises(ValidationError, match="Giờ về phải sau giờ đến"):
        apply_answers(Trip(destination="da-lat", days=1, budget=1),
                      TripAnswers(arrival_time="15:00", departure_time="10:00"))


def test_merge_keeps_previous_answers_when_follow_up_is_silent():
    old = Trip(**BASE, travel_mode="o-to-rieng", arrival_time="14:00", start_date=DATE)
    new = Trip(destination="da-lat", days=2, budget=1, preferred_tags=["gia-re"])
    t = merge_trip(old, new)
    assert (t.travel_mode, t.arrival_time, t.start_date, t.preferred_tags) == ("o-to-rieng", "14:00", DATE, ["gia-re"])


def test_merge_lets_follow_up_override():
    t = merge_trip(Trip(**BASE, travel_mode="grab"), Trip(**BASE, travel_mode="xe-may-rieng"))
    assert t.travel_mode == "xe-may-rieng"
