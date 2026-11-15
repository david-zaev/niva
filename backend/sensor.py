"""What the ESP32 tells us: the soil test, the field's microclimate against NASA, live alerts and the season log.

Readings arrive every few seconds (demo) or minutes (field). Nothing here is a weather forecast: every alert comes
from what the sensor is measuring in the field now, and the thresholds are written next to each rule.
"""
from datetime import datetime, timedelta, timezone
import math

import numpy as np
import pandas as pd

import soil as soilmod


def _utc(t: datetime) -> datetime:
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def frame(readings) -> pd.DataFrame:
    if not readings:
        return pd.DataFrame(columns=["soil_pct", "soil2_pct", "soil_temp_c", "air_temp_c", "humidity_pct",
                                     "pressure_hpa"])
    df = pd.DataFrame([{"time": _utc(r.time), "soil_pct": r.soil_pct, "soil2_pct": getattr(r, "soil2_pct", None),
                        "soil_temp_c": r.soil_temp_c, "air_temp_c": r.air_temp_c,
                        "humidity_pct": r.humidity_pct, "pressure_hpa": r.pressure_hpa} for r in readings])
    return df.set_index("time").sort_index().astype(float)


def dew_point(t: float, rh: float) -> float | None:
    if t is None or rh is None or rh <= 0 or math.isnan(t) or math.isnan(rh):
        return None
    a, b = 17.62, 243.12
    g = math.log(rh / 100) + a * t / (b + t)
    return round(b * g / (a - g), 1)


# ---------- soil test ----------

def analyse_test(df: pd.DataFrame, started: datetime, ended: datetime | None, col: str = "soil_pct") -> dict:
    """Curve of soil moisture after pouring water: baseline, soak-in time, peak, drainage speed, settled value."""
    started = _utc(started)
    s = df[col].dropna() if col in df else pd.Series(dtype=float)
    before = s[(s.index >= started - timedelta(minutes=3)) & (s.index < started + timedelta(seconds=5))]
    after = s[(s.index >= started) & ((s.index <= _utc(ended)) if ended else True)]
    if len(after) < 4:
        return {"ok": False, "message": "Waiting for readings after the water was poured."}
    base = float(before.median()) if len(before) else float(after.iloc[0])
    peak_t = after.idxmax()
    peak = float(after.max())
    rise = peak - base
    if rise < 3:
        return {"ok": False, "message": "No rise in soil moisture yet: pour the water close to the probe.",
                "baseline": round(base, 1), "now": round(float(after.iloc[-1]), 1)}
    reach = after[after >= base + 0.9 * rise]
    rise_s = (reach.index[0] - started).total_seconds() if len(reach) else None
    tail = after[after.index >= peak_t]
    minutes_after_peak = (tail.index[-1] - peak_t).total_seconds() / 60 if len(tail) else 0
    drain_pct_h = None
    if len(tail) >= 4 and minutes_after_peak >= 2:
        hrs = (tail.index - peak_t).total_seconds() / 3600
        k = np.polyfit(hrs, tail.to_numpy(), 1)[0]
        drain_pct_h = round(max(0.0, -float(k)), 1)
    settle = float(tail.iloc[-5:].mean()) if len(tail) >= 5 else float(after.iloc[-1])
    settled = minutes_after_peak >= 8
    props = soilmod.from_test(rise_s, drain_pct_h, settle, settled)
    curve = [{"t": round((t - started).total_seconds()), "v": round(float(v), 1)} for t, v in after.items()]
    return {
        "ok": True, "baseline_pct": round(base, 1), "peak_pct": round(peak, 1), "rise_pct": round(rise, 1),
        "soak_in_s": None if rise_s is None else round(rise_s), "drain_pct_per_h": drain_pct_h,
        "settled_pct": round(settle, 1), "settled": settled, "minutes_after_peak": round(minutes_after_peak, 1),
        "soil": props, "curve": curve[-400:],
        "note": None if settled else "Keep the test running about 8 minutes after the peak for a field-capacity "
                                     "reading; until then the texture default is used.",
    }


