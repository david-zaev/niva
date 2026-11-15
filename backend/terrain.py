"""Elevation and slope under a field, from NASA NASADEM (SRTM reprocessed, 30 m).

The tiles are plain .hgt files in data/dem (downloaded by data/scripts/download_dem.py). For a point we read a
small window around it; for a drawn field outline we sample every 30 m pixel inside it. Slope uses Horn's method
(the one used by GIS software), in degrees and in percent.

Erosion: the slope steepness factor S of the Revised Universal Soil Loss Equation (McCool et al., 1987) says how
much faster soil washes off this slope than off a gentle 2 % one. scoring.py multiplies the bare-soil penalty by it.
"""
import math
from functools import lru_cache

import numpy as np

import nasa

N = 3601  # 1 arc-second tiles: 3601 x 3601
DATASET = "NASA NASADEM_HGT v001 (SRTM reprocessed), 30 m, LP DAAC"


@lru_cache(maxsize=12)
def tile(lat0: int, lon0: int):
    path = nasa.DATA_DIR / "dem" / f"n{lat0:02d}e{lon0:03d}.hgt"
    if not path.exists():
        return None
    return np.memmap(path, dtype=">i2", mode="r", shape=(N, N))


def elevation_grid(lat: float, lon: float, half: int = 2):
    """(2*half+1)^2 window of elevations around a point, and the pixel size in metres (dx, dy)."""
    lat0, lon0 = math.floor(lat), math.floor(lon)
    t = tile(lat0, lon0)
    if t is None:
        return None
    r = int(round((lat0 + 1 - lat) * (N - 1)))
    c = int(round((lon - lon0) * (N - 1)))
    if r - half < 0 or c - half < 0 or r + half >= N or c + half >= N:
        return None  # at a tile edge: skip rather than read the wrong tile
    w = np.array(t[r - half:r + half + 1, c - half:c + half + 1], dtype=float)
    w[w < -500] = np.nan  # voids
    dy = 6371000 * math.radians(1 / 3600)
    return w, dy * math.cos(math.radians(lat)), dy


def slope_at(lat: float, lon: float) -> tuple[float, float] | None:
    """(elevation m, slope degrees) around a point. SRTM has a few metres of radar noise, which on flat plains
    reads as fake 3-4 degree slopes from one pixel, so the 11 x 11 window (~330 m) is smoothed 3 x 3 first and
    the median slope of the inner pixels is used."""
    g = elevation_grid(lat, lon, 5)
    if g is None:
        return None
    z, dx, dy = g
    if np.isnan(z).mean() > 0.2:
        return None
    z = np.where(np.isnan(z), np.nanmean(z), z)
    sm = sum(z[1 + i:z.shape[0] - 1 + i, 1 + j:z.shape[1] - 1 + j] for i in (-1, 0, 1) for j in (-1, 0, 1)) / 9
    gy, gx = np.gradient(sm, dy, dx)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))[1:-1, 1:-1]
    return float(z[5, 5]), float(np.median(slope))


def inside(lat, lon, poly) -> bool:
    hit = False
    for i in range(len(poly)):
        (a1, o1), (a2, o2) = poly[i], poly[i - 1]
        if (a1 > lat) != (a2 > lat) and lon < (o2 - o1) * (lat - a1) / (a2 - a1) + o1:
            hit = not hit
    return hit


def rusle_s(slope_deg: float) -> float:
    s = math.sin(math.radians(slope_deg))
    return 10.8 * s + 0.03 if math.tan(math.radians(slope_deg)) < 0.09 else 16.8 * s - 0.50


def for_field(lat: float, lon: float, polygon=None) -> dict | None:
    """Elevation, slope and erosion factor for a field: over its outline if drawn, else at its point."""
    pts = []
    if polygon and len(polygon) >= 3:
        lats, lons = [p[0] for p in polygon], [p[1] for p in polygon]
        step = 3 / 3600
        la = min(lats)
        while la <= max(lats) and len(pts) < 4000:
            lo = min(lons)
            while lo <= max(lons):
                if inside(la, lo, polygon):
                    v = slope_at(la, lo)
                    if v:
                        pts.append(v)
                lo += step
            la += step
    if not pts:
        v = slope_at(lat, lon)
        if not v:
            return None
        pts = [v]
    elev = [p[0] for p in pts]
    slopes = sorted(p[1] for p in pts)
    mean = sum(slopes) / len(slopes)
    steep = slopes[int(0.9 * (len(slopes) - 1))]
    factor = max(0.5, min(4.0, rusle_s(mean) / rusle_s(math.degrees(math.atan(0.02)))))
    return {
        "elevation_m": round(sum(elev) / len(elev)),
        "slope_deg": round(mean, 1), "slope_pct": round(100 * math.tan(math.radians(mean)), 1),
        "steepest_deg": round(steep, 1), "pixels": len(pts), "from_outline": len(pts) > 1,
        "erosion_factor": round(factor, 2),
        "class": "flat" if mean < 2 else "gentle" if mean < 5 else "moderate" if mean < 10 else "steep",
        "source": {"dataset": DATASET, "dates": "acquired February 2000 (SRTM)"},
    }
