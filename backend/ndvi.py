"""Vegetation greenness (NDVI) over a field from NASA MODIS, and what it says about the field's past.

Data: MOD13Q1 v061, 250 m, 16-day composites (NASA LP DAAC), read through the ORNL DAAC MODIS subset web service,
which needs no login. We ask for a 3 x 3 km window around the field, keep the pixels whose centres fall inside the
field outline (or the nearest pixel for a small field) and average them.

From the series:
- bare periods: composites with NDVI below BARE (soil showing, no crop or cover),
- the season pattern of each year (spring peak = winter cereal, summer peak = summer crop, ...),
- stress: a summer whose peak is well below the field's usual peak, set against NASA POWER rainfall that season.
"""
import logging
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone

import hashlib

import httpx
from sqlmodel import Session, select

from models import Cache, engine

log = logging.getLogger("niva.ndvi")

BASE = "https://modis.ornl.gov/rst/api/v1/MOD13Q1"
BAND = "250m_16_days_NDVI"
DATASET = "NASA MODIS MOD13Q1 v061 NDVI, 250 m, 16-day (LP DAAC, via ORNL DAAC subset service)"
START_YEAR = 2016
BARE = 0.25   # below this the pixel is mostly soil
GREEN = 0.45  # above this a crop or cover is growing well
R = 6371007.181  # MODIS sinusoidal sphere


def _inside(lat, lon, poly) -> bool:
    hit = False
    for i in range(len(poly)):
        (a1, o1), (a2, o2) = poly[i], poly[i - 1]
        if (a1 > lat) != (a2 > lat) and lon < (o2 - o1) * (lat - a1) / (a2 - a1) + o1:
            hit = not hit
    return hit


def _dates(lat, lon) -> list[str]:
    r = httpx.get(f"{BASE}/dates", params={"latitude": lat, "longitude": lon}, timeout=60)
    r.raise_for_status()
    return [d["modis_date"] for d in r.json()["dates"] if int(d["modis_date"][1:5]) >= START_YEAR]


def _chunk(lat, lon, d0, d1) -> dict:
    for attempt in range(3):
        try:
            r = httpx.get(f"{BASE}/subset", timeout=90, params={
                "latitude": lat, "longitude": lon, "band": BAND, "startDate": d0, "endDate": d1,
                "kmAboveBelow": 1, "kmLeftRight": 1})
            r.raise_for_status()
            return r.json()
        except Exception:
            if attempt == 2:
                raise
    return {}


def _pixel_centres(meta: dict) -> list[tuple[float, float]]:
    """Lat/lon of each pixel in the returned window (row-major from the top), from the sinusoidal grid."""
    n_r, n_c, size = int(meta["nrows"]), int(meta["ncols"]), float(meta["cellsize"])
    x0, y0 = float(meta["xllcorner"]), float(meta["yllcorner"])
    out = []
    for i in range(n_r):
        y = y0 + (n_r - i - 0.5) * size
        la = y / R
        for j in range(n_c):
            x = x0 + (j + 0.5) * size
            lo = x / (R * math.cos(la))
            out.append((math.degrees(la), math.degrees(lo)))
    return out


def download(lat: float, lon: float, polygon: list | None) -> dict:
    dates = _dates(lat, lon)
    chunks = [(dates[i], dates[min(i + 9, len(dates) - 1)]) for i in range(0, len(dates), 10)]
    with ThreadPoolExecutor(6) as ex:
        parts = list(ex.map(lambda c: _chunk(lat, lon, *c), chunks))
    series, pick, used = [], None, 0
    for p in parts:
        if not p.get("subset"):
            continue
        if pick is None:
            centres = _pixel_centres(p)
            pick = [k for k, (a, o) in enumerate(centres) if polygon and len(polygon) >= 3 and _inside(a, o, polygon)]
            if not pick:  # small field: nearest pixel
                pick = [min(range(len(centres)), key=lambda k: (centres[k][0] - lat) ** 2
                            + ((centres[k][1] - lon) * math.cos(math.radians(lat))) ** 2)]
            used = len(pick)
        for s in p["subset"]:
            vals = [s["data"][k] for k in pick if s["data"][k] > -2000]
            if vals:
                series.append({"date": s["calendar_date"], "ndvi": round(sum(vals) / len(vals) / 10000, 3)})
    series.sort(key=lambda r: r["date"])
    return {"series": series, "pixels": used, "dataset": DATASET}


def _key(lat, lon, polygon) -> str:
    shape = ";".join(f"{a:.5f},{o:.5f}" for a, o in (polygon or []))
    return f"ndvi:{lat:.5f},{lon:.5f}:{hashlib.md5(shape.encode()).hexdigest()[:8]}"


