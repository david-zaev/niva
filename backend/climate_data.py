"""Field indicators from NASA POWER, per demo location (DESIGN.md "Step 1 — Field indicators").

    python data/scripts/compute_indicators.py

Reads data/locations/<id>/power.csv, writes data/locations/<id>/indicators.json.
Baseline = 1991-2020 (WMO climate normal). Recent = the last 10 full years.
Slope comes from NASA NASADEM (terrain.py) and the soil-moisture anomaly from NASA SMAP (smap.py) when their
files are on disk; bare months (MODIS NDVI) stay null here (the field screens fetch NDVI live).
"""
import json
from pathlib import Path
from datetime import datetime, timezone
import os

import pandas as pd

import smap
import terrain

DATA = Path(os.getenv("NIVA_DATA", Path(__file__).resolve().parent.parent / "data"))
BASELINE = (1991, 2020)
HEAT_C = 35.0       # heat-stress day: Tmax above this, June-August
HEAVY_MM = 20.0     # heavy-rain day: more than this in one day
FROST_C = 0.0       # frost: Tmin at or below this


def r1(x):
    return None if pd.isna(x) else round(float(x), 1)


def mmdd(doy):
    """Median day-of-year -> 'MM-DD' (non-leap calendar)."""
    if pd.isna(doy):
        return None
    return (pd.Timestamp("2001-01-01") + pd.Timedelta(days=int(round(doy)) - 1)).strftime("%m-%d")


def per_year(df: pd.DataFrame, years: range) -> pd.DataFrame:
    out = []
    for y in years:
        d = df[df.year == y]
        if len(d.dropna(subset=['t_max', 't_min', 'rain_mm'])) < 360:
            continue
        summer = d[d.month.isin([6, 7, 8])]
        spring = d[(d.month <= 6) & (d.t_min <= FROST_C)]
        autumn = d[(d.month >= 7) & (d.t_min <= FROST_C)]
        last_spring = spring.doy.max() if len(spring) else None
        first_autumn = autumn.doy.min() if len(autumn) else None
        t_mean = (d.t_max + d.t_min) / 2
        out.append({
            "year": y,
            "heat_days": int((summer.t_max > HEAT_C).sum()),
            "heavy_rain_days": int((d.rain_mm > HEAVY_MM).sum()),
            "rain_mm": round(float(d.rain_mm.sum()), 0),
            "et0_mm": round(float(d.et0.sum()), 0),
            "t_mean": round(float(t_mean.mean()), 2),
            "last_spring_frost_doy": last_spring,
            "first_autumn_frost_doy": first_autumn,
            "frost_free_days": (first_autumn - last_spring) if last_spring and first_autumn else None,
            # growing degree days, base 0 °C (wheat) and base 10 °C (maize, sunflower, pepper)
            "gdd_base0": round(float((t_mean.clip(lower=0)).sum()), 0),
            "gdd_base10": round(float(((d.t_max.clip(upper=30) + d.t_min.clip(lower=10)) / 2 - 10).clip(lower=0).sum()), 0),
        })
    return pd.DataFrame(out)


def monthly(df: pd.DataFrame, y0: int, y1: int) -> list[dict]:
    d = df[(df.year >= y0) & (df.year <= y1)]
    by_ym = d.groupby(["year", "month"]).agg(
        rain_mm=("rain_mm", "sum"), et0_mm=("et0", "sum"),
        t_max=("t_max", "mean"), t_min=("t_min", "mean"),
        heavy=("rain_mm", lambda s: (s > HEAVY_MM).sum()),
        frost=("t_min", lambda s: (s <= FROST_C).sum()),
    )
    m = by_ym.groupby("month").mean()
    return [{
        "month": int(i),
        "rain_mm": r1(row.rain_mm), "et0_mm": r1(row.et0_mm),
        "balance_mm": r1(row.rain_mm - row.et0_mm),
        "t_max": r1(row.t_max), "t_min": r1(row.t_min),
        "heavy_rain_days": round(float(row.heavy), 2), "frost_days": round(float(row.frost), 1),
    } for i, row in m.iterrows()]


