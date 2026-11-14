"""Field insights for the summary banner, Field & soil metrics, and the advanced panels.

Every number names its source. Outside services are free and need no login:
- NASA POWER daily point API (field coordinates): temperature, rain, GWETTOP / GWETROOT soil wetness, growing degree days
- NASA MODIS MOD13Q1 NDVI, 250 m, 16-day, via the ORNL DAAC MODIS web service
- ISRIC SoilGrids 2.0 (250 m): soil texture, pH, organic carbon, CEC, bulk density, 0-60 cm
- Open-Meteo forecast (ECMWF / DWD ICON): the next 7 days (NASA POWER has no forecast)
Answers are cached in the `cache` table so each service is asked rarely.
"""
import logging
import threading
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlmodel import Session, select

import nasa
from models import Cache, ClimateDaily, FieldRow, Planting, Reading, engine, utcnow

log = logging.getLogger("niva.insights")
POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
ORNL = "https://modis.ornl.gov/rst/api/v1/MOD13Q1"
SOILGRIDS = "https://rest.isric.org/soilgrids/v2.0/properties/query"
FORECAST = "https://api.open-meteo.com/v1/forecast"

# FAO-56 Table 12 single crop coefficients (initial, mid-season, end). Tobacco and the vetch-oat mix are not
# in the table, so they get no Kc and their actual ET stays empty.
KC = {"wheat": (0.7, 1.15, 0.3), "barley": (0.3, 1.15, 0.25), "maize": (0.3, 1.2, 0.35),
      "sunflower": (0.35, 1.05, 0.35), "tomato": (0.6, 1.15, 0.8), "pepper": (0.6, 1.05, 0.9),
      "bean": (0.4, 1.15, 0.35), "chickpea": (0.4, 1.0, 0.35), "alfalfa": (0.4, 0.95, 0.9),
      "rapeseed": (0.35, 1.05, 0.35), "sorghum": (0.3, 1.05, 0.55), "mustard": (0.35, 1.0, 0.35)}
KC_SOURCE = "FAO-56 (Allen et al. 1998), Table 12"

# FAO-56 Table 19: total available water (field capacity minus wilting point), m3/m3, middle of the range
TAW = {"sand": 0.08, "loamy sand": 0.09, "sandy loam": 0.13, "loam": 0.155, "silt loam": 0.16, "silt": 0.18,
       "sandy clay loam": 0.14, "clay loam": 0.15, "silty clay loam": 0.155, "sandy clay": 0.15,
       "silty clay": 0.16, "clay": 0.16}


# ---------- cache ----------

_busy: set[str] = set()


def cached(s: Session, key: str, max_age: timedelta, make, background: bool = False):
    """Serve a fresh enough copy; otherwise fetch. background=True (slow services: SoilGrids, MODIS) never makes
    the caller wait: it returns the old copy or None and fetches in a thread."""
    row = s.get(Cache, key)
    if row and utcnow() - (row.fetched_at if row.fetched_at.tzinfo else row.fetched_at.replace(tzinfo=timezone.utc)) < max_age:
        return row.data
    if background:
        if key not in _busy:
            _busy.add(key)

            def work():
                try:
                    with Session(engine) as s2:
                        cached(s2, key, max_age, make)
                finally:
                    _busy.discard(key)
            threading.Thread(target=work, daemon=True).start()
        return row.data if row else None
    try:
        data = make()
    except Exception:
        log.exception("fetch %s failed", key)
        return row.data if row else None  # an old answer beats none
    if data is not None:
        s.merge(Cache(key=key, data=data, fetched_at=utcnow()))
        s.commit()
    return data


def crops_by_id() -> dict:
    return {c["id"]: c for c in (nasa.read_data_file("crops.json") or {"crops": []})["crops"]}


# ---------- weather forecast ----------

