"""Train the SYNTHETIC quote win-probability model (M6) -> models/quote-win/. Needs requirements-ml.txt.

    python -m scripts.train_quote_win_model [--data ../../data/training/quote_win_synthetic.csv] [--out ../../models/quote-win]

Leakage rules: features come only from win_model.build_features (quote-time data; competitor index and rain
probability are treated as known at quote time). true_p_win, won, markup_pct, offered_total never enter X.
Split is by quote_date, never shuffled: first 24 months train, next 6 validation (early stopping + small grid),
last 6 test (scored once).
"""
import argparse
import hashlib
import itertools
import json
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

from app.services.quote.win_model import FEATURE_NAMES, FEATURE_VERSION, PRICE_FEATURES, build_features

SEED = 42
CTX_KEYS = ("pax", "days", "lead_days", "segment", "destination", "weekend", "holiday", "tet", "month",
            "competitor_price_index", "rain_prob", "response_time_h")
GRID = {"max_depth": (2, 3, 4), "min_child_weight": (5, 30)}


def add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def featurize(df: pd.DataFrame) -> np.ndarray:
    rows = (build_features({k: r[k] for k in CTX_KEYS}, r["cost_total_vnd"], r["offered_price_per_pax"]) for r in df.to_dict("records"))
    return np.array([[f[n] for n in FEATURE_NAMES] for f in rows], dtype=float)


def calibration(p, y, p_true, bins=10) -> list[dict]:
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return [{"bin": f"{b / bins:.1f}-{(b + 1) / bins:.1f}", "n": int(m.sum()), "mean_p_hat": float(p[m].mean()),
             "observed_win_rate": float(y[m].mean()), "mean_true_p": float(p_true[m].mean())}
            for b in range(bins) if (m := idx == b).any()]