def summary(py: pd.DataFrame) -> dict:
    return {
        "heat_days": r1(py.heat_days.mean()),
        "heavy_rain_days": r1(py.heavy_rain_days.mean()),
        "rain_mm": r1(py.rain_mm.mean()),
        "et0_mm": r1(py.et0_mm.mean()),
        "t_mean": r1(py.t_mean.mean()),
        "last_spring_frost": mmdd(py.last_spring_frost_doy.median()),
        "first_autumn_frost": mmdd(py.first_autumn_frost_doy.median()),
        "frost_free_days": r1(py.frost_free_days.median()),
        "gdd_base0": r1(py.gdd_base0.mean()),
        "gdd_base10": r1(py.gdd_base10.mean()),
    }


def current_year(df: pd.DataFrame) -> dict:
    """Partial-year observations with individual publication dates and matched-period comparisons."""
    valid = df.dropna(subset=['t_max', 't_min'])
    year = int(valid.year.max())
    current = df[df.year == year].copy()
    dates = {col: (None if current[col].dropna().empty else
                  current.loc[current[col].notna(), 'date'].max().date().isoformat())
             for col in ['t_max', 't_min', 'rain_mm', 'humidity', 'solar', 'wind', 'et0']}
    temp = current.dropna(subset=['t_max', 't_min'])
    temp_cutoff = temp.date.max().strftime('%m-%d')
    rain_cutoff = (dates['rain_mm'] or f'{year}-01-01')[5:]
    baseline = df[df.year.between(*BASELINE)]
    base_temp = baseline[baseline.date.dt.strftime('%m-%d') <= temp_cutoff]
    base_rain = baseline[baseline.date.dt.strftime('%m-%d') <= rain_cutoff]
    t_mean = (temp.t_max + temp.t_min).mean() / 2
    normal_temp = (base_temp.t_max + base_temp.t_min).mean() / 2
    rain = current.rain_mm.sum(min_count=1)
    normal_rain = base_rain.groupby('year').rain_mm.sum(min_count=1).mean()
    months = []
    for month in range(1, 13):
        rows = current[current.month == month]
        rain_m, et0_m = rows.rain_mm.sum(min_count=1), rows.et0.sum(min_count=1)
        months.append({'month': month, 'rain_mm': r1(rain_m), 'et0_mm': r1(et0_m),
                       'balance_mm': r1(rain_m - et0_m)})
    summer = temp[temp.month.isin([6, 7, 8])]
    spring = temp[(temp.month <= 6) & (temp.t_min <= FROST_C)]
    autumn = temp[(temp.month >= 7) & (temp.t_min <= FROST_C)]
    last = temp.iloc[-1]
    return {
        'year': year, 'start_date': f'{year}-01-01', 'end_date': temp.date.max().date().isoformat(),
        'partial': temp.date.max().strftime('%m-%d') != '12-31',
        'dates': dates, 'temperature_days': len(temp), 'rain_days': int(current.rain_mm.count()),
        't_mean': r1(t_mean), 't_mean_change_c': r1(t_mean - normal_temp),
        'rain_mm': r1(rain), 'rain_change_pct': r1(100 * (rain - normal_rain) / normal_rain) if normal_rain else None,
        'heat_days': int((summer.t_max > HEAT_C).sum()),
        'last_spring_frost_doy': None if spring.empty else int(spring.doy.max()),
        'first_autumn_frost_doy': None if autumn.empty else int(autumn.doy.min()),
        'latest': {'date': last.date.date().isoformat(), 't_max': r1(last.t_max), 't_min': r1(last.t_min)},
        'monthly': months,
    }


