"""P(win) for a quote at a given price. Loads models/quote-win (verifying sha256 + feature list, like
MLRankerService._load); any problem -> logistic heuristic with source="heuristic". xgboost/numpy are optional.

The bundle is trained on SYNTHETIC data (deployment_eligible=false): treat outputs as a demo, not as market truth.
"""
import hashlib
import json
import math
import os
from pathlib import Path

SEGMENTS = ("family", "corporate", "school")
DESTINATIONS = ("cu_chi", "mekong", "can_gio", "vung_tau", "city")
FEATURE_VERSION = "quote-win-features-v1"
FEATURE_NAMES = [
    "pax", "days", "lead_days", *(f"seg_{s}" for s in SEGMENTS), *(f"dest_{d}" for d in DESTINATIONS),
    "weekend", "holiday", "tet", "month", "competitor_price_index", "rain_prob", "response_time_h",
    "cost_per_pax", "price_ratio_cost", "price_ratio_comp",
]
PRICE_FEATURES = ("price_ratio_cost", "price_ratio_comp")  # the only price-dependent features; monotone -1
def _default_dir() -> Path:
    """Same lookup as config._default_ranker_model_dir: the /models mount in Docker, else <repo>/models."""
    if os.environ.get("QUOTE_WIN_MODEL_DIR"):
        return Path(os.environ["QUOTE_WIN_MODEL_DIR"])
    if os.name != "nt" and Path("/models/quote-win").is_dir():
        return Path("/models/quote-win")
    from app.core.config import _PROJECT_ROOT
    return _PROJECT_ROOT / "models" / "quote-win"


DEFAULT_DIR = _default_dir()


DEFAULT_PRICE_RATIO_MAX = 1.6  # heuristic fallback: the synthetic data's max markup (60%)


def build_features(ctx: dict, cost_total_vnd: float, price_per_pax: float) -> dict:
    """Quote-time features only. ctx: pax, days, lead_days, segment, destination, weekend, holiday, tet, month,
    competitor_price_index, rain_prob, response_time_h."""
    cost_pp = cost_total_vnd / ctx["pax"]
    comp = ctx.get("competitor_price_index", 1.0)
    f = {k: ctx.get(k, 0) for k in ("pax", "days", "lead_days", "weekend", "holiday", "tet", "month", "rain_prob", "response_time_h")}
    f.update({f"seg_{s}": int(ctx.get("segment") == s) for s in SEGMENTS})
    f.update({f"dest_{d}": int(ctx.get("destination") == d) for d in DESTINATIONS})
    f.update(competitor_price_index=comp, cost_per_pax=cost_pp,
             price_ratio_cost=price_per_pax / cost_pp, price_ratio_comp=price_per_pax / (cost_pp * comp))
    return f


def _heuristic(f: dict) -> float:
    # Generic prior, NOT fitted to the synthetic truth: logistic in price vs the 25%-markup reference.
    rel = f.get("price_ratio_comp", 1.25) / 1.25 - 1
    z = 0.0 - 5.0 * rel - 0.3 * math.log1p(f.get("response_time_h", 0)) + 0.3 * (f.get("holiday", 0) or f.get("tet", 0))
    return 1 / (1 + math.exp(-z))


class WinModel:
    def __init__(self, bundle_dir: Path | str | None = None):
        self.dir = Path(bundle_dir) if bundle_dir else DEFAULT_DIR
        self.metadata: dict = {}
        self.error: str | None = None
        self._booster = None
        self._names = FEATURE_NAMES
        self._load()

    @property
    def price_ratio_max(self) -> float:
        """Highest price/cost seen in training; the optimizer must not offer prices above it."""
        return self.metadata.get("price_support", {}).get("price_ratio_cost_max", DEFAULT_PRICE_RATIO_MAX)

    @property
    def source(self) -> str:
        return "model" if self._booster is not None else "heuristic"

    def _load(self) -> None:
        try:
            meta = json.loads((self.dir / "model_metadata.json").read_text(encoding="utf-8"))
            schema = json.loads((self.dir / "feature_schema.json").read_text(encoding="utf-8"))
            file = meta.get("model_file", "xgboost_win.json")
            if Path(file).name != file:
                raise ValueError("model_file must be a bare filename")
            blob = (self.dir / file).read_bytes()
            if hashlib.sha256(blob).hexdigest() != str(meta.get("model_sha256", "")).lower():
                raise ValueError("model SHA-256 does not match metadata; refusing to load")
            if not (meta.get("feature_names") == schema.get("feature_names") == FEATURE_NAMES
                    and meta.get("feature_version") == schema.get("feature_version") == FEATURE_VERSION):
                raise ValueError("feature list/version mismatch between bundle and code")
            import xgboost as xgb  # optional runtime dep

            booster = xgb.Booster()
            booster.load_model(bytearray(blob))
            self._booster, self.metadata = booster, meta
        except Exception as error:  # missing bundle, bad hash, no xgboost... -> heuristic
            self.error = f"{type(error).__name__}: {error}"

    def predict(self, features: dict | list | tuple) -> dict:
        row = dict(zip(self._names, features)) if isinstance(features, (list, tuple)) else features
        if self._booster is None:
            return {"p_win": _heuristic(row), "source": "heuristic"}
        import numpy as np
        import xgboost as xgb

        x = xgb.DMatrix(np.array([[float(row[n]) for n in self._names]]), feature_names=None)
        return {"p_win": float(self._booster.predict(x)[0]), "source": "model",
                "model_version": self.metadata.get("model_version")}


_default: WinModel | None = None


def predict_p_win(features: dict | list | tuple, model: WinModel | None = None) -> dict:
    global _default
    if model is None:
        _default = _default or WinModel()
        model = _default
    return model.predict(features)


def price_ratio_max(model: WinModel | None = None) -> float:
    global _default
    if model is None:
        _default = _default or WinModel()
        model = _default
    return model.price_ratio_max
