"""Vietnam holiday calendar for quote surcharges (hard-coded, no lunar math).

ponytail: table covers 2023-2028 only; extend TET/GIO_TO by hand each year.
Dates outside the table raise CalendarRangeError instead of silently
returning "no holiday" (which would under-price a Tết tour).
"""
from datetime import date, timedelta

FIRST_YEAR, LAST_YEAR = 2023, 2028

# Solar date of Tết Nguyên Đán day 1 (mùng 1).
TET = {
    2023: date(2023, 1, 22),
    2024: date(2024, 2, 10),
    2025: date(2025, 1, 29),
    2026: date(2026, 2, 17),
    2027: date(2027, 2, 6),
    2028: date(2028, 1, 26),
}
# Solar date of Giỗ Tổ Hùng Vương (10/3 âm lịch).
GIO_TO = {
    2023: date(2023, 4, 29),
    2024: date(2024, 4, 18),
    2025: date(2025, 4, 7),
    2026: date(2026, 4, 26),
    2027: date(2027, 4, 16),
    2028: date(2028, 4, 4),
}
# Tết surcharge window: eve (30/12 âm, = mùng 1 - 1) through mùng 5 inclusive.
TET_EVE_DAYS, TET_AFTER_DAYS = 1, 4
# Fixed solar holidays (month, day). National Day is 2/9 plus ONE adjacent day
# that the government picks each year (1/9 or 3/9), so we price 1/9-3/9 all as holiday.
FIXED_HOLIDAYS = {(1, 1), (4, 30), (5, 1), (9, 1), (9, 2), (9, 3)}


class CalendarRangeError(ValueError):
    pass


def _check(d: date) -> None:
    if not FIRST_YEAR <= d.year <= LAST_YEAR:
        raise CalendarRangeError(f"{d} outside holiday table {FIRST_YEAR}-{LAST_YEAR}")


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5


def is_tet(d: date) -> bool:
    _check(d)
    start = TET[d.year] - timedelta(days=TET_EVE_DAYS)
    return start <= d <= TET[d.year] + timedelta(days=TET_AFTER_DAYS)


def is_holiday(d: date) -> bool:
    """Any public-holiday day, Tết window included."""
    _check(d)
    return is_tet(d) or d == GIO_TO[d.year] or (d.month, d.day) in FIXED_HOLIDAYS


def day_flags(d: date) -> dict:
    return {"weekend": is_weekend(d), "holiday": is_holiday(d), "tet": is_tet(d), "month": d.month}
