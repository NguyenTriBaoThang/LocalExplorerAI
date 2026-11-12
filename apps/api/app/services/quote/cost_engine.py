"""Deterministic tour cost engine. Integer VND, stdlib only, no DB, no LLM.

Conventions
- unit "pct": amount_vnd holds a WHOLE percent (20 -> 20%).
- Fixed (do not scale with pax): vehicles, guide, guide FOC meals, guide room.
- Variable: meals, tickets, hotel rooms. Hotel is STEP-variable: ceil(pax/2) rooms.
- Surcharge proration: a pct item matches a tour day when ALL its conditions hold
  (weekdays / holiday / tet / months; empty = every day). Each targeted category
  line is surcharged by pct * (matching days / total days); hotel counts nights
  (night i belongs to day i). So a Fri-Sat trip with a weekend surcharge hits
  half of vehicle/guide/meals/tickets but not the Friday-night hotel.
- Surcharges ride on the base line (CostLine.surcharge_vnd), no separate lines.
"""
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from math import ceil

from app.services.quote.vn_calendar import day_flags

CATEGORIES = ("vehicle", "guide", "meal", "ticket", "hotel", "surcharge")
_WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
_COSTED = ("vehicle", "guide", "meal", "ticket", "hotel")


class MissingRateError(ValueError):
    """A required cost category has no usable rate item."""


@dataclass
class RateItem:
    id: str
    card_id: str
    card_version: int
    supplier: str
    category: str
    code: str
    label: str
    unit: str  # per_km|per_day|per_trip|per_pax|per_room_night|pct
    amount_vnd: int
    seats: int | None = None
    max_pax: int | None = None
    experience_id: str | None = None
    conditions: dict = field(default_factory=dict)


@dataclass
class QuoteRequestLite:
    pax: int
    days: int
    meals: int = 0  # total meals per guest over the trip
    guide_count: int = 1
    meal_code: str | None = None  # None = cheapest per_pax meal item


@dataclass
class CostLine:
    category: str
    label: str
    rate_item_id: str | None
    card_version: int | None
    qty: int
    unit_vnd: int
    amount_vnd: int
    fixed: bool
    surcharge_vnd: int = 0
    surcharge_codes: tuple = ()

    @property
    def total_vnd(self) -> int:
        return self.amount_vnd + self.surcharge_vnd