def series(lat: float, lon: float, polygon: list | None, max_age_days: int = 20, fetch: bool = True) -> dict | None:
    key = _key(lat, lon, polygon)
    with Session(engine) as s:
        c = s.get(Cache, key)
        if c is None:  # written under an older key format for the same field centre: take it over
            old = s.exec(select(Cache).where(Cache.key.startswith(f"ndvi:{lat:.5f},{lon:.5f}:"))).first()
            if old:
                c = Cache(key=key, data=old.data, fetched_at=old.fetched_at)
                s.delete(old)
                s.add(c)
                s.commit()
                s.refresh(c)
        if c:
            age = datetime.now(timezone.utc) - (c.fetched_at if c.fetched_at.tzinfo else
                                                c.fetched_at.replace(tzinfo=timezone.utc))
            if age < timedelta(days=max_age_days) or not fetch:
                return c.data
        if not fetch:
            return None
        try:
            data = download(lat, lon, polygon)
        except Exception as e:
            log.warning("MODIS NDVI download failed: %s", e)
            return c.data if c else None
        # merge, not add: two requests for the same field may both have fetched it
        s.merge(Cache(key=key, data=data, fetched_at=datetime.now(timezone.utc)))
        s.commit()
        return data


def season_label(peaks: list[tuple[int, float]]) -> str:
    """Rough guess of what grew from the months of the green peaks (to be confirmed by the farmer)."""
    green = [m for m, v in peaks if v >= GREEN]
    if not green:
        return "bare or very sparse all year"
    spring = any(m in (3, 4, 5) for m in green)
    summer = any(m in (6, 7, 8, 9) for m in green)
    if spring and summer:
        return "green spring and summer: two crops, a long crop, or weeds"
    if spring:
        return "green in spring, bare after June: looks like a winter cereal (wheat, barley)"
    if summer:
        return "green in summer only: looks like a summer crop (vegetables, maize, tobacco)"
    return "green in autumn or winter only: cover crop or weeds"


def analyse(data: dict | None, rain_by_season: dict[int, float] | None = None) -> dict | None:
    """Bare windows, season pattern and stressed years from the series."""
    if not data or not data.get("series"):
        return None
    rows = [(date.fromisoformat(r["date"]), r["ndvi"]) for r in data["series"]]
    years = sorted({d.year for d, _ in rows if d.year < date.today().year or d.month >= 11})
    per_year = []
    peaks_summer = {}
    for y in years:
        ys = [(d, v) for d, v in rows if d.year == y]
        if len(ys) < 15:
            continue
        bare_days = sum(16 for d, v in ys if v < BARE)
        windows, cur = [], None
        for d, v in ys:
            if v < BARE:
                cur = [d, d + timedelta(days=15)] if cur is None else [cur[0], d + timedelta(days=15)]
            elif cur:
                windows.append(cur)
                cur = None
        if cur:
            windows.append(cur)
        monthly = {}
        for d, v in ys:
            monthly[d.month] = max(monthly.get(d.month, 0), v)
        peaks = sorted(monthly.items())
        summer = max([v for m, v in peaks if 5 <= m <= 9] or [0])
        peaks_summer[y] = summer
        per_year.append({
            "year": y, "bare_days": bare_days, "peak": round(max(v for _, v in ys), 2),
            "summer_peak": round(summer, 2),
            "bare_windows": [{"from": a.isoformat(), "to": b.isoformat()} for a, b in windows if (b - a).days >= 30],
            "pattern": season_label(peaks),
        })
    if not per_year:
        return None
    med = sorted(peaks_summer.values())[len(peaks_summer) // 2]
    stressed = []
    for py in per_year:
        if med and py["summer_peak"] < 0.8 * med and py["summer_peak"] >= BARE:
            rain = rain_by_season.get(py["year"]) if rain_by_season else None
            stressed.append({"year": py["year"], "summer_peak": py["summer_peak"], "usual_peak": round(med, 2),
                             "drop_pct": round(100 * (1 - py["summer_peak"] / med)),
                             "rain_apr_aug_pct_of_normal": rain})
    # months bare in most years
    month_bare = {}
    for d, v in rows:
        month_bare.setdefault(d.month, []).append(v < BARE)
    typical_bare = [m for m, l in sorted(month_bare.items()) if sum(l) / len(l) >= 0.5]
    recent = per_year[-5:]
    return {
        "years": per_year, "stressed_years": stressed, "typically_bare_months": typical_bare,
        "bare_days_avg_recent": round(sum(p["bare_days"] for p in recent) / len(recent)),
        "series": data["series"], "pixels": data.get("pixels"),
        "source": {"dataset": DATASET, "dates": f"{START_YEAR} to now"},
        "thresholds": {"bare": BARE, "green": GREEN},
    }
