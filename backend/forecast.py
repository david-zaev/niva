"""Soil-moisture forecast: the one trained model in Niva (PLAN.md "The AI model").

What it predicts: how much top-soil moisture (0-7 cm, volumetric) changes between the last day with data and
1..H days later.

What it looks at:
- the soil now, its recent trend and where it sits in this place's own wet/dry range;
- the last 1-30 days of NASA POWER rain, heat, humidity, sun and wind;
- the season;
- and, the part the first version lacked, the weather in the days being forecast: rain, crop water use (FAO-56
  Hargreaves ET0) and heat between today and day h. Soil moisture is mostly what rain adds minus what the sun
  takes; a model that cannot see the coming rain can only guess "about the same", which is what v1 did.

One model serves every place and every horizon: each training row is (a day, a horizon h), so the model learns
from all three regions at once (3x the data) and knows h as an input. Gradient-boosted trees (scikit-learn
HistGradientBoosting). Two more models of the same kind give the 5th and 95th percentile, so the band is wide
when the coming weather makes the answer uncertain (a storm on day 4) and narrow when it does not.

The same feature code trains (data/scripts/train_model.py) and forecasts on the server.
"""
from functools import lru_cache
from math import acos, cos, pi, sin, tan, radians

import nasa

H = 14  # days ahead of the last day with data (POWER and ERA5-Land arrive 3-6 days late)

PAST = ["sm", "sm_rel", "sm_d3", "sm_d7", "rain_1", "rain_3", "rain_7", "rain_30", "et0_7", "et0_30",
        "balance_30", "tmax_7", "tmin_7", "hum_7", "solar_7", "wind_7", "doy_sin", "doy_cos"]
FUTURE = ["h", "fut_rain", "fut_et0", "fut_balance", "fut_rain_last3", "fut_rain_max", "fut_tmax"]
FEATURES = PAST + FUTURE
WEATHER_COLS = ["rain_mm", "et0", "t_max"]  # what the coming days must supply


def build_frame(df, sm_range):
    """df: daily rows indexed by date with rain_mm, t_max, t_min, humidity, solar, wind, et0, sm.
    sm_range: (p10, p90) of this place's soil moisture in the training years.
    Returns the past-and-present features, one row per day (NaN where a window is not complete)."""
    import pandas as pd
    df = df.asfreq("D")
    w = df.ffill(limit=2)  # one or two missing days (late POWER radiation) do not break a window
    f = pd.DataFrame(index=df.index)
    f["sm"] = df["sm"]
    lo, hi = sm_range
    f["sm_rel"] = (df["sm"] - lo) / (hi - lo)
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
    return f[PAST]


def future_features(rain, et0, tmax, h: int) -> dict:
    """Coming-days features from the daily weather of days 1..h after the anchor (lists, oldest first)."""
    r, e, t = rain[:h], et0[:h], tmax[:h]
    return {"h": h, "fut_rain": sum(r), "fut_et0": sum(e), "fut_balance": sum(r) - sum(e),
            "fut_rain_last3": sum(r[-3:]), "fut_rain_max": max(r), "fut_tmax": sum(t) / len(t)}


def future_frame(df, h: int):
    """Training version of future_features for every day at once (the days after each date are observed)."""
    import pandas as pd
    w = df.asfreq("D").ffill(limit=2)
    ahead = lambda s, n, how: getattr(s.rolling(n, min_periods=n), how)().shift(-n)  # days t+1..t+n
    f = pd.DataFrame(index=w.index)
    f["h"] = h
    f["fut_rain"] = ahead(w["rain_mm"], h, "sum")
    f["fut_et0"] = ahead(w["et0"], h, "sum")
    f["fut_balance"] = f["fut_rain"] - f["fut_et0"]
    f["fut_rain_last3"] = w["rain_mm"].rolling(min(3, h), min_periods=min(3, h)).sum().shift(-h)
    f["fut_rain_max"] = ahead(w["rain_mm"], h, "max")
    f["fut_tmax"] = ahead(w["t_max"], h, "mean")
    return f[FUTURE]


def extra_radiation(lat: float, doy: int) -> float:
    """FAO-56 eq. 21: extraterrestrial radiation Ra, MJ/m2/day (Hargreaves ET0 needs it)."""
    phi = radians(lat)
    dr = 1 + 0.033 * cos(2 * pi * doy / 365)
    d = 0.409 * sin(2 * pi * doy / 365 - 1.39)
    ws = acos(max(-1.0, min(1.0, -tan(phi) * tan(d))))
    return 24 * 60 / pi * 0.0820 * dr * (ws * sin(phi) * sin(d) + cos(phi) * cos(d) * sin(ws))


@lru_cache(maxsize=2)
def _load(mtime):
    import joblib
    return joblib.load(nasa.DATA_DIR / "model" / "soil_forecast.joblib")


def load():
    """{mid, low, high} models, or None until train_model.py has run."""
    path = nasa.DATA_DIR / "model" / "soil_forecast.joblib"
    return _load(path.stat().st_mtime) if path.exists() else None


def report() -> dict | None:
    return nasa.read_data_file("model/model_report.json")


def predict(location_id: str, df, coming) -> dict | None:
    """Forecast from the last day of `df` with complete inputs.
    df: daily history (see build_frame). coming: {date: {rain_mm, et0, t_max}} for the days after it, observed
    where NASA POWER already has them and forecast after that.
    Returns {anchor, sm, days: [{h, sm, low, high}], weather_days} in volumetric % (m3/m3 x 100)."""
    import pandas as pd
    models, rep = load(), report()
    if models is None or rep is None or location_id not in rep["locations"]:
        return None
    frame = build_frame(df, rep["locations"][location_id]["sm_range"]).dropna()
    if frame.empty:
        return None
    anchor = frame.index[-1]
    rain, et0, tmax = [], [], []
    for i in range(1, H + 1):
        w = coming.get((anchor + pd.Timedelta(days=i)).date())
        if not w or any(w.get(k) is None for k in WEATHER_COLS):
            break  # weather known only this far: forecast only this far
        rain.append(w["rain_mm"]), et0.append(w["et0"]), tmax.append(w["t_max"])
    if not rain:
        return None
    past = frame.iloc[-1].to_dict()
    X = pd.DataFrame([{**past, **future_features(rain, et0, tmax, h)} for h in range(1, len(rain) + 1)])[FEATURES]
    mid, lo, hi = (models[k].predict(X).tolist() for k in ("mid", "low", "high"))
    sm0 = float(past["sm"])
    days = []
    for i in range(len(rain)):
        m = sm0 + mid[i]
        a, b = sorted((sm0 + lo[i], sm0 + hi[i]))
        days.append({"h": i + 1, "sm": round(100 * m, 1),
                     "low": round(100 * max(0.0, min(a, m)), 1), "high": round(100 * max(b, m), 1)})
    return {"anchor": anchor.date(), "sm": round(100 * sm0, 1), "days": days}