def compare_pots(df: pd.DataFrame, started: datetime, ended: datetime | None) -> dict | None:
    """Bare pot (probe 1) against the covered pot (probe 2), when the second probe is wired."""
    if "soil2_pct" not in df or df["soil2_pct"].dropna().empty:
        return None
    a = analyse_test(df, started, ended, "soil_pct")
    b = analyse_test(df, started, ended, "soil2_pct")
    if not (a.get("ok") and b.get("ok")):
        return {"ok": False}
    return {"ok": True, "bare": {k: a[k] for k in ("soak_in_s", "drain_pct_per_h", "settled_pct", "curve")},
            "covered": {k: b[k] for k in ("soak_in_s", "drain_pct_per_h", "settled_pct", "curve")}}


# ---------- microclimate ----------

def microclimate(df: pd.DataFrame, weather: pd.DataFrame) -> dict:
    """Night temperature of the field against NASA POWER. Same-day comparison when the days overlap (POWER is
    published a few days late), otherwise against the 25-year NASA normal for the date."""
    t = df["air_temp_c"].dropna() if "air_temp_c" in df else pd.Series(dtype=float)
    if t.empty:
        return {"ok": False}
    local = t.tz_convert("Europe/Skopje")
    days = local.groupby(local.index.date)
    rows = []
    for d, s in days:
        span_h = (s.index[-1] - s.index[0]).total_seconds() / 3600
        rows.append({"date": d, "min": float(s.min()), "max": float(s.max()), "hours": span_h})
    full = [r for r in rows if r["hours"] >= 18]
    overlap = []
    for r in full:
        ts = pd.Timestamp(r["date"])
        if ts in weather.index and not np.isnan(weather.loc[ts, "t_min"]):
            overlap.append(r["min"] - float(weather.loc[ts, "t_min"]))
    out = {"ok": True, "days_measured": len(rows), "full_days": len(full)}
    if overlap:
        out.update(offset_c=round(float(np.mean(overlap)), 1), basis="same days in NASA POWER",
                   days_compared=len(overlap))
    now = local.index[-1]
    doy = now.dayofyear
    window = weather[(abs(weather.index.dayofyear - doy) <= 7)]
    out["now_c"] = round(float(local.iloc[-1]), 1)
    out["normal_min_c"] = round(float(window["t_min"].mean()), 1)
    out["normal_max_c"] = round(float(window["t_max"].mean()), 1)
    out["normal_mean_c"] = round(float(window["t_mean"].mean()), 1)
    if rows:
        out["today_min_c"] = round(rows[-1]["min"], 1)
        out["today_max_c"] = round(rows[-1]["max"], 1)
    return out


# ---------- live alerts ----------

