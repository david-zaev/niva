"""Pest and disease warnings (Main_Prompt section 5): regional crop pest list (data/pests.json) x NASA POWER
weather at the field point x the field sensor (air temperature, humidity, pressure, soil moisture and temperature)
x the 7-day forecast, plus what the farmer reported seeing.

Each rule counts "favourable days" with thresholds from the model named in pests.json, over the last 7 days of
NASA POWER data and the next 3 forecast days. 3+ such days = high, 1-2 = medium, 0 = low. A fresh sensor reading
or a falling barometer can raise a level by one; the reasons are returned so the app can show them.
"""
from datetime import date, timedelta

from sqlmodel import Session, select

import insights
import nasa
from models import FieldRow, PestReport, Planting

LEVELS = ["low", "medium", "high"]
FUNGAL = {"late_blight", "powdery_mildew", "rust", "fusarium", "downy_mildew", "wet_leaf"}
DRY_PESTS = {"spider_mite", "thrips", "tuta", "aphids"}


def in_season(crop: dict, month: int) -> bool:
    """True from the first sowing month to the last harvest month (wrapping over the new year)."""
    sow, harvest = crop.get("sow_months") or [], crop.get("harvest_months") or []
    if not sow or not harvest:
        return True
    a, b = sow[0], harvest[-1]
    return a <= month <= b if a <= b else month >= a or month <= b


def t_mean(d):
    if d.get("t_mean") is not None:
        return d["t_mean"]
    if d.get("t_max") is None or d.get("t_min") is None:
        return None
    return (d["t_max"] + d["t_min"]) / 2


def count(days, test):
    return sum(1 for d in days if t_mean(d) is not None and test(d))


def rule(name: str, days: list[dict], month: int) -> tuple[int | None, str]:
    """Number of favourable days (None = out of the pest's months) and the condition, in plain words."""
    rain = lambda d: d.get("rain_mm") or 0
    hum = lambda d: d.get("humidity") or 0
    if name == "late_blight":  # Hutton: Tmin >= 10 °C and humid; daily RH mean >= 85% stands in for 6 h >= 90%
        n = count(days, lambda d: (d.get("t_min") or 0) >= 10 and hum(d) >= 85)
        return n, "nights ≥ 10 °C with humidity ≥ 85%"
    if name == "tuta":
        return count(days, lambda d: t_mean(d) >= 20), "days averaging ≥ 20 °C"
    if name == "spider_mite":
        return count(days, lambda d: (d.get("t_max") or 0) >= 30 and hum(d) < 50), "days ≥ 30 °C with dry air (< 50%)"
    if name == "powdery_mildew":
        return count(days, lambda d: 15 <= t_mean(d) <= 28 and 50 <= hum(d) <= 90 and rain(d) < 2), \
            "mild days (15–28 °C), humid air, no heavy rain"
    if name == "rust":
        return count(days, lambda d: 10 <= t_mean(d) <= 25 and (hum(d) >= 85 or rain(d) >= 1)), \
            "days 10–25 °C with wet leaves (rain or humidity ≥ 85%)"
    if name == "fusarium":
        if month not in (5, 6):
            return None, "only around flowering (May–June)"
        return count(days, lambda d: 18 <= t_mean(d) <= 30 and (rain(d) >= 2 or hum(d) >= 85)), \
            "warm (18–30 °C) wet days around flowering"
    if name == "corn_borer":
        if month not in (6, 7, 8):
            return None, "moths fly June–August"
        return count(days, lambda d: (d.get("t_min") or 0) >= 15), "warm nights (≥ 15 °C) in the flight season"
    if name == "downy_mildew":
        return count(days, lambda d: 12 <= t_mean(d) <= 23 and (hum(d) >= 85 or rain(d) >= 2)), \
            "cool (12–23 °C), humid or rainy days"
    if name == "aphids":
        return count(days, lambda d: 18 <= t_mean(d) <= 25 and rain(d) < 1), "mild (18–25 °C) dry days"
    if name == "thrips":
        return count(days, lambda d: t_mean(d) >= 20 and rain(d) < 1), "warm (≥ 20 °C) dry days"
    if name == "wet_leaf":
        return count(days, lambda d: 15 <= t_mean(d) <= 25 and rain(d) >= 2), "rainy days at 15–25 °C"
    if name == "alfalfa_weevil":
        if month not in (4, 5):
            return None, "larvae feed April–May"
        return count(days, lambda d: t_mean(d) >= 12), "days averaging ≥ 12 °C"
    if name == "pollen_beetle":
        if month not in (3, 4):
            return None, "beetles arrive March–April"
        return count(days, lambda d: (d.get("t_max") or 0) >= 15), "days reaching 15 °C"
    return None, ""


def spray_windows(wx: dict | None) -> list[dict]:
    """Calm, dry days: wind below 20 km/h, under 1 mm rain that day and under 2 mm the next, below 30 °C."""
    days = (wx or {}).get("days", [])
    out = []
    for i, d in enumerate(days):
        nxt = days[i + 1] if i + 1 < len(days) else None
        ok = ((d["wind_kmh"] or 0) < 20 and (d["rain_mm"] or 0) < 1 and (d["t_max"] or 0) < 30
              and (nxt is None or (nxt["rain_mm"] or 0) < 2))
        out.append({"day": d["day"], "ok": ok, "wind_kmh": d["wind_kmh"], "rain_mm": d["rain_mm"],
                    "next_rain_mm": nxt["rain_mm"] if nxt else None, "t_max": d["t_max"]})
    return out