@dataclass
class CostBreakdown:
    pax: int
    lines: list[CostLine]
    # Re-runs the engine for another pax count (exact: vehicle/room steps included).
    _recompute: Callable[[int], "CostBreakdown"] | None = field(default=None, repr=False, compare=False)

    @property
    def total(self) -> int:
        return sum(line.total_vnd for line in self.lines)

    @property
    def fixed_total(self) -> int:
        return sum(line.total_vnd for line in self.lines if line.fixed)

    @property
    def variable_total(self) -> int:
        return self.total - self.fixed_total

    @property
    def variable_per_pax(self) -> int:
        # Rounded up; room step-cost is spread over this pax, so only exact at self.pax.
        return -(-self.variable_total // self.pax)

    def cost_at(self, pax: int) -> int:
        if pax == self.pax or self._recompute is None:
            return self.total
        return self._recompute(pax).total


def _cheapest(items: list[RateItem], category: str, unit: str, code: str | None = None) -> RateItem:
    pool = [i for i in items if i.category == category and i.unit == unit
            and i.experience_id is None and (code is None or i.code == code)]
    if not pool:
        raise MissingRateError(f"no {category} rate ({unit}{', ' + code if code else ''})")
    return min(pool, key=lambda i: i.amount_vnd)


def _vehicles(items: list[RateItem], need_seats: int, days: int, km: int) -> list[tuple[RateItem, int, int]]:
    """Cheapest multiset of vehicles covering need_seats. Returns (base item, count, per_vehicle_km_cost)."""
    types: dict[tuple, dict] = {}
    for i in items:
        if i.category == "vehicle" and i.seats and i.experience_id is None:
            t = types.setdefault((i.supplier, i.seats), {"base": None, "km": 0})
            if i.unit in ("per_trip", "per_day"):
                cost = i.amount_vnd * (days if i.unit == "per_day" else 1)
                if t["base"] is None or cost < t["base"][0]:
                    t["base"] = (cost, i)
            elif i.unit == "per_km":
                t["km"] = i.amount_vnd if not t["km"] else min(t["km"], i.amount_vnd)
    opts = [(b[0] + t["km"] * km, b[1], t["km"] * km, key[1]) for key, t in types.items() if (b := t["base"])]
    if not opts:
        raise MissingRateError("no vehicle rate")
    # Unbounded-knapsack DP over seats; ties prefer fewer vehicles.
    best: list[tuple[int, int, int] | None] = [(0, 0, -1)] + [None] * need_seats
    for s in range(1, need_seats + 1):
        for idx, (cost, _, _, seats) in enumerate(opts):
            prev = best[max(0, s - seats)]
            cand = (prev[0] + cost, prev[1] + 1, idx)
            if best[s] is None or cand[:2] < best[s][:2]:
                best[s] = cand
    counts: dict[int, int] = {}
    s = need_seats
    while s > 0:
        idx = best[s][2]
        counts[idx] = counts.get(idx, 0) + 1
        s = max(0, s - opts[idx][3])
    return [(opts[i][1], n, opts[i][2]) for i, n in counts.items()]


def _matches(cond: dict, d: date) -> bool:
    f = day_flags(d)
    if "weekdays" in cond and _WEEKDAYS[d.weekday()] not in cond["weekdays"]:
        return False
    if cond.get("holiday") and not f["holiday"]:
        return False
    if cond.get("tet") and not f["tet"]:
        return False
    return not ("months" in cond and d.month not in cond["months"])


def _ticket_lines(itin: dict, items: list[RateItem], pax: int) -> list[CostLine]:
    lines = []
    for day in itin.get("days", []):
        for stop in day.get("stops", []):
            code = stop.get("ticket_code")
            if code:
                it = _cheapest(items, "ticket", "per_pax", code)
                lines.append(CostLine("ticket", it.label, it.id, it.card_version, pax, it.amount_vnd, it.amount_vnd * pax, False))
            elif stop.get("price_vnd"):
                # Same rule as planner_service: per_person x group, per_group flat.
                per_person = stop.get("price_basis", "per_person") == "per_person"
                qty = pax if per_person else 1
                lines.append(CostLine("ticket", stop.get("name", "Experience"), None, None, qty,
                                      stop["price_vnd"], stop["price_vnd"] * qty, False))
    return lines


def compute_cost(itin: dict, req: QuoteRequestLite, items: list[RateItem], depart: date) -> CostBreakdown:
    pax, days = req.pax, req.days
    nights, guides = days - 1, req.guide_count
    km = sum(leg.get("distance_km", 0) for day in itin.get("days", []) for leg in day.get("legs", []))
    km = ceil(km)
    lines: list[CostLine] = []

    for base, n, km_cost in _vehicles(items, pax + guides, days, km):
        unit = base.amount_vnd * (days if base.unit == "per_day" else 1)
        lines.append(CostLine("vehicle", f"{base.label} ({base.seats} seats)", base.id, base.card_version, n, unit, unit * n, True))
        if km_cost:
            lines.append(CostLine("vehicle", f"Distance {km} km ({base.seats} seats)", base.id, base.card_version,
                                  n * km, km_cost // km, km_cost * n, True))

    if guides:
        g = _cheapest(items, "guide", "per_day")
        lines.append(CostLine("guide", g.label, g.id, g.card_version, days * guides, g.amount_vnd, g.amount_vnd * days * guides, True))
    if req.meals:
        m = _cheapest(items, "meal", "per_pax", req.meal_code)
        lines.append(CostLine("meal", m.label, m.id, m.card_version, req.meals * pax, m.amount_vnd, m.amount_vnd * req.meals * pax, False))
        if guides:
            lines.append(CostLine("meal", f"{m.label} (guide FOC)", m.id, m.card_version, req.meals * guides,
                                  m.amount_vnd, m.amount_vnd * req.meals * guides, True))
    lines += _ticket_lines(itin, items, pax)
    if nights:
        h = _cheapest(items, "hotel", "per_room_night")
        rooms = ceil(pax / 2)
        lines.append(CostLine("hotel", h.label, h.id, h.card_version, rooms * nights, h.amount_vnd, h.amount_vnd * rooms * nights, False))
        if guides:
            lines.append(CostLine("hotel", f"{h.label} (guide room)", h.id, h.card_version, guides * nights,
                                  h.amount_vnd, h.amount_vnd * guides * nights, True))

    for s in (i for i in items if i.category == "surcharge" and i.unit == "pct"):
        targets = s.conditions.get("applies_to") or _COSTED
        for line in lines:
            if line.category not in targets:
                continue
            span = nights if line.category == "hotel" else days
            hit = sum(_matches(s.conditions, depart + timedelta(days=i)) for i in range(span))
            if hit:
                num, den = line.amount_vnd * hit * s.amount_vnd, 100 * span
                line.surcharge_vnd += (2 * num + den) // (2 * den)  # round half up
                line.surcharge_codes += (s.code,)

    return CostBreakdown(pax, lines, lambda p: compute_cost(itin, QuoteRequestLite(p, days, req.meals, guides, req.meal_code), items, depart))