def alerts(df: pd.DataFrame, crop: dict | None, soil: dict) -> list[dict]:
    """Alerts from the latest readings. level: act (now), watch (soon), ok."""
    out = []
    if df.empty:
        return out
    last = df.iloc[-1]
    now = df.index[-1]
    recent = lambda h: df[df.index >= now - timedelta(hours=h)]

    # water now: soil below the crop's stress threshold (fraction p of available water used)
    sp = last.get("soil_pct")
    if sp is not None and not math.isnan(sp):
        th = soilmod.theta(sp)
        avail = (th - soil["wp"]) / (soil["fc"] - soil["wp"])
        p = crop["p"] if crop else 0.5
        name = crop["name"].lower() if crop else "the crop"
        if avail < 1 - p:
            out.append({"id": "water", "level": "act", "title": "Water now",
                        "text": f"The soil holds {max(0, round(100 * avail))}% of its available water; {name} is "
                                f"stressed below {round(100 * (1 - p))}%.",
                        "rule": f"available water < {round(100 * (1 - p))}% (FAO-56 p = {p})"})
        elif avail < 1 - p + 0.15:
            out.append({"id": "water", "level": "watch", "title": "Water soon",
                        "text": f"Available water {round(100 * avail)}%: plan to irrigate in the next days.",
                        "rule": f"within 15 points of the stress threshold ({round(100 * (1 - p))}%)"})
        if avail > 1.15:
            r12 = recent(12)["soil_pct"].dropna()
            if len(r12) > 3 and (soilmod.theta(r12.min()) - soil["wp"]) / (soil["fc"] - soil["wp"]) > 1.15 \
                    and (r12.index[-1] - r12.index[0]) >= timedelta(hours=6):
                out.append({"id": "waterlog", "level": "watch", "title": "Waterlogged soil",
                            "text": "Soil has stayed above field capacity for hours: roots lack air. Avoid irrigating and "
                                    "driving on the field.", "rule": "above field capacity for 6+ hours"})

    # frost tonight: low and falling air temperature with a low dew point (clear, dry nights cool fastest)
    at, rh = last.get("air_temp_c"), last.get("humidity_pct")
    dp = dew_point(at, rh)
    r3 = recent(3)["air_temp_c"].dropna()
    falling = len(r3) > 3 and (r3.iloc[-1] - r3.iloc[0]) < -1.0
    if at is not None and not math.isnan(at):
        if at <= 0.5:
            out.append({"id": "frost", "level": "act", "title": "Frost now",
                        "text": f"Air at {at:.1f} °C in the field: cover seedlings or run frost irrigation.",
                        "rule": "air temperature ≤ 0.5 °C"})
        elif at <= 5 and (falling or (dp is not None and dp <= 1)):
            out.append({"id": "frost", "level": "watch", "title": "Frost risk tonight",
                        "text": f"Air {at:.1f} °C" + (" and falling" if falling else "")
                                + (f", dew point {dp:.1f} °C" if dp is not None else "")
                                + ": the field can reach 0 °C before dawn. Protect young plants.",
                        "rule": "air ≤ 5 °C and falling > 1 °C in 3 h, or dew point ≤ 1 °C"})

    # front coming: pressure falling fast (classic barometer rule, ~3 hPa in 3 hours)
    pr = recent(3)["pressure_hpa"].dropna()
    if len(pr) > 3 and (pr.index[-1] - pr.index[0]) >= timedelta(minutes=20):
        hours = (pr.index[-1] - pr.index[0]).total_seconds() / 3600
        rate = (pr.iloc[-1] - pr.iloc[0]) / hours * 3
        if rate <= -3:
            out.append({"id": "storm", "level": "act", "title": "Storm front coming",
                        "text": f"Pressure falling {abs(rate):.1f} hPa per 3 hours: wind and heavy rain likely within "
                                f"hours. Secure covers and delay spraying.", "rule": "pressure drop ≥ 3 hPa / 3 h"})
        elif rate <= -1.5:
            out.append({"id": "storm", "level": "watch", "title": "Weather turning",
                        "text": f"Pressure falling {abs(rate):.1f} hPa per 3 hours.", "rule": "pressure drop ≥ 1.5 hPa / 3 h"})

    # heat stress: hot air on dry soil
    if at is not None and not math.isnan(at) and at >= 35:
        out.append({"id": "heat", "level": "act", "title": "Heat stress",
                    "text": f"Air {at:.1f} °C: flowers of pepper and tomato drop above 35 °C. Irrigate early morning, "
                            f"shade if possible.", "rule": "air ≥ 35 °C"})

    # disease weather: warm and very humid for hours (blights and mildews on nightshades)
    r12 = recent(12)
    wet = r12[(r12["humidity_pct"] >= 90) & (r12["air_temp_c"].between(10, 25))]
    if len(r12) > 5:
        frac = len(wet) / len(r12)
        hrs = frac * min(12.0, (r12.index[-1] - r12.index[0]).total_seconds() / 3600)
        if hrs >= 6:
            out.append({"id": "disease", "level": "watch", "title": "Disease weather",
                        "text": f"About {hrs:.0f} of the last 12 hours were humid (≥ 90%) and mild (10-25 °C): "
                                f"late blight and downy mildew spread. Check leaves.",
                        "rule": "≥ 6 h with humidity ≥ 90 % and 10-25 °C"})
    return out


def season_log(df: pd.DataFrame) -> dict:
    """How often the alert conditions happened in the readings so far, per day. Feeds the next rotation choice."""
    if df.empty:
        return {"days": 0}
    local = df.tz_convert("Europe/Skopje")
    g = local.groupby(local.index.date)
    frost = int((g["air_temp_c"].min() <= 0.5).sum())
    heat = int((g["air_temp_c"].max() >= 35).sum())
    humid = local[(local["humidity_pct"] >= 90) & (local["air_temp_c"].between(10, 25))]
    disease_days = int(len(set(humid.index.date)))
    p = local["pressure_hpa"].dropna()
    fronts = 0
    if len(p) > 10:
        p3 = p.resample("1h").mean().dropna()
        fronts = int(((p3 - p3.shift(3)) <= -3).sum())
    return {"days": int(g.ngroups), "frost_days": frost, "heat_days": heat, "disease_days": disease_days,
            "pressure_drops": fronts, "first": local.index[0].isoformat(), "last": local.index[-1].isoformat()}
