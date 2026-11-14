"""Soil-moisture forecast: the one trained model in Niva (PLAN.md "The AI model").

A random forest predicts how top-soil moisture (0-7 cm, volumetric) changes over the next 1..H days from what is
known today: the soil moisture now and its recent trend, NASA POWER rain, heat, humidity, sun and wind over the last
1-30 days, and the season. It predicts the change, not the level, so it never has to extrapolate a level it has
not seen. The same feature code is used to train (data/scripts/train_model.py) and to forecast on the server.
"""
from functools import lru_cache
from math import cos, pi, sin

import nasa

H = 14  # days ahead from the last day with data (POWER and ERA5-Land arrive 3-6 days late)

FEATURES = ["sm", "sm_d3", "sm_d7", "rain_1", "rain_3", "rain_7", "rain_30", "et0_7", "et0_30", "balance_30",
            "tmax_7", "tmin_7", "hum_7", "solar_7", "wind_7", "doy_sin", "doy_cos"]


def build_frame(df):
    """df: daily rows indexed by date with rain_mm, t_max, t_min, humidity, solar, wind, et0, sm.
    Returns the feature table (one row per day; NaN where a window is not complete)."""
    import pandas as pd
    df = df.asfreq("D")
    w = df.ffill(limit=2)  # one or two missing days (late POWER radiation) do not break a window
    f = pd.DataFrame(index=df.index)
    f["sm"] = df["sm"]
    f["sm_d3"] = df["sm"] - df["sm"].shift(3)
    f["sm_d7"] = df["sm"] - df["sm"].shift(7)
    for n in (1, 3, 7, 30):
        f[f"rain_{n}"] = w["rain_mm"].rolling(n, min_periods=n).sum()
    f["et0_7"] = w["et0"].rolling(7, min_periods=6).mean() * 7
    f["et0_30"] = w["et0"].rolling(30, min_periods=27).mean() * 30
    f["balance_30"] = f["rain_30"] - f["et0_30"]
    f["tmax_7"] = w["t_max"].rolling(7, min_periods=6).mean()
    f["tmin_7"] = w["t_min"].rolling(7, min_periods=6).mean()
    f["hum_7"] = w["humidity"].rolling(7, min_periods=6).mean()
    f["solar_7"] = w["solar"].rolling(7, min_periods=6).mean()
    f["wind_7"] = w["wind"].rolling(7, min_periods=6).mean()
    doy = df.index.dayofyear
    f["doy_sin"] = [sin(2 * pi * d / 365.25) for d in doy]
    f["doy_cos"] = [cos(2 * pi * d / 365.25) for d in doy]
    return f[FEATURES]


def build_targets(df):
    """Change in soil moisture 1..H days later (column h1..hH)."""
    import pandas as pd
    sm = df["sm"].asfreq("D")
    return pd.DataFrame({f"h{h}": sm.shift(-h) - sm for h in range(1, H + 1)})


def tree_spread(model, x):
    """10th-90th percentile of the individual trees' answers, per horizon (shape: H x 2)."""
    import numpy as np
    per_tree = np.stack([t.predict(x.to_numpy()) for t in model.estimators_])  # trees x rows x H
    return np.percentile(per_tree[:, 0, :], [10, 90], axis=0).T


@lru_cache(maxsize=8)
def load(location_id: str):
    """The trained model for a demo location, or None until train_model.py has run."""
    path = nasa.DATA_DIR / "model" / f"soil_forecast_{location_id}.joblib"
    if not path.exists():
        return None
    import joblib
    return joblib.load(path)


def report() -> dict | None:
    return nasa.read_data_file("model/model_report.json")


def predict(location_id: str, frame) -> dict | None:
    """Forecast from the last complete row of `frame` (from build_frame).
    Returns {anchor: date, sm: now, days: [{h, sm, low, high}]} in volumetric % (m3/m3 x 100)."""
    model = load(location_id)
    rep = report()
    if model is None or rep is None:
        return None
    ok = frame.dropna()
    if ok.empty:
        return None
    anchor = ok.index[-1]
    x = ok.iloc[[-1]]
    delta = model.predict(x)[0]
    # Band: 10th-90th percentile of the model's own errors on the test years (2023-2024), per horizon. That band
    # held about 80% of real values in those years; the trees' spread alone is reported in model_report.json.
    q = rep["locations"][location_id]["test"]["error_quantiles"]
    sm0 = float(x["sm"].iloc[0])
    days = []
    for h in range(1, H + 1):
        mid = sm0 + float(delta[h - 1])
        lo, hi = q[h - 1]
        days.append({"h": h, "sm": round(100 * mid, 1),
                     "low": round(100 * max(0.0, mid + lo), 1), "high": round(100 * (mid + hi), 1)})
    return {"anchor": anchor.date(), "sm": round(100 * sm0, 1), "days": days}
