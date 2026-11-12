from app.services.quote.pricing import STEP, optimize

CTX = {"days": 1, "lead_days": 30, "segment": "family", "destination": "city", "month": 6, "competitor_price_index": 1.0}


def logistic(center=1.3, slope=8.0):
    # P falls as price/cost rises: monotone like the real model.
    return lambda f: 1 / (1 + 2.718281828 ** (slope * (f["price_ratio_cost"] - center)))


def run(cost=20_000_000, pax=20, floor=0.10, fn=None):
    return optimize(cost, pax, CTX, floor, fn or logistic())


def test_modes_ordered_and_above_floor():
    r = run()
    floor_pp = 20_000_000 / 20 * 1.10
    assert r["safe"]["price_per_pax"] <= r["balanced"]["price_per_pax"] <= r["max_profit"]["price_per_pax"]
    assert all(r[m]["price_per_pax"] >= floor_pp and r[m]["margin_pct"] > 0 for m in ("safe", "balanced", "max_profit"))
    assert r["safe"]["p_win"] >= 0.75


def test_max_profit_is_exact_argmax_and_ep_formula():
    r = run()
    best = max(r["curve"], key=lambda pt: pt["expected_profit"])
    assert r["max_profit"]["price_per_pax"] == best["price_per_pax"]
    pt = r["curve"][3]
    assert pt["expected_profit"] == pt["p_win"] * (pt["total"] - 20_000_000)
    # stub with a known optimum: P = 0.5 flat except one price that is clearly best
    target = r["curve"][7]["price_per_pax"]
    stub = optimize(20_000_000, 20, CTX, 0.10, lambda f: 0.9 if round(f["price_ratio_cost"] * 1_000_000) == target else 0.1)
    assert stub["max_profit"]["price_per_pax"] == target


def test_floor_bound_when_no_price_reaches_p():
    r = run(fn=lambda f: 0.4)
    assert r["safe"]["floor_bound"] and not r["max_profit"]["floor_bound"] and not r["balanced"]["floor_bound"]
    assert r["safe"]["price_per_pax"] == r["curve"][0]["price_per_pax"]


def test_grid_rounded_up_to_10k_and_bounded():
    r = optimize(19_999_999, 7, CTX, 0.12, logistic(), ceiling=1.8)
    prices = [pt["price_per_pax"] for pt in r["curve"]]
    assert all(p % STEP == 0 for p in prices)
    cost_pp = 19_999_999 / 7
    assert prices[0] >= cost_pp * 1.12 and prices[0] - STEP < cost_pp * 1.12
    assert prices[-1] <= cost_pp * 1.8 < prices[-1] + STEP  # explicit ceiling; top is rounded down, never above it
    assert all(b - a == STEP for a, b in zip(prices, prices[1:]))


def test_default_ceiling_is_training_support_and_never_exceeded():
    from app.services.quote.win_model import price_ratio_max

    cap = price_ratio_max()
    r = run(fn=lambda f: 0.9)  # P never falls, so an unbounded optimizer would pick the top of the grid
    assert all(pt["price_per_pax"] <= 1_000_000 * cap for pt in r["curve"])
    assert all(r[m]["price_per_pax"] <= 1_000_000 * cap for m in ("safe", "balanced", "max_profit"))
    wide = optimize(20_000_000, 20, CTX, 0.10, lambda f: 0.9, ceiling=2.0)  # explicit override still works
    assert wide["max_profit"]["price_per_pax"] > r["max_profit"]["price_per_pax"]


def test_balanced_is_highest_p_within_95pct_of_max_ep():
    r = run()
    max_ep = r["max_profit"]["expected_profit"]
    assert r["balanced"]["expected_profit"] >= 0.95 * max_ep
    near = [pt for pt in r["curve"] if pt["expected_profit"] >= 0.95 * max_ep and pt["price_per_pax"] >= r["safe"]["price_per_pax"]]
    assert r["balanced"]["p_win"] == max(pt["p_win"] for pt in near)
    assert r["balanced"]["p_win"] >= r["max_profit"]["p_win"]


def test_balanced_exact_on_stub_with_flat_top():
    # EP = p*(price-cost): p chosen so points 4,5,6 have EP 100, 98, 96 (all >=95% of max 100) and others far lower.
    base = optimize(20_000_000, 20, CTX, 0.10, lambda f: 0.5)["curve"]
    prices = [pt["price_per_pax"] for pt in base]
    ep = {prices[4]: 100.0, prices[5]: 98.0, prices[6]: 96.0}
    def stub(f):
        price = round(f["price_ratio_cost"] * 1_000_000)
        return ep[price] / ((price - 1_000_000) * 20) if price in ep else 1e-12

    r = optimize(20_000_000, 20, CTX, 0.10, stub)
    assert r["max_profit"]["price_per_pax"] == prices[4]
    assert r["balanced"]["price_per_pax"] == prices[4]  # highest P among {4,5,6} is the cheapest