def weather(s: Session, f: FieldRow) -> dict | None:
    def make():
        r = httpx.get(FORECAST, timeout=30, params={
            "latitude": f.lat, "longitude": f.lon, "timezone": "Europe/Skopje", "forecast_days": 7,
            "daily": "precipitation_sum,precipitation_probability_max,temperature_2m_max,temperature_2m_min,"
                     "wind_speed_10m_max,relative_humidity_2m_mean,et0_fao_evapotranspiration"})
        r.raise_for_status()
        d = r.json()["daily"]
        days = [{"day": t, "rain_mm": d["precipitation_sum"][i], "rain_prob": d["precipitation_probability_max"][i],
                 "t_max": d["temperature_2m_max"][i], "t_min": d["temperature_2m_min"][i],
                 "wind_kmh": d["wind_speed_10m_max"][i], "humidity": d["relative_humidity_2m_mean"][i],
                 "et0": d["et0_fao_evapotranspiration"][i]} for i, t in enumerate(d["time"])]
        return {"days": days, "source": {"dataset": "Open-Meteo forecast (ECMWF IFS, DWD ICON); NASA POWER has no forecast",
                                         "dates": f"{days[0]['day']} to {days[-1]['day']}"}}
    out = cached(s, f"weather:{round(f.lat, 3)}:{round(f.lon, 3)}", timedelta(hours=3), make)
    if out:  # drop days already past when an older copy is served
        today = date.today().isoformat()
        out = {**out, "days": [d for d in out["days"] if d["day"] >= today]}
    return out


# ---------- NASA POWER at the field point ----------

def power_series(s: Session, f: FieldRow, start: date, end: date) -> dict:
    """Daily t_max, t_min (°C) at the field point from NASA POWER, start..end inclusive."""
    def make():
        r = httpx.get(POWER, timeout=120, params={
            "parameters": "T2M_MAX,T2M_MIN", "community": "AG", "latitude": f.lat, "longitude": f.lon,
            "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON"})
        r.raise_for_status()
        p = r.json()["properties"]["parameter"]
        return {f"{d[:4]}-{d[4:6]}-{d[6:]}": [p["T2M_MAX"][d], p["T2M_MIN"][d]] for d in p["T2M_MAX"]
                if p["T2M_MAX"][d] not in (None, -999.0) and p["T2M_MIN"].get(d) not in (None, -999.0)}
    return cached(s, f"power:{f.id}:{start}:{end}", timedelta(hours=20), make) or {}


def gdd_day(t_max, t_min, base):
    return max(0.0, (t_max + t_min) / 2 - base)


def climatology_gdd(loc_id: str, base: float) -> dict[int, float]:
    """Average GDD per day of year over the last 10 full years of the region's POWER file."""
    import pandas as pd
    path = nasa.DATA_DIR / "locations" / loc_id / "power.csv"
    df = pd.read_csv(path, usecols=["date", "t_max", "t_min"], parse_dates=["date"]).dropna()
    last = df["date"].dt.year.max() - 1
    df = df[df["date"].dt.year.between(last - 9, last)]
    g = ((df["t_max"] + df["t_min"]) / 2 - base).clip(lower=0)
    return g.groupby(df["date"].dt.dayofyear).mean().to_dict()


def planting_progress(s: Session, f: FieldRow, p: Planting, crops: dict, wx: dict | None) -> dict:
    c = crops.get(p.crop, {})
    base, need = c.get("base_temp_c"), c.get("gdd_to_maturity")
    out = {"id": p.id, "crop": p.crop, "planted_on": p.planted_on.isoformat(),
           "harvested_on": p.harvested_on.isoformat() if p.harvested_on else None,
           "gdd": None, "gdd_needed": need, "base_temp_c": base, "progress": None, "expected_harvest": None,
           "status": "unknown"}
    if base is None or not need or p.harvested_on:
        out["status"] = "harvested" if p.harvested_on else "unknown"
        return out
    yesterday = date.today() - timedelta(days=1)
    series = power_series(s, f, p.planted_on, yesterday) if p.planted_on <= yesterday else {}
    acc, reached = 0.0, None
    for d in sorted(series):
        acc += gdd_day(*series[d], base)
        if reached is None and acc >= need:
            reached = date.fromisoformat(d)  # the day the crop had enough warmth to be ripe
    last_day = max((date.fromisoformat(d) for d in series), default=p.planted_on - timedelta(days=1))
    # POWER runs a few days late: fill those days and the future with the forecast, then the 10-year average
    fc = {d["day"]: d for d in (wx or {}).get("days", []) if d["t_max"] is not None}
    loc, _, _ = nasa.location_for(f.lat, f.lon, f.region)
    clim = climatology_gdd(loc["id"], base)
    day, total, expected = last_day + timedelta(days=1), acc, reached
    for _ in range(0 if reached else 400):
        if total >= need:
            expected = day - timedelta(days=1)
            break
        w = fc.get(day.isoformat())
        add = gdd_day(w["t_max"], w["t_min"], base) if w else clim.get(min(day.timetuple().tm_yday, 365), 0)
        if day < date.today():
            acc += add  # days POWER has not published yet count toward today's total
        total += add
        day += timedelta(days=1)
    progress = acc / need
    out.update(gdd=round(acc), progress=round(progress, 3),
               expected_harvest=expected.isoformat() if expected else None,
               status="ready" if progress >= 1 else "soon" if progress >= 0.9 else "growing",
               kc=kc_for(p.crop, progress), power_days=len(series),
               source={"dataset": "NASA POWER daily T2M_MAX/T2M_MIN at the field point",
                       "dates": f"{p.planted_on} to {last_day}"})
    return out


