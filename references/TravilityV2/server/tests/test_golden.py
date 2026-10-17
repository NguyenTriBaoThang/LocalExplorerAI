from scripts import golden
from scripts.golden import PROMPTS, summarize, table


def test_summarize_counts_valid_and_averages():
    rows = [{"valid": True, "conflicts": 2, "seconds": 10.0, "calls": 12, "fallback": False},
            {"valid": True, "conflicts": 0, "seconds": 20.0, "calls": 14, "fallback": True},
            {"valid": False, "conflicts": 0, "seconds": 30.0, "calls": 4, "fallback": False}]
    assert summarize(rows) == {"n": 3, "valid_pct": 67, "conflicts": 1.0, "seconds": 20.0, "calls": 10.0,
                               "fallbacks": 1}
    assert summarize([])["valid_pct"] == 0


def test_table_has_one_row_per_mode():
    s = summarize([{"valid": True, "conflicts": 1, "seconds": 9.0, "calls": 13, "fallback": False}])
    out = table({"single": s, "multi": s})
    assert out.count("\n") == 4 and "| single | 1 | 100% | 1.0 | 9.0 | 13.0 | 0 |" in out


def test_eight_prompts():
    assert len(PROMPTS) == 8 and len(set(PROMPTS)) == 8


def test_throttle_waits_only_when_minute_window_is_full(monkeypatch):
    now, slept = [100.0], []

    def sleep(s):
        slept.append(s)
        now[0] += s

    monkeypatch.setattr(golden, "_now", lambda: now[0])
    monkeypatch.setattr(golden, "_sleep", sleep)
    t = golden.Throttle(2)
    assert t.acquire() == 0 and t.acquire() == 0 and slept == []
    assert t.acquire() == 61 and slept == [61]
    t.drain()  # trước prompt kế: chờ tới khi lượt gần nhất ra khỏi cửa sổ
    assert slept == [61, 61] and t.acquire() == 0
    assert golden.Throttle(0).acquire() == 0
