import asyncio

from scripts.loadtest import measure, percentile, row, summarize


def test_percentile_is_nearest_rank():
    xs = [0.4, 0.1, 0.3, 0.2]
    assert percentile(xs, 0.5) == 0.2
    assert percentile(xs, 0.95) == 0.4
    assert percentile([0.7], 0.95) == 0.7
    assert percentile([], 0.5) == 0.0


def test_summary_counts_errors_and_rate_of_successes():
    s = summarize([0.1, 0.2, 0.3, 0.4], errors=1, wall=2.0)
    assert s == {"n": 5, "errors": 1, "p50_ms": 200, "p95_ms": 400, "rps": 2.0}
    assert summarize([], errors=3, wall=0.0) == {"n": 3, "errors": 3, "p50_ms": 0, "p95_ms": 0, "rps": 0.0}


def test_row_is_a_markdown_table_line():
    s = summarize([0.1], errors=0, wall=1.0)
    assert row("2 api", "mở Trip", s) == "| 2 api | mở Trip | 1 | 0 | 100 | 100 | 1.0 |"


def test_measure_never_runs_more_than_the_concurrency_limit():
    live, peak = 0, 0

    async def call(ok=True):
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await asyncio.sleep(0.01)
        live -= 1
        return ok

    s = asyncio.run(measure([call() for _ in range(9)] + [call(False)], concurrency=3))
    assert peak == 3
    assert (s["n"], s["errors"]) == (10, 1)
