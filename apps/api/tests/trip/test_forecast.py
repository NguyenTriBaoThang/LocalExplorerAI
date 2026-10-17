import datetime as dt

from app.services import open_meteo_service
from app.services.open_meteo_service import OpenMeteoUnavailable
from app.services.trip.forecast import get_rain_chance

TODAY = dt.date(2026, 9, 25)


def fake(monkeypatch, pct_by_date=None):
    calls = []

    def daily_forecast(lat, lon, d, location_name=""):
        calls.append(d)
        if pct_by_date is None or d not in pct_by_date:
            raise OpenMeteoUnavailable("x")
        return {"precipitation_probability_pct": pct_by_date[d]}
    monkeypatch.setattr(open_meteo_service, "daily_forecast", daily_forecast)
    return calls


def test_within_horizon(monkeypatch):
    start = dt.date(2026, 9, 27)
    fake(monkeypatch, {start + dt.timedelta(days=i): v for i, v in enumerate([10, 70, 20])})
    assert get_rain_chance(10.7, 106.7, start, 3, TODAY) == [10, 70, 20]


def test_partial_horizon_is_padded(monkeypatch):
    start = dt.date(2026, 10, 9)  # horizon ends 2026-10-10
    calls = fake(monkeypatch, {start: 10, start + dt.timedelta(days=1): 70})
    assert get_rain_chance(10.7, 106.7, start, 3, TODAY) == [10, 70, None]
    assert len(calls) == 2  # ngày ngoài khung không gọi Open-Meteo


def test_no_date_or_too_far_or_past(monkeypatch):
    calls = fake(monkeypatch, {})
    assert get_rain_chance(10.7, 106.7, None, 3, TODAY) is None
    assert get_rain_chance(10.7, 106.7, dt.date(2026, 10, 20), 3, TODAY) is None
    assert get_rain_chance(10.7, 106.7, dt.date(2026, 9, 1), 3, TODAY) is None
    assert calls == []


def test_unavailable_first_day_gives_none(monkeypatch):
    fake(monkeypatch, {})
    assert get_rain_chance(10.7, 106.7, dt.date(2026, 9, 27), 2, TODAY) is None


def test_unavailable_later_day_is_none_for_that_day(monkeypatch):
    start = dt.date(2026, 9, 27)
    fake(monkeypatch, {start: 10})
    assert get_rain_chance(10.7, 106.7, start, 2, TODAY) == [10, None]
