"""NASA SMAP soil moisture at any field in North Macedonia.

data/smap/smap_mk.npz holds the SMAP Enhanced L3 9 km daily grid over the country (downloaded by
data/scripts/download_smap.py, refreshed daily on the server). Morning and evening passes are averaged when both
exist. Values are volumetric water content of the top ~5 cm, m3/m3; the app shows them x 100 as %.
"""
from datetime import date, timedelta
from functools import lru_cache

import warnings

import numpy as np

import nasa

DATASET = "NASA SMAP Enhanced L3 radiometer soil moisture, 9 km, daily (SPL3SMP_E v6, NSIDC)"


def _mtime():
    p = nasa.DATA_DIR / "smap" / "smap_mk.npz"
    return p.stat().st_mtime if p.exists() else None


@lru_cache(maxsize=2)
def _grid(mtime):
    z = np.load(nasa.DATA_DIR / "smap" / "smap_mk.npz")
    both = np.stack([z["am"], z["pm"]])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        daily = np.nanmean(both, axis=0)
    return [date.fromisoformat(str(d)) for d in z["dates"]], z["lat"], z["lon"], daily


def grid():
    m = _mtime()
    return _grid(m) if m else None


def pixel(lat: float, lon: float):
    """Daily SMAP at the 9 km pixel holding a point: (dates, values). Falls back to the mean of the 3x3 pixels
    around it on days the centre pixel has no retrieval (dense vegetation, water or RFI flags)."""
    g = grid()
    if g is None:
        return None
    dates, la, lo, daily = g
    i, j = int(np.argmin(abs(la - lat))), int(np.argmin(abs(lo - lon)))
    if abs(la[i] - lat) > 0.1 or abs(lo[j] - lon) > 0.1:
        return None  # outside the downloaded window
    centre = daily[:, i, j]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        ring = np.nanmean(daily[:, max(0, i - 1):i + 2, max(0, j - 1):j + 2], axis=(1, 2))
    vals = np.where(np.isnan(centre), ring, centre)
    return dates, vals


def normals(dates, vals, before_year: int):
    """Mean SMAP for each day of the year (a 31-day window), over the years before `before_year`."""
    doy = np.array([d.timetuple().tm_yday for d in dates])
    use = np.array([d.year < before_year for d in dates]) & ~np.isnan(vals)
    out = np.full(367, np.nan)
    for day in range(1, 367):
        gap = np.abs(doy[use] - day)
        sel = np.minimum(gap, 366 - gap) <= 15
        if sel.sum() >= 20:
            out[day] = vals[use][sel].mean()
    return out


def series(lat: float, lon: float, days: int = 400) -> dict | None:
    """Recent daily SMAP at a field (volumetric %), each day with this pixel's normal for that time of year."""
    px = pixel(lat, lon)
    if px is None:
        return None
    dates, vals = px
    start = date.today() - timedelta(days=days)
    keep = [k for k, d in enumerate(dates) if d >= start and not np.isnan(vals[k])]
    if not keep:
        return None
    last = dates[keep[-1]]
    norm = _normals(lat, lon, len(dates), last.year)
    pct = lambda v: None if v is None or np.isnan(v) else round(float(v) * 100, 1)
    rows = [{"day": dates[k].isoformat(), "sm": pct(vals[k]), "normal": pct(norm[dates[k].timetuple().tm_yday])}
            for k in keep]
    latest = rows[-1]
    return {"days": rows, "latest": latest, "normal_for_date": latest["normal"],
            "anomaly": round(latest["sm"] - latest["normal"], 1) if latest["normal"] is not None else None,
            "years_in_normal": f"{dates[0].year}-{last.year - 1}",
            "source": {"dataset": DATASET, "dates": f"{rows[0]['day']} to {latest['day']}"}}


@lru_cache(maxsize=64)
def _normals(lat, lon, n_dates, year):  # n_dates: a new download invalidates the cache
    dates, vals = pixel(lat, lon)
    return normals(dates, vals, year)
