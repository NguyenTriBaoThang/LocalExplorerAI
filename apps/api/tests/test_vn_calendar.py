from datetime import date

import pytest

from app.services.quote.vn_calendar import CalendarRangeError, day_flags, is_holiday, is_tet, is_weekend


def test_tet_window_is_eve_through_day_5():
    # Tết 2024 = Sat 2024-02-10; window 02-09 .. 02-14.
    assert not is_tet(date(2024, 2, 8))
    assert is_tet(date(2024, 2, 9)) and is_tet(date(2024, 2, 10)) and is_tet(date(2024, 2, 14))
    assert not is_tet(date(2024, 2, 15))


@pytest.mark.parametrize("tet", [date(2023, 1, 22), date(2025, 1, 29), date(2026, 2, 17), date(2027, 2, 6), date(2028, 1, 26)])
def test_tet_day_one_is_tet_and_holiday(tet):
    assert is_tet(tet) and is_holiday(tet)


def test_gio_to_and_fixed_holidays():
    for d in (date(2023, 4, 29), date(2024, 4, 18), date(2025, 4, 7), date(2026, 4, 26), date(2027, 4, 16), date(2028, 4, 4)):
        assert is_holiday(d) and not is_tet(d)
    for d in (date(2024, 1, 1), date(2024, 4, 30), date(2024, 5, 1), date(2024, 9, 1), date(2024, 9, 2), date(2024, 9, 3)):
        assert is_holiday(d)
    assert not is_holiday(date(2024, 9, 4))


def test_weekend_and_flags():
    assert is_weekend(date(2024, 2, 10)) and not is_weekend(date(2024, 2, 9))
    assert day_flags(date(2024, 2, 10)) == {"weekend": True, "holiday": True, "tet": True, "month": 2}


def test_year_outside_table_raises():
    for d in (date(2022, 12, 31), date(2029, 1, 1)):
        with pytest.raises(CalendarRangeError):
            is_holiday(d)
    assert is_weekend(date(2030, 1, 5))  # weekend needs no table
