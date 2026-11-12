"""SYNTHETIC quote history for the quote-win model (M6). Deterministic for a given seed. Stdlib only.

    python -m scripts.generate_quote_history --seed 42 --start 2023-01-01 --years 3 --out ../../data/training/quote_win_synthetic.csv

Costs come from the REAL compute_cost on the seed rate cards (scripts.seed_operator_demo.CARDS).
True win probability: TRUE_BETA + true_p_win() below, documented in docs/quote-pricing-ground-truth.md.
"""
import argparse
import csv
import math
import random
from datetime import date, timedelta
from pathlib import Path

from app.services.quote.cost_engine import QuoteRequestLite, RateItem, compute_cost
from app.services.quote.vn_calendar import day_flags
from scripts.seed_operator_demo import CARDS

SEGMENTS = ("family", "corporate", "school")
DESTINATIONS = ("cu_chi", "mekong", "can_gio", "vung_tau", "city")
REF_MARKUP = 1.25  # reference price = cost x 1.25 x competitor index
DRY_MONTHS = (12, 1, 2, 3, 4)
OUTDOOR = ("mekong", "can_gio")
RAIN_BY_MONTH = (0.10, 0.05, 0.08, 0.18, 0.55, 0.75, 0.78, 0.78, 0.80, 0.75, 0.45, 0.20)  # HCMC climatology, Jan..Dec

TRUE_BETA = {
    "b0": 0.3,
    "price_by_segment": {"family": 6.0, "corporate": 3.5, "school": 9.0},  # slope on (price/ref - 1)
    "peak_dampen": 0.35,  # sensitivity x (1 - 0.35 x season_level)
    "season": 0.3,
    "lead": 0.25,
    "resp": 0.35,
    "comp": 1.0,
    "pax": 0.25,
    "days": 0.15,
    "rain_outdoor": 0.8,
    "segment_icpt": {"family": 0.0, "corporate": 0.2, "school": -0.2},
    "dest_icpt": {"cu_chi": 0.2, "mekong": 0.1, "can_gio": -0.1, "vung_tau": -0.2, "city": 0.1},
}
SEGMENT_DEST_W = {
    "family": (0.20, 0.25, 0.15, 0.20, 0.20),
    "corporate": (0.10, 0.15, 0.20, 0.35, 0.20),
    "school": (0.35, 0.25, 0.20, 0.05, 0.15),
}
DAYS_W = {"cu_chi": (8, 2, 0), "mekong": (6, 3.5, 0.5), "can_gio": (6, 3.5, 0.5), "vung_tau": (3, 5, 2), "city": (7, 2.5, 0.5)}
# destination -> (km on day 1, km on later days, ticket code on day 1)
ROUTES = {
    "cu_chi": (70, 40, "ticket-dia-dao-cu-chi"),
    "mekong": (160, 40, "ticket-thuyen-mekong"),
    "can_gio": (120, 40, "ticket-can-gio"),
    "vung_tau": (250, 60, None),
    "city": (40, 40, None),
}


def seed_rate_items() -> list[RateItem]:
    return [
        RateItem(code, supplier, 1, supplier, category, code, label, unit, amount, seats, max_pax, None, dict(cond))
        for supplier, category, items in CARDS
        for code, label, unit, amount, seats, max_pax, cond in items
    ]


def season_level(row: dict) -> float:
    """Demand peakiness in [0, 1]: Tet 1.0, holiday 0.8, dry season 0.5, weekend 0.3."""
    return max(
        1.0 if row["tet"] else 0.0,
        0.8 if row["holiday"] else 0.0,
        0.5 if row["month"] in DRY_MONTHS else 0.0,
        0.3 if row["weekend"] else 0.0,
    )


def true_p_win(row: dict, price_per_pax: float) -> float:
    """Ground-truth P(win) for a quote at any price (so backtests are exact counterfactuals)."""
    b, seg = TRUE_BETA, row["segment"]
    cost_pp = row["cost_total_vnd"] / row["pax"]
    comp = row["competitor_price_index"]
    level = season_level(row)
    rel = price_per_pax / (cost_pp * REF_MARKUP * comp) - 1
    sens = b["price_by_segment"][seg] * (1 - b["peak_dampen"] * level)
    z = (
        b["b0"] + b["segment_icpt"][seg] + b["dest_icpt"][row["destination"]]
        - sens * rel
        + b["lead"] * max(-1.5, min(1.5, math.log(row["lead_days"] / 14)))
        + b["season"] * level
        - b["resp"] * math.log1p(row["response_time_h"])
        + b["comp"] * (comp - 1)
        - b["pax"] * math.log(row["pax"] / 20)
        - b["days"] * (row["days"] - 1)
        - (b["rain_outdoor"] * row["rain_prob"] if row["destination"] in OUTDOOR else 0.0)
    )
    return 1 / (1 + math.exp(-z))