def kc_for(crop: str, progress: float | None):
    """FAO-56 Kc by growth stage, with the stage read from GDD progress (15% initial, 25% development,
    40% mid-season, 20% late)."""
    if crop not in KC or progress is None:
        return None
    ini, mid, end = KC[crop]
    x = max(0.0, min(1.0, progress))
    if x < 0.15:
        return ini
    if x < 0.40:
        return round(ini + (mid - ini) * (x - 0.15) / 0.25, 2)
    if x < 0.80:
        return mid
    return round(mid + (end - mid) * (x - 0.80) / 0.20, 2)


# ---------- MODIS NDVI ----------

def ndvi(s: Session, f: FieldRow) -> dict | None:
    """MOD13Q1 NDVI at the field pixel (250 m), the last ~3 years."""
    lat, lon = f.lat, f.lon  # plain values: make() may run in a thread after this session is gone

    def make():
        h = {"Accept": "application/json"}
        dates = httpx.get(f"{ORNL}/dates", params={"latitude": lat, "longitude": lon}, headers=h, timeout=60)
        dates.raise_for_status()
        cutoff = (date.today() - timedelta(days=3 * 366)).isoformat()
        wanted = [d for d in dates.json()["dates"] if d["calendar_date"] >= cutoff]
        points = []
        for i in range(0, len(wanted), 10):  # the service answers at most 10 dates per request
            chunk = wanted[i:i + 10]
            r = httpx.get(f"{ORNL}/subset", headers=h, timeout=90, params={
                "latitude": lat, "longitude": lon, "band": "250m_16_days_NDVI",
                "startDate": chunk[0]["modis_date"], "endDate": chunk[-1]["modis_date"],
                "kmAboveBelow": 0, "kmLeftRight": 0})
            r.raise_for_status()
            for row in r.json()["subset"]:
                v = row["data"][0] * 0.0001
                if -0.2 <= v <= 1:
                    points.append({"day": row["calendar_date"], "ndvi": round(v, 3)})
        if not points:
            return None
        return {"points": points, "source": {
            "dataset": "NASA MODIS Terra MOD13Q1 NDVI, 250 m, 16-day (ORNL DAAC)",
            "dates": f"{points[0]['day']} to {points[-1]['day']}"}}
    out = cached(s, f"ndvi:{round(f.lat, 3)}:{round(f.lon, 3)}", timedelta(days=4), make, background=True)
    if not out:
        return None
    pts = out["points"]
    last = pts[-1]
    # same 16-day period in earlier years
    md = last["day"][5:]
    earlier = [p["ndvi"] for p in pts[:-1] if abs((date.fromisoformat(p["day"][:4] + "-" + md) -
                                                     date.fromisoformat(p["day"])).days) <= 8]
    avg = round(sum(earlier) / len(earlier), 3) if earlier else None
    level = "bare" if last["ndvi"] < 0.2 else "sparse" if last["ndvi"] < 0.4 else "green" if last["ndvi"] < 0.65 else "dense"
    return {**out, "latest": last, "same_time_before": avg,
            "change": round(last["ndvi"] - avg, 3) if avg is not None else None, "level": level}


# ---------- SoilGrids ----------

def texture_class(sand, silt, clay) -> str:
    """USDA soil texture triangle."""
    if silt + 1.5 * clay < 15:
        return "sand"
    if silt + 1.5 * clay < 30:
        return "loamy sand"
    if (7 <= clay < 20 and sand > 52 and silt + 2 * clay >= 30) or (clay < 7 and silt < 50 and silt + 2 * clay >= 30):
        return "sandy loam"
    if 7 <= clay < 27 and 28 <= silt < 50 and sand <= 52:
        return "loam"
    if (silt >= 50 and 12 <= clay < 27) or (50 <= silt < 80 and clay < 12):
        return "silt loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if 20 <= clay < 35 and silt < 28 and sand > 45:
        return "sandy clay loam"
    if 27 <= clay < 40 and 20 < sand <= 45:
        return "clay loam"
    if 27 <= clay < 40 and sand <= 20:
        return "silty clay loam"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    return "clay"