def field_crops(s: Session, f: FieldRow, crops: dict) -> tuple[list[str], str]:
    planted = [p.crop for p in s.exec(select(Planting).where(Planting.field_id == f.id,
                                                             Planting.harvested_on == None)).all()]  # noqa: E711
    if planted:
        return list(dict.fromkeys(planted)), "planted"
    return [c for c in dict.fromkeys(f.current_rotation or []) if c in crops], "rotation"


def evaluate(s: Session, f: FieldRow) -> dict:
    catalogue = (nasa.read_data_file("pests.json") or {"pests": []})["pests"]
    crops = insights.crops_by_id()
    my_crops, crops_from = field_crops(s, f, crops)
    if not my_crops:  # nothing entered: the region's common rotation
        loc, _, _ = nasa.location_for(f.lat, f.lon, f.region)
        lib = (nasa.read_data_file("rotations.json") or {"rotations": []})["rotations"]
        common = next((r for r in lib if r.get("kind") == "common" and loc["id"] in r.get("regions", [])), None)
        my_crops = list(dict.fromkeys(p["crop"] for p in (common or {}).get("plantings", [])))
        crops_from = "region"

    rows = insights.daily(s, f)
    past = [r for r in rows if r["t_max"] is not None][-7:]
    wx = insights.weather(s, f)
    future = [{"day": d["day"], "t_max": d["t_max"], "t_min": d["t_min"], "rain_mm": d["rain_mm"],
               "humidity": d["humidity"]} for d in (wx or {}).get("days", [])[:3]]
    days = past + future
    month = date.today().month
    sensor = insights.latest_reading(s, f.id)
    dp = insights.pressure_trend(s, f.id)
    wet_soil = (sensor and sensor.soil_pct is not None and sensor.soil_pct > 70) or \
               (past and past[-1].get("gwettop") is not None and past[-1]["gwettop"] > 0.7)
    dry_soil = (sensor and sensor.soil_pct is not None and sensor.soil_pct < 25) or \
               (past and past[-1].get("gwettop") is not None and past[-1]["gwettop"] < 0.35)
    since = date.today() - timedelta(days=21)
    reports = s.exec(select(PestReport).where(PestReport.field_id == f.id, PestReport.seen_on >= since)
                     .order_by(PestReport.seen_on.desc())).all()
    seen = {r.pest for r in reports}

    risks = []
    for p in catalogue:
        hit = [c for c in p["crops"] if c in my_crops]
        if not hit and p["id"] not in seen:
            continue
        season = any(in_season(crops[c], month) for c in hit if c in crops) if hit else True
        n, condition = rule(p["rule"], days, month)
        reasons = []
        if n is None or not season:
            level = "off"
        else:
            idx = 2 if n >= 3 else 1 if n >= 1 else 0
            reasons.append({"key": "days", "value": n, "of": len(days), "condition": condition})
            boost = False
            if sensor and p["rule"] in FUNGAL and (sensor.humidity_pct or 0) >= 85 and \
                    sensor.air_temp_c is not None and 10 <= sensor.air_temp_c <= 25:
                boost = True
                reasons.append({"key": "sensor_humid", "value": sensor.humidity_pct, "temp": sensor.air_temp_c})
            if sensor and p["rule"] in DRY_PESTS and (sensor.air_temp_c or 0) >= 28 and (sensor.humidity_pct or 100) < 45:
                boost = True
                reasons.append({"key": "sensor_hot_dry", "value": sensor.humidity_pct, "temp": sensor.air_temp_c})
            if dp is not None and dp <= -4 and p["rule"] in FUNGAL:
                boost = True
                reasons.append({"key": "pressure_drop", "value": dp})
            if wet_soil and p["rule"] in FUNGAL:
                reasons.append({"key": "wet_soil"})
                boost = boost or n >= 1
            if dry_soil and p["rule"] == "spider_mite":
                reasons.append({"key": "dry_soil"})
                boost = boost or n >= 1
            if boost:
                idx = min(2, idx + 1)
            level = LEVELS[idx]
        if p["id"] in seen:
            level = "seen"
        risks.append({"id": p["id"], "kind": p["kind"], "crops": hit, "level": level, "reasons": reasons,
                      "name": p["name"], "name_mk": p["name_mk"], "model": p["model"],
                      "signs": p["signs"], "signs_mk": p["signs_mk"], "steps": p["steps"]})
    order = {"seen": 0, "high": 1, "medium": 2, "low": 3, "off": 4}
    risks.sort(key=lambda r: order[r["level"]])
    return {
        "field_id": f.id, "crops": my_crops, "crops_from": crops_from, "risks": risks,
        "catalogue": [{"id": p["id"], "name": p["name"], "name_mk": p["name_mk"], "kind": p["kind"],
                       "crops": p["crops"]} for p in catalogue],
        "reports": [{"id": r.id, "pest": r.pest, "seen_on": r.seen_on.isoformat(), "severity": r.severity,
                     "note": r.note} for r in reports],
        "spray": spray_windows(wx),
        "weather_days": days,
        "sensor": None if not sensor else {"time": sensor.time.isoformat(), "air_temp_c": sensor.air_temp_c,
                                           "humidity_pct": sensor.humidity_pct, "pressure_hpa": sensor.pressure_hpa,
                                           "soil_pct": sensor.soil_pct, "soil_temp_c": sensor.soil_temp_c},
        "pressure_change_24h": dp,
        "sources": [
            {"dataset": "NASA POWER daily at the field point (T2M, RH2M, PRECTOTCORR, GWETTOP)",
             "dates": f"{past[0]['day']} to {past[-1]['day']}" if past else "not published yet"},
            (wx or {}).get("source") or {"dataset": "Open-Meteo forecast", "dates": "not available"},
            {"dataset": "Pest list and thresholds: data/pests.json (published disease models, see each card)",
             "dates": "static"},
        ],
    }
