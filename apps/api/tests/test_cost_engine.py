from datetime import date

import pytest

from app.services.quote.cost_engine import MissingRateError, QuoteRequestLite, RateItem, compute_cost


def item(id, category, unit, amount, **kw):
    return RateItem(id, "card1", 3, "sup", category, kw.pop("code", id), id, unit, amount, **kw)


def rates(*extra):
    return [
        item("v45", "vehicle", "per_trip", 4_000_000, seats=45),
        item("v45km", "vehicle", "per_km", 10_000, seats=45),
        item("v29", "vehicle", "per_trip", 2_500_000, seats=29),
        item("v29km", "vehicle", "per_km", 8_000, seats=29),
        item("g", "guide", "per_day", 800_000),
        item("m", "meal", "per_pax", 100_000),
        item("h", "hotel", "per_room_night", 600_000),
        item("t", "ticket", "per_pax", 120_000, code="CUCHI"),
        *extra,
    ]


# 100 km total, one ticketed stop.
ITIN = {"days": [{"legs": [{"distance_km": 60}, {"distance_km": 40}], "stops": [{"ticket_code": "CUCHI"}]}]}
ITIN2 = {"days": [{"legs": [{"distance_km": 100}], "stops": []}, {"legs": [], "stops": []}]}
FRI = date(2025, 3, 7)  # Friday
THU = date(2025, 3, 6)


def cost(pax, days=1, meals=2, itin=ITIN, depart=THU, extra=()):
    return compute_cost(itin, QuoteRequestLite(pax, days, meals), rates(*extra), depart)


def vehicles(b):
    return {(l.rate_item_id, l.qty) for l in b.lines if l.category == "vehicle" and l.unit_vnd > 20_000}


def test_vehicle_boundary_45_vs_2x29():
    # need = pax + 1 guide. v45 = 4.0M+1.0M km = 5.0M ; v29 = 2.5M+0.8M = 3.3M each.
    assert vehicles(cost(28)) == {("v29", 1)}   # 29 seats, 3.3M < 5.0M
    assert vehicles(cost(40)) == {("v45", 1)}   # 41 seats: only v45 (5.0M < 2x29=6.6M)
    assert vehicles(cost(44)) == {("v45", 1)}   # 45 seats exactly
    assert vehicles(cost(45)) == {("v29", 2)}   # 46 seats: 2x29=6.6M < 45+29=8.3M


def test_golden_single_day_pax40_fixed_variable_split():
    b = cost(40)
    # fixed: vehicle 5.0M + guide 0.8M + guide meals 2x100k = 6.0M
    assert b.fixed_total == 6_000_000
    # variable: meals 2x40x100k = 8.0M + tickets 40x120k = 4.8M
    assert b.variable_total == 12_800_000 and b.variable_per_pax == 320_000
    assert b.total == 18_800_000


def test_cost_at_matches_engine_and_steps_at_vehicle_boundary():
    b = cost(40)
    assert b.cost_at(40) == 18_800_000
    assert b.cost_at(44) == 5_000_000 + 800_000 + 200_000 + 44 * 320_000 == 20_000_000 + 80_000
    # 45 pax flips to 2x29: fixed 6.6M+0.8M+0.2M, variable 45x320k
    assert b.cost_at(45) == 7_600_000 + 45 * 320_000 == cost(45).total


def test_odd_pax_rooms_round_up():
    # 5 and 6 pax -> 3 rooms; 4 -> 2 rooms. 1 night at 600k, guide has own room (fixed).
    def hotel(pax):
        return [l for l in cost(pax, days=2, meals=0, itin=ITIN2).lines if l.category == "hotel"]
    h5 = hotel(5)
    assert (h5[0].qty, h5[0].amount_vnd, h5[0].fixed) == (3, 1_800_000, False)
    assert (h5[1].qty, h5[1].amount_vnd, h5[1].fixed) == (1, 600_000, True)
    assert hotel(6)[0].qty == 3 and hotel(4)[0].qty == 2


def test_tet_surcharge_full_trip():
    tet = {"tet": True}
    s = item("tet", "surcharge", "pct", 30, code="TET", conditions=tet)
    b = cost(5, days=2, meals=0, itin=ITIN2, depart=date(2024, 2, 9), extra=[s])  # 02-09 eve, 02-10 Tết
    by = {(l.category, l.label): l for l in b.lines}
    assert by[("vehicle", "v29 (29 seats)")].surcharge_vnd == 750_000      # 2.5M x 30%
    assert by[("vehicle", "Distance 100 km (29 seats)")].surcharge_vnd == 240_000
    assert by[("guide", "g")].surcharge_vnd == 480_000                     # 1.6M x 30%
    assert by[("hotel", "h")].surcharge_vnd == 540_000                     # 1.8M x 30%
    assert by[("hotel", "h (guide room)")].surcharge_vnd == 180_000
    assert sum(l.surcharge_vnd for l in b.lines) == 2_190_000
    assert b.total == 3_300_000 + 1_600_000 + 1_800_000 + 600_000 + 2_190_000


def test_tet_surcharge_partial_proration():
    s = item("tet", "surcharge", "pct", 30, code="TET", conditions={"tet": True})
    # Departs 02-08, only 02-09 (eve) is Tết: guide 1.6M x 30% x 1/2 = 240k; Thu-night hotel not Tết.
    b = cost(5, days=2, meals=0, itin=ITIN2, depart=date(2024, 2, 8), extra=[s])
    surch = {l.label: l.surcharge_vnd for l in b.lines}
    assert surch["g"] == 240_000 and surch["h"] == 0
    assert surch["v29 (29 seats)"] == 375_000


def test_weekend_surcharge_fri_sat_two_day_trip():
    s = item("we", "surcharge", "pct", 10, code="WE", conditions={"weekdays": ["sat", "sun"]})
    b = cost(5, days=2, meals=0, itin=ITIN2, depart=FRI, extra=[s])
    surch = {l.label: l.surcharge_vnd for l in b.lines}
    assert surch["v29 (29 seats)"] == 125_000   # 2.5M x 10% x 1/2
    assert surch["Distance 100 km (29 seats)"] == 40_000
    assert surch["g"] == 80_000                 # 1.6M x 10% x 1/2
    assert surch["h"] == 0 and surch["h (guide room)"] == 0  # the only night is Friday
    assert b.total == 3_300_000 + 1_600_000 + 1_800_000 + 600_000 + 245_000


def test_applies_to_limits_categories():
    s = item("we", "surcharge", "pct", 10, code="WE", conditions={"weekdays": ["sat"], "applies_to": ["vehicle"]})
    b = cost(5, days=1, meals=0, depart=date(2025, 3, 8), extra=[s])
    assert {l.category for l in b.lines if l.surcharge_vnd} == {"vehicle"}


def test_experience_price_rule():
    itin = {"days": [{"legs": [], "stops": [
        {"name": "A", "price_vnd": 50_000, "price_basis": "per_person"},
        {"name": "B", "price_vnd": 700_000, "price_basis": "per_group"},
    ]}]}
    b = compute_cost(itin, QuoteRequestLite(10, 1, 0, 0), rates(), THU)
    amounts = [l.amount_vnd for l in b.lines if l.category == "ticket"]
    assert amounts == [500_000, 700_000]


def test_missing_rates_raise():
    with pytest.raises(MissingRateError):
        compute_cost(ITIN, QuoteRequestLite(10, 1, 0), [i for i in rates() if i.category != "vehicle"], THU)
    with pytest.raises(MissingRateError):
        compute_cost(ITIN, QuoteRequestLite(10, 2, 0), [i for i in rates() if i.category != "hotel"], THU)