def soil(s: Session, f: FieldRow) -> dict | None:
    props = ["clay", "sand", "silt", "phh2o", "soc", "cec", "bdod", "nitrogen"]
    depths = ["0-5cm", "5-15cm", "15-30cm", "30-60cm"]
    lat, lon = f.lat, f.lon

    def make():
        found = []
        for prop in props:  # one property per request: the full query often times out on their side
            for attempt in range(3):
                try:
                    r = httpx.get(SOILGRIDS, timeout=120, params=[("lon", lon), ("lat", lat), ("value", "mean"),
                                                                  ("property", prop)] + [("depth", d) for d in depths])
                    r.raise_for_status()
                    found += r.json()["properties"]["layers"]
                    break
                except httpx.HTTPError:
                    if attempt == 2:
                        raise
                    time.sleep(10)
        layers = {}
        for layer in found:
            k = layer["unit_measure"]["d_factor"]
            for d in layer["depths"]:
                v = d["values"]["mean"]
                layers.setdefault(d["label"], {})[layer["name"]] = None if v is None else round(v / k, 2)
        if not any(v.get("clay") is not None for v in layers.values()):
            return None
        return {"layers": [{"depth": d, **layers.get(d, {})} for d in depths]}
    out = cached(s, f"soil:{round(f.lat, 3)}:{round(f.lon, 3)}", timedelta(days=365), make, background=True)
    if not out:
        return None
    top = [l for l in out["layers"][:3] if l.get("clay") is not None]
    w = {"0-5cm": 5, "5-15cm": 10, "15-30cm": 15}
    avg = lambda k: round(sum(l[k] * w[l["depth"]] for l in top) / sum(w[l["depth"]] for l in top), 1)
    sand, silt, clay = avg("sand"), avg("silt"), avg("clay")
    tex = texture_class(sand, silt, clay)
    return {**out, "topsoil": {"sand": sand, "silt": silt, "clay": clay, "ph": avg("phh2o"), "soc": avg("soc"),
                               "texture": tex, "taw_mm_per_m": round(TAW[tex] * 1000)},
            "units": {"clay": "%", "sand": "%", "silt": "%", "phh2o": "pH", "soc": "g/kg", "cec": "cmol(c)/kg",
                      "bdod": "kg/dm³", "nitrogen": "g/kg"},
            "source": {"dataset": "ISRIC SoilGrids 2.0, 250 m (MASIS national survey has no public web service)",
                       "dates": "static map, 2020 release"},
            "taw_source": "FAO-56 Table 19, middle of the range for the texture class"}


# ---------- daily field metrics (last 50 days) ----------

def daily(s: Session, f: FieldRow, crop: str | None = None, progress: float | None = None) -> list[dict]:
    rows = s.exec(select(ClimateDaily).where(ClimateDaily.field_id == f.id)
                  .order_by(ClimateDaily.date.desc()).limit(60)).all()
    kc = kc_for(crop, progress) if crop else None
    out = []
    for r in reversed(rows):
        out.append({"day": r.date.isoformat(), "rain_mm": r.rain_mm, "et0": r.et0,
                    "eta": round(r.et0 * kc, 2) if kc is not None and r.et0 is not None else None,
                    "t_max": r.t_max, "t_min": r.t_min, "t_mean": r.t_mean, "humidity": r.humidity, "wind": r.wind,
                    "gwettop": r.gwettop, "gwetroot": r.gwetroot,
                    "sm": round(r.sm * 100, 1) if r.sm is not None else None})
    return out


def latest_reading(s: Session, field_id: int, hours: int = 6) -> Reading | None:
    r = s.exec(select(Reading).where(Reading.field_id == field_id).order_by(Reading.time.desc()).limit(1)).first()
    if not r:
        return None
    t = r.time if r.time.tzinfo else r.time.replace(tzinfo=timezone.utc)
    return r if utcnow() - t < timedelta(hours=hours) else None


def pressure_trend(s: Session, field_id: int) -> float | None:
    """Change in barometric pressure over the last ~24 h from the field sensor, hPa."""
    now = utcnow()
    rows = s.exec(select(Reading).where(Reading.field_id == field_id, Reading.pressure_hpa != None,  # noqa: E711
                                        Reading.time >= now - timedelta(hours=27)).order_by(Reading.time)).all()
    if len(rows) < 2:
        return None
    first, last = rows[0], rows[-1]
    t0 = first.time if first.time.tzinfo else first.time.replace(tzinfo=timezone.utc)
    t1 = last.time if last.time.tzinfo else last.time.replace(tzinfo=timezone.utc)
    if t1 - t0 < timedelta(hours=12) or now - t1 > timedelta(hours=6):
        return None
    return round(last.pressure_hpa - first.pressure_hpa, 1)