def scores(p, y, p_true) -> dict:
    return {"auc": roc_auc_score(y, p), "brier": brier_score_loss(y, p), "log_loss": log_loss(y, p),
            "mean_abs_err_vs_true_p": float(np.abs(p - p_true).mean()), "n": int(len(y)), "win_rate": float(y.mean())}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, default=Path("../../data/training/quote_win_synthetic.csv"))
    ap.add_argument("--out", type=Path, default=Path("../../models/quote-win"))
    a = ap.parse_args()
    df = pd.read_csv(a.data)
    qd = pd.to_datetime(df["quote_date"]).dt.date
    t0 = qd.min().replace(day=1)
    train_end, val_end = add_months(t0, 24), add_months(t0, 30)
    split = {"train": qd < train_end, "val": (qd >= train_end) & (qd < val_end), "test": qd >= val_end}
    assert all(m.any() for m in split.values()), "need >30 months of data for the 24/6/6 split"
    X, y, p_true = featurize(df), df["won"].to_numpy(), df["true_p_win"].to_numpy()
    part = {k: (X[m.to_numpy()], y[m.to_numpy()], p_true[m.to_numpy()]) for k, m in split.items()}
    mono = tuple(-1 if n in PRICE_FEATURES else 0 for n in FEATURE_NAMES)

    best = None
    for depth, mcw in itertools.product(*GRID.values()):
        clf = xgb.XGBClassifier(n_estimators=800, learning_rate=0.05, max_depth=depth, min_child_weight=mcw, subsample=0.8,
                                colsample_bytree=0.8, reg_lambda=2.0, monotone_constraints=mono, eval_metric="logloss",
                                early_stopping_rounds=40, random_state=SEED, n_jobs=1)
        clf.fit(part["train"][0], part["train"][1], eval_set=[part["val"][:2]], verbose=False)
        ll = clf.best_score
        print(f"depth={depth} mcw={mcw} val_logloss={ll:.4f} trees={clf.best_iteration + 1}")
        if best is None or ll < best[0]:
            best = (ll, clf, {"max_depth": depth, "min_child_weight": mcw, "n_estimators": clf.best_iteration + 1})
    _, clf, params = best

    metrics = {"validation": scores(clf.predict_proba(part["val"][0])[:, 1], part["val"][1], part["val"][2])}
    p_test = clf.predict_proba(part["test"][0])[:, 1]
    metrics["test"] = scores(p_test, part["test"][1], part["test"][2])
    metrics["test"]["calibration_10_bins"] = calibration(p_test, part["test"][1], part["test"][2])
    metrics["test_oracle_true_p"] = {"auc": roc_auc_score(part["test"][1], part["test"][2]),
                                     "brier": brier_score_loss(part["test"][1], part["test"][2]),
                                     "log_loss": log_loss(part["test"][1], part["test"][2])}
    metrics["chosen_params"] = params

    a.out.mkdir(parents=True, exist_ok=True)
    model_path = a.out / "xgboost_win.json"
    clf.save_model(model_path)
    sha = hashlib.sha256(model_path.read_bytes()).hexdigest()
    trained_at = datetime.now(timezone.utc)
    meta = {
        "model_version": f"quote-win-xgb-synthetic-{trained_at:%Y%m%dT%H%M%SZ}", "model_family": "xgboost",
        "model_file": "xgboost_win.json", "model_sha256": sha, "feature_version": FEATURE_VERSION,
        "feature_names": FEATURE_NAMES, "monotone_constraints": dict(zip(FEATURE_NAMES, mono)),
        "dataset_status": "synthetic", "deployment_eligible": False, "production_eligible": False,
        "warning": "Trained on SYNTHETIC quote history; probabilities are not market evidence.",
        "source_dataset": a.data.name, "source_dataset_sha256": hashlib.sha256(a.data.read_bytes()).hexdigest(),
        # optimizer must not extrapolate beyond the prices seen in training (trees go flat and overestimate P)
        "price_support": {f"{n}_{k}": float(fn(X[split['train'].to_numpy(), FEATURE_NAMES.index(n)])) for n in ("price_ratio_cost",) for k, fn in (("min", np.min), ("max", np.max))},
        "trained_at": trained_at.isoformat(), "seed": SEED, "model_parameters": params,
        "split": {"train": [str(t0), str(train_end)], "validation": [str(train_end), str(val_end)],
                  "test": [str(val_end), str(qd.max())], "rows": {k: int(m.sum()) for k, m in split.items()}},
    }
    (a.out / "model_metadata.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (a.out / "feature_schema.json").write_text(json.dumps({
        "feature_version": FEATURE_VERSION, "feature_names": FEATURE_NAMES,
        "feature_builder": "apps/api/app/services/quote/win_model.py::build_features",
        "price_dependent_features": list(PRICE_FEATURES),
        "excluded_label_or_truth_columns": ["won", "true_p_win", "markup_pct", "offered_total", "offered_price_per_pax"],
    }, indent=2) + "\n", encoding="utf-8")
    (a.out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    t, o = metrics["test"], metrics["test_oracle_true_p"]
    (a.out / "model_card.md").write_text(f"""# Quote win model (SYNTHETIC)

> **DỮ LIỆU GIẢ LẬP.** Mô hình này chỉ học từ lịch sử báo giá sinh bằng `scripts/generate_quote_history.py`
> (xem `docs/quote-pricing-ground-truth.md`). `dataset_status=synthetic`, `deployment_eligible=false`.
> Xác suất chốt tour ở đây KHÔNG phải bằng chứng thị trường; chỉ dùng để demo và kiểm thử optimizer.

- Phiên bản: `{meta['model_version']}` (XGBoost, `{FEATURE_VERSION}`), sha256 `{sha[:16]}...`
- Mục tiêu: dự đoán P(chốt) cho một báo giá tại một mức giá; đầu vào chỉ gồm thông tin có tại thời điểm báo giá
  (đoàn, ngày đi, lead time, cờ lễ/Tết/cuối tuần, chỉ số giá đối thủ, xác suất mưa, thời gian phản hồi, giá/giá vốn).
  Chỉ số giá đối thủ và xác suất mưa được coi là đã biết lúc báo giá.
- Ràng buộc đơn điệu: P giảm khi `price_ratio_cost`, `price_ratio_comp` tăng.
- Chia theo thời gian (không xáo trộn): train {meta['split']['train'][0]}..{meta['split']['train'][1]} ({meta['split']['rows']['train']} dòng),
  validation ..{meta['split']['validation'][1]} ({meta['split']['rows']['val']}), test ..{meta['split']['test'][1]} ({meta['split']['rows']['test']}).
  Tham số chọn theo log loss trên validation: {params}.

## Kết quả trên tập test
| | AUC | Brier | Log loss | |p_hat - p_thật| |
|---|---|---|---|---|
| Mô hình | {t['auc']:.4f} | {t['brier']:.4f} | {t['log_loss']:.4f} | {t['mean_abs_err_vs_true_p']:.4f} |
| Oracle (P thật) | {o['auc']:.4f} | {o['brier']:.4f} | {o['log_loss']:.4f} | 0 |

Bảng calibration 10 bin nằm trong `metrics.json`.

## Hạn chế
- P thật do chúng tôi tự đặt (hàm sigmoid có hệ số cố định); mô hình chỉ khôi phục lại chính quy luật đó.
- Không có hành vi khách thật, không có đối thủ thật, giá vốn lấy từ bảng giá seed.
- Không được dùng để ra quyết định giá thật cho tới khi huấn luyện lại bằng lịch sử báo giá thật của nhà điều hành.

<!-- backtest -->
""", encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in ("validation", "chosen_params")}, indent=1))
    print("TEST", json.dumps({k: v for k, v in t.items() if k != "calibration_10_bins"}), "ORACLE", json.dumps(o))
    for row in t["calibration_10_bins"]:
        print(row)


if __name__ == "__main__":
    main()