def _pax(rng: random.Random, segment: str) -> int:
    if segment == "family":
        return rng.randint(4, 15)
    lo, mode = (15, 25) if segment == "corporate" else (25, 40)
    return int(rng.triangular(lo, 60, mode))


def _competitor_index(rng: random.Random, months: int) -> list[float]:
    idx, out = 0.0, []
    for _ in range(months):
        idx = 0.8 * idx + rng.gauss(0, 0.04)  # AR(1) around 1.0
        out.append(max(0.8, min(1.25, 1 + idx)))
    return out


def generate(seed: int = 42, start: date = date(2023, 1, 1), years: int = 3, per_day: int = 20) -> list[dict]:
    rng = random.Random(seed)
    end = date(start.year + years, start.month, start.day)
    comp_by_month = _competitor_index(rng, years * 12 + 2)
    items = seed_rate_items()
    rows = []
    for n in range((end - start).days):
        quote_date = start + timedelta(days=n)
        comp = round(comp_by_month[(quote_date.year - start.year) * 12 + quote_date.month - start.month], 4)
        for _ in range(rng.randint(per_day // 2, per_day * 3 // 2)):
            segment = rng.choices(SEGMENTS, (0.4, 0.3, 0.3))[0]
            dest = rng.choices(DESTINATIONS, SEGMENT_DEST_W[segment])[0]
            days = rng.choices((1, 2, 3), DAYS_W[dest])[0]
            pax = _pax(rng, segment)
            lead = max(3, min(120, int(rng.lognormvariate(3.3, 0.7))))
            depart = quote_date + timedelta(days=lead)
            flags = day_flags(depart)
            km1, km2, ticket = ROUTES[dest]
            itin = {"days": [{"legs": [{"distance_km": km1 if i == 0 else km2}],
                              "stops": [{"ticket_code": ticket}] if ticket and i == 0 else []} for i in range(days)]}
            req = QuoteRequestLite(pax=pax, days=days, meals=max(1, 2 * days - 1))
            cost = round(compute_cost(itin, req, items, depart).total * rng.uniform(0.95, 1.05))
            price_pp = math.ceil(cost / pax * (1 + rng.uniform(0.05, 0.60)) / 10_000) * 10_000
            row = {
                "quote_date": quote_date.isoformat(), "departure_date": depart.isoformat(), "lead_days": lead,
                "pax": pax, "days": days, "segment": segment, "destination": dest,
                "weekend": int(flags["weekend"]), "holiday": int(flags["holiday"]), "tet": int(flags["tet"]),
                "month": flags["month"], "competitor_price_index": comp,
                "rain_prob": round(min(0.98, max(0.01, RAIN_BY_MONTH[depart.month - 1] + rng.gauss(0, 0.05))), 3),
                "response_time_h": round(min(72.0, rng.lognormvariate(1.2, 0.8)), 2),
                "cost_total_vnd": cost, "offered_price_per_pax": price_pp,
                "markup_pct": round((price_pp * pax / cost - 1) * 100, 2),
            }
            p = true_p_win(row, price_pp)
            row["true_p_win"] = round(p, 6)
            row["won"] = int(rng.random() < p)
            rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--start", type=date.fromisoformat, default=date(2023, 1, 1))
    ap.add_argument("--years", type=int, default=3)
    ap.add_argument("--per-day", type=int, default=20, help="mean quotes per day")
    ap.add_argument("--out", type=Path, default=Path("../../data/training/quote_win_synthetic.csv"))
    a = ap.parse_args()
    rows = generate(a.seed, a.start, a.years, a.per_day)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with a.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} quotes -> {a.out}  win rate {sum(r['won'] for r in rows) / len(rows):.3f}  mean true_p {sum(r['true_p_win'] for r in rows) / len(rows):.3f}")


if __name__ == "__main__":
    main()