# ---------- summary banner ----------

def readiness(s: Session, f: FieldRow, rows: list[dict], crops: dict, active_crops: list[str]) -> dict:
    with_wet = [r for r in rows if r["gwettop"] is not None]
    last = with_wet[-1] if with_wet else None
    sensor = latest_reading(s, f.id)
    recent = [r for r in rows[-7:] if r["t_max"] is not None and r["t_min"] is not None]
    air7 = round(sum((r["t_max"] + r["t_min"]) / 2 for r in recent) / len(recent), 1) if recent else None
    soil_t = sensor.soil_temp_c if sensor and sensor.soil_temp_c is not None else None
    temp = soil_t if soil_t is not None else air7
    wet = last["gwettop"] if last else None
    # GWETTOP = share of the pore space holding water (0 dry .. 1 saturated). Rule of thumb: below 0.35 the seedbed
    # is dry, above 0.8 the soil is too wet to drive on and work.
    status = "unknown" if wet is None else "dry" if wet < 0.35 else "wet" if wet > 0.8 else "ok"
    if sensor and sensor.soil_pct is not None:  # the field sensor is closer to the truth than a 50 km grid
        status = "dry" if sensor.soil_pct < 20 else "wet" if sensor.soil_pct > 80 else "ok"
    month = date.today().month
    rotation = list(dict.fromkeys(active_crops + list(f.current_rotation or [])))
    if not rotation:  # nothing entered: what is common in the region
        loc, _, _ = nasa.location_for(f.lat, f.lon, f.region)
        lib = (nasa.read_data_file("rotations.json") or {"rotations": []})["rotations"]
        common = next((r for r in lib if r.get("kind") == "common" and loc["id"] in r.get("regions", [])), None)
        rotation = list(dict.fromkeys(p["crop"] for p in (common or {}).get("plantings", [])))
    sow_now = []
    for cid in rotation:
        c = crops.get(cid)
        if c and month in c.get("sow_months", []):
            warm = temp is None or temp >= (c.get("base_temp_c") or 0) + 2
            sow_now.append({"crop": cid, "warm_enough": warm})
    return {"status": status, "gwettop": wet, "gwetroot": last["gwetroot"] if last else None,
            "wet_day": last["day"] if last else None, "soil_pct": sensor.soil_pct if sensor else None,
            "soil_temp_c": soil_t, "air_temp_7d": air7, "temp_source": "sensor" if soil_t is not None else "nasa",
            "sow_now": sow_now,
            "source": {"dataset": "NASA POWER GWETTOP / GWETROOT at the field point",
                       "dates": last["day"] if last else "not published yet"}}


def next_days(wx: dict | None) -> dict | None:
    if not wx or not wx.get("days"):
        return None
    days = wx["days"]
    rain = [(d["day"], d["rain_mm"] or 0) for d in days]
    wettest = max(rain, key=lambda x: x[1])
    return {
        "rain_total": round(sum(r for _, r in rain), 1),
        "wettest_day": wettest[0] if wettest[1] >= 1 else None, "wettest_mm": round(wettest[1], 1),
        "dry_days": sum(1 for _, r in rain if r < 1),
        "t_max": max(d["t_max"] for d in days), "t_min": min(d["t_min"] for d in days),
        "frost_days": [d["day"] for d in days if d["t_min"] is not None and d["t_min"] <= 0],
        "hot_days": [d["day"] for d in days if d["t_max"] is not None and d["t_max"] >= 35],
        "windy_days": [d["day"] for d in days if d["wind_kmh"] is not None and d["wind_kmh"] >= 40],
        "humid_after_rain": any((d["rain_mm"] or 0) >= 5 and (d["humidity"] or 0) >= 80 for d in days),
        "et0_total": round(sum(d["et0"] or 0 for d in days), 1),
    }


def active_plantings(s: Session, field_id: int) -> list[Planting]:
    return s.exec(select(Planting).where(Planting.field_id == field_id).order_by(Planting.planted_on.desc())).all()


def iso(d):
    return d.isoformat() if isinstance(d, (date, datetime)) else d
