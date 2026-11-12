"""Price optimizer (M7 core): pure function, no LLM. EP = P(win) x (price - cost) x pax.

Grid: per-pax price from cost/pax x (1 + floor) to the model's price support (default: max price/cost seen in training), rounded UP to 10,000 VND at the floor, DOWN at the
ceiling so no price exceeds the support. floor_pct is a markup on cost
(0.10 = 10%). margin_pct in the output is margin on price: (total - cost) / total.
"""
from collections.abc import Callable
from math import ceil

from app.services.quote.win_model import build_features, price_ratio_max

STEP = 10_000
BALANCED_EP_SHARE = 0.95  # balanced = highest P(win) among prices keeping >= 95% of the max expected profit
SAFE_MIN_P = 0.75


def _up(x: float) -> int:
    return ceil(round(x / STEP, 9)) * STEP


def optimize(cost_total_vnd: float, pax: int, context_features: dict, floor_pct: float,
             p_win_fn: Callable[[dict], float], ceiling: float | None = None) -> dict:
    """p_win_fn receives the full feature dict (win_model.FEATURE_NAMES) and returns P(win)."""
    cost_pp = cost_total_vnd / pax
    # No extrapolation: beyond the training price range trees go flat and overestimate P(win), so the optimizer
    # would chase prices the model has never seen (backtest: x1.8 grid lost 14-23% vs fixed 25%).
    ceiling = price_ratio_max() if ceiling is None else ceiling
    first, last = _up(cost_pp * (1 + floor_pct)), int(round(cost_pp * ceiling, 6) // STEP) * STEP
    ctx = {**context_features, "pax": pax}
    curve = []
    for price in range(first, max(first, last) + 1, STEP):
        total = price * pax
        p = float(p_win_fn(build_features(ctx, cost_total_vnd, price)))
        curve.append({"price_per_pax": price, "total": total, "margin_pct": round((total - cost_total_vnd) / total * 100, 2),
                      "p_win": p, "expected_profit": p * (total - cost_total_vnd)})
    out = {"floor_pct": floor_pct, "curve": curve}
    best = max(curve, key=lambda pt: pt["expected_profit"])  # first max = lowest price on ties
    out["max_profit"] = {**best, "floor_bound": False}
    safe_ok = [pt for pt in curve if pt["p_win"] >= SAFE_MIN_P]  # none -> floor price
    out["safe"] = {**max(safe_ok, key=lambda pt: pt["expected_profit"]), "floor_bound": False} if safe_ok else {**curve[0], "floor_bound": True}
    near = [pt for pt in curve if pt["expected_profit"] >= BALANCED_EP_SHARE * best["expected_profit"]]
    bal = max(near, key=lambda pt: pt["p_win"])  # first max = lowest price on ties
    # Keep Safe <= Balanced: if Safe's own EP is already within the 95% band, Safe is at least as good a pick.
    out["balanced"] = {**(out["safe"] if bal["price_per_pax"] < out["safe"]["price_per_pax"] else bal), "floor_bound": False}
    return out