def compute(df: pd.DataFrame, meta: dict, loc: dict) -> dict:
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["year"], df["month"], df["doy"] = df.date.dt.year, df.date.dt.month, df.date.dt.dayofyear
    py = per_year(df, range(BASELINE[0], int(df.year.max()) + 1))
    py = py[py.year.isin(df[df.date.dt.strftime('%m-%d') == '12-31'].year)]
    last_full = int(py.year.max())
    recent = (last_full - 9, last_full)
    base = py[(py.year >= BASELINE[0]) & (py.year <= BASELINE[1])]
    rec = py[py.year >= recent[0]]
    b, r = summary(base), summary(rec)

    dataset = "NASA POWER daily"
    terrain_at = terrain.for_field(loc["lat"], loc["lon"])
    smap_at = smap.series(loc["lat"], loc["lon"], 30)
    out = {
        "location": {k: loc[k] for k in ("id", "name", "name_mk", "lat", "lon")},
        "periods": {"baseline": f"{BASELINE[0]}-{BASELINE[1]}", "recent": f"{recent[0]}-{recent[1]}"},
        "thresholds": {"heat_day_tmax_c": HEAT_C, "heavy_rain_mm": HEAVY_MM, "frost_tmin_c": FROST_C},
        "baseline": b,
        "recent": r,
        "trend": {
            "t_mean_change_c": r1(r["t_mean"] - b["t_mean"]),
            "rain_change_pct": r1(100 * (r["rain_mm"] - b["rain_mm"]) / b["rain_mm"]),
            "heat_days_change": r1(r["heat_days"] - b["heat_days"]),
            "frost_free_days_change": r1(r["frost_free_days"] - b["frost_free_days"]),
        },
        "monthly": {"baseline": monthly(df, *BASELINE), "recent": monthly(df, *recent)},
        # What-if "+N °C": recent summers with every day N degrees warmer (simple shift, no new weather)
        "what_if_warming": {
            str(n): {
                "heat_days": r1(df[(df.year >= recent[0]) & (df.year <= recent[1]) & df.month.isin([6, 7, 8])]
                                .assign(hot=lambda x: x.t_max + n > HEAT_C).groupby("year").hot.sum().mean()),
            } for n in (0, 1, 2, 3)
        },
        "yearly": [{k: (None if pd.isna(v) else (int(v) if k != "t_mean" else v)) for k, v in row.items()}
                   for row in py[["year", "heat_days", "heavy_rain_days", "rain_mm", "t_mean",
                                  "last_spring_frost_doy", "first_autumn_frost_doy"]].to_dict("records")],
        "slope_deg": (terrain_at or {}).get("slope_deg"),
        "terrain": terrain_at,
        "bare_months": None,
        "soil_moisture_anomaly": (smap_at or {}).get("anomaly"),
        "smap": {k: smap_at[k] for k in ("latest", "normal_for_date", "anomaly", "years_in_normal", "source")}
                if smap_at else None,
        "sources": [{
            "dataset": dataset,
            "url": meta["source_url"],
            "dates": f"{meta['first_date']} to {meta['last_date']}",
            "used_for": "temperature, rain, heat days, frost dates, heavy-rain days, water balance (ET0: FAO-56 Hargreaves)",
        }],
        "pending": [p for p in [
            None if terrain_at else {"indicator": "slope_deg", "dataset": terrain.DATASET},
            {"indicator": "bare_months", "dataset": "MODIS NDVI MOD13Q1 250 m (ORNL DAAC)"},
            None if smap_at else {"indicator": "soil_moisture_anomaly", "dataset": smap.DATASET},
        ] if p],
    }
    out["current"] = current_year(df)
    out["updated_at"] = meta.get("downloaded_at")
    return out


def compute_location(loc: dict) -> dict:
    folder = DATA / "locations" / loc["id"]
    meta = json.loads((folder / "power_meta.json").read_text(encoding="utf-8"))
    out = compute(pd.read_csv(folder / "power.csv"), meta, loc)
    write_json(folder / "indicators.json", out)
    return out


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)
