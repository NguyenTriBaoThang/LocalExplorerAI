"""Backtest the price optimizer on the TEST period with the exact synthetic P(win) (counterfactual is exact).

    python -m scripts.backtest_quote_pricing   # after train_quote_win_model; writes backtest.json + model_card.md section
"""
import argparse
import csv
import json
from pathlib import Path

from app.services.quote.pricing import STEP, optimize
from app.services.quote.win_model import WinModel, build_features
from scripts.generate_quote_history import REF_MARKUP, true_p_win
from scripts.train_quote_win_model import CTX_KEYS

FLOOR = 0.10  # minimum markup on cost
NUM = {"pax", "days", "lead_days", "weekend", "holiday", "tet", "month", "cost_total_vnd"}
FLT = {"competitor_price_index", "rain_prob", "response_time_h"}


def load(path: Path, start: str) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        rows = [r for r in csv.DictReader(f) if r["quote_date"] >= start]
    for r in rows:
        for k in NUM:
            r[k] = int(r[k])
        for k in FLT:
            r[k] = float(r[k])
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("../../data/training/quote_win_synthetic.csv"))
    ap.add_argument("--bundle", type=Path, default=Path("../../models/quote-win"))
    a = ap.parse_args()
    model = WinModel(a.bundle)
    assert model.source == "model", f"bundle did not load: {model.error}"
    cap = model.price_ratio_max
    rows = load(a.data, model.metadata["split"]["test"][0])
    acc = {k: {"expected_profit_vnd": 0.0, "p_sum": 0.0, "margin_sum": 0.0, "margin_p_sum": 0.0, "model_est_profit_vnd": 0.0}
           for k in ("fixed_25pct_markup", "optimizer_balanced", "optimizer_max_profit", "oracle_max_profit_true_p", "legacy_balanced_grid_1.80_unsupported", "legacy_max_profit_grid_1.80_unsupported")}

    def add(name, row, price_pp, est_profit=None):
        cost, pax = row["cost_total_vnd"], row["pax"]
        p = true_p_win(row, price_pp)
        total = price_pp * pax
        m = (total - cost) / total * 100
        s = acc[name]
        s["expected_profit_vnd"] += p * (total - cost)
        s["p_sum"] += p
        s["margin_sum"] += m
        s["margin_p_sum"] += p * m
        s["model_est_profit_vnd"] += est_profit if est_profit is not None else 0.0

    for r in rows:
        cost, pax = r["cost_total_vnd"], r["pax"]
        ctx = {k: r[k] for k in CTX_KEYS}
        add("fixed_25pct_markup", r, -(-round(cost / pax * REF_MARKUP, 6) // STEP) * STEP)
        res = optimize(cost, pax, ctx, FLOOR, lambda f: model.predict(f)["p_win"], ceiling=cap)
        add("optimizer_balanced", r, res["balanced"]["price_per_pax"], res["balanced"]["expected_profit"])
        add("optimizer_max_profit", r, res["max_profit"]["price_per_pax"], res["max_profit"]["expected_profit"])
        # what went wrong before the support cap: a x1.8 grid extrapolates beyond the training prices
        wide = optimize(cost, pax, ctx, FLOOR, lambda f: model.predict(f)["p_win"], ceiling=1.8)
        add("legacy_balanced_grid_1.80_unsupported", r, wide["balanced"]["price_per_pax"], wide["balanced"]["expected_profit"])
        add("legacy_max_profit_grid_1.80_unsupported", r, wide["max_profit"]["price_per_pax"], wide["max_profit"]["expected_profit"])
        true_res = optimize(cost, pax, ctx, FLOOR, lambda f, r=r: true_p_win(r, f["price_ratio_cost"] * cost / pax), ceiling=cap)
        add("oracle_max_profit_true_p", r, true_res["max_profit"]["price_per_pax"])

    n = len(rows)
    out = {"period": [model.metadata["split"]["test"][0], model.metadata["split"]["test"][1]], "quotes": n, "floor_markup_pct": FLOOR * 100,
           "note": "expected values under the TRUE synthetic P(win); margin_pct = (price-cost)/price",
           "strategies": {k: {"expected_profit_vnd": round(s["expected_profit_vnd"]),
                              "expected_profit_per_quote_vnd": round(s["expected_profit_vnd"] / n),
                              "expected_win_rate": round(s["p_sum"] / n, 4),
                              "avg_margin_pct_offered": round(s["margin_sum"] / n, 2),
                              "avg_margin_pct_on_wins": round(s["margin_p_sum"] / s["p_sum"], 2),
                              **({"model_estimated_profit_vnd": round(s["model_est_profit_vnd"])} if s["model_est_profit_vnd"] else {})}
                          for k, s in acc.items()}}
    (a.bundle / "backtest.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    base = out["strategies"]["fixed_25pct_markup"]["expected_profit_vnd"]
    lines = ["## Backtest (tập test, P thật của dữ liệu giả lập)", "",
             f"{n} báo giá, sàn markup {FLOOR:.0%}. Kỳ vọng tính bằng P thật nên phản thực tế là chính xác.", "",
             "| Chiến lược | Lợi nhuận kỳ vọng (VND) | so với markup 25% | Tỉ lệ chốt kỳ vọng | Biên TB chào giá | Biên TB khi chốt |", "|---|---|---|---|---|---|"]
    lines += [f"| {k} | {s['expected_profit_vnd']:,} | {s['expected_profit_vnd'] / base - 1:+.1%} | {s['expected_win_rate']:.1%} | "
              f"{s['avg_margin_pct_offered']:.1f}% | {s['avg_margin_pct_on_wins']:.1f}% |" for k, s in out["strategies"].items()]
    lines += ['', 'Optimizer mặc định giới hạn lưới giá ở `price_support.price_ratio_cost_max` (giá/vốn lớn nhất trong tập train). Hai dòng `legacy_*_grid_1.80_unsupported` là phiên bản đầu dùng lưới tới x1,8: nó THUA markup cố định 25% vì dữ liệu huấn luyện chỉ có markup 5-60%; ngoài vùng đó cây quyết định ngoại suy phẳng và đánh giá P quá cao (`model_estimated_profit_vnd` gần gấp đôi lợi nhuận thật ở chế độ max_profit). Nguyên nhân gốc là ngoại suy, nên optimizer không bao giờ chào giá ngoài vùng hỗ trợ. Chế độ cân bằng: trong các mức giá giữ được >= 95% lợi nhuận kỳ vọng tối đa, chọn mức có P chốt cao nhất.']
    card = a.bundle / "model_card.md"
    card.write_text(card.read_text(encoding="utf-8").split("<!-- backtest -->")[0] + "<!-- backtest -->\n" + "\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
