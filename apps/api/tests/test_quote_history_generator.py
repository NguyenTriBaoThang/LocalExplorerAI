from datetime import date

from scripts.generate_quote_history import generate, true_p_win


def tiny(seed):
    return generate(seed, date(2023, 3, 1), 1, per_day=1)


def test_generator_is_deterministic_and_consistent():
    a, b = tiny(7), tiny(7)
    assert a == b and a != tiny(8)
    assert all(r["cost_total_vnd"] > 0 and 3 <= r["lead_days"] <= 120 and 5 <= r["markup_pct"] <= 61 for r in a)
    r = a[0]
    assert abs(true_p_win(r, r["offered_price_per_pax"]) - r["true_p_win"]) < 1e-6
    assert true_p_win(r, r["offered_price_per_pax"] * 1.3) < r["true_p_win"]
