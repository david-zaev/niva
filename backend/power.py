"""NASA POWER daily data for a field, 2001 to now, cached per POWER grid cell.

POWER's meteorology grid is 0.5° latitude x 0.625° longitude (MERRA-2), so every field in the same cell gets the
same numbers: all of Murtino and Strumica share one cell, and a newly drawn field there needs no new download.

Reference evapotranspiration ET0 is computed with FAO-56 Penman-Monteith (Allen et al. 1998, eq. 6) from POWER's
temperature, dew point, wind at 2 m, solar radiation and surface pressure.
"""
import csv
import logging
import math
from datetime import date, timedelta
from pathlib import Path

import httpx
import pandas as pd

import nasa

log = logging.getLogger("niva.power")

CACHE = nasa.DATA_DIR / "cache" / "power"
START = date(2001, 1, 1)
DATASET = "NASA POWER daily, Agroclimatology community (MERRA-2 / GEOS meteorology, 0.5° x 0.625°)"
URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

# POWER name -> our column
PARAMS = {
    "T2M": "t_mean", "T2M_MAX": "t_max", "T2M_MIN": "t_min", "T2MDEW": "t_dew", "RH2M": "rh",
    "PS": "ps_kpa", "WS2M": "wind", "ALLSKY_SFC_SW_DWN": "solar", "PRECTOTCORR": "rain",
    "GWETTOP": "wet_top", "GWETROOT": "wet_root", "TSOIL1": "soil_t",
}
COLS = ["date", *PARAMS.values(), "et0"]


def cell(lat: float, lon: float) -> tuple[float, float]:
    """Centre of the POWER meteorology cell holding a point."""
    return (math.floor(lat / 0.5) * 0.5 + 0.25, math.floor(lon / 0.625) * 0.625 + 0.3125)


def cell_key(lat: float, lon: float) -> str:
    la, lo = cell(lat, lon)
    return f"{la:.3f}_{lo:.4f}"


def et0_pm(t_max, t_min, t_dew, wind, solar, ps_kpa, lat, doy) -> float | None:
    """FAO-56 Penman-Monteith reference ET (mm/day). solar in MJ/m2/day."""
    if None in (t_max, t_min, wind, solar, ps_kpa):
        return None
    t = (t_max + t_min) / 2
    es = lambda x: 0.6108 * math.exp(17.27 * x / (x + 237.3))
    e_s = (es(t_max) + es(t_min)) / 2
    e_a = es(t_dew) if t_dew is not None else es(t_min)
    delta = 4098 * es(t) / (t + 237.3) ** 2
    gamma = 0.000665 * ps_kpa
    # net radiation (FAO-56 eq. 21-40), albedo 0.23
    phi = math.radians(lat)
    dr = 1 + 0.033 * math.cos(2 * math.pi * doy / 365)
    dec = 0.409 * math.sin(2 * math.pi * doy / 365 - 1.39)
    ws = math.acos(max(-1, min(1, -math.tan(phi) * math.tan(dec))))
    ra = 24 * 60 / math.pi * 0.082 * dr * (ws * math.sin(phi) * math.sin(dec)
                                           + math.cos(phi) * math.cos(dec) * math.sin(ws))
    rso = 0.75 * ra
    rns = 0.77 * solar
    ratio = min(1.0, solar / rso) if rso > 0 else 0.5
    sigma = 4.903e-9
    rnl = sigma * ((t_max + 273.16) ** 4 + (t_min + 273.16) ** 4) / 2 * (0.34 - 0.14 * math.sqrt(max(e_a, 0))) \
        * (1.35 * ratio - 0.35)
    rn = rns - rnl
    et0 = (0.408 * delta * rn + gamma * 900 / (t + 273) * wind * (e_s - e_a)) / (delta + gamma * (1 + 0.34 * wind))
    return max(0.0, round(et0, 2))


def _download(lat: float, lon: float, start: date, end: date) -> list[dict]:
    q = {"parameters": ",".join(PARAMS), "community": "AG", "latitude": round(lat, 4), "longitude": round(lon, 4),
         "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON"}
    r = httpx.get(URL, params=q, timeout=180)
    r.raise_for_status()
    p = r.json()["properties"]["parameter"]
    rows = []
    for day in sorted(p["T2M"]):
        row = {"date": f"{day[:4]}-{day[4:6]}-{day[6:]}"}
        for name, col in PARAMS.items():
            v = p[name].get(day)
            row[col] = None if v is None or v <= -998 else v
        if row["t_max"] is None:
            continue  # POWER publishes recent days a few days late
        d = date.fromisoformat(row["date"])
        row["et0"] = et0_pm(row["t_max"], row["t_min"], row["t_dew"], row["wind"], row["solar"], row["ps_kpa"],
                            lat, d.timetuple().tm_yday)
        rows.append(row)
    return rows


def path_for(lat: float, lon: float) -> Path:
    return CACHE / f"{cell_key(lat, lon)}.csv"


def ensure(lat: float, lon: float, max_age_days: int = 3) -> Path:
    """Download (or top up) the cell's file. Works offline once the file exists."""
    path = path_for(lat, lon)
    la, lo = cell(lat, lon)
    today = date.today()
    last = None
    if path.exists():
        with path.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                last = row["date"]
    if last and (today - date.fromisoformat(last)).days <= max_age_days:
        return path
    start = date.fromisoformat(last) + timedelta(days=1) if last else START
    try:
        rows = _download(la, lo, start, today)
    except Exception as e:  # offline or POWER down: keep what we have
        if path.exists():
            log.warning("POWER top-up failed (%s), using cached file", e)
            return path
        raise
    CACHE.mkdir(parents=True, exist_ok=True)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        if new:
            w.writeheader()
        w.writerows(rows)
    _frames.pop(str(path), None)
    return path


_frames: dict[str, tuple[float, pd.DataFrame]] = {}


def frame(lat: float, lon: float) -> pd.DataFrame:
    """Daily frame indexed by date (datetime64)."""
    path = ensure(lat, lon)
    m = path.stat().st_mtime
    hit = _frames.get(str(path))
    if hit and hit[0] == m:
        return hit[1]
    df = pd.read_csv(path, parse_dates=["date"]).drop_duplicates("date").set_index("date").sort_index()
    df["et0"] = df["et0"].fillna(df["et0"].rolling(5, min_periods=1, center=True).mean())
    df["rain"] = df["rain"].fillna(0)
    _frames[str(path)] = (m, df)
    return df


def source() -> dict:
    return {"dataset": DATASET, "url": "https://power.larc.nasa.gov/", "dates": f"{START.year} to now"}
