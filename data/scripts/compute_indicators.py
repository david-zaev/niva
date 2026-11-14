"""Field indicators from NASA POWER, per demo location (DESIGN.md "Step 1 — Field indicators").

    python data/scripts/compute_indicators.py

Reads data/locations/<id>/power.csv, writes data/locations/<id>/indicators.json.
Baseline = 1991-2020 (WMO climate normal). Recent = the last 10 full years.
Slope (SRTM), bare months (MODIS NDVI) and soil-moisture anomaly (SMAP) stay null until
the Data role adds those downloads; the app shows them as "waiting for data".
"""
import json
from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent.parent
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
        if len(d) < 360:
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


def main() -> None:
    for loc in json.loads((DATA / "locations.json").read_text(encoding="utf-8")):
        folder = DATA / "locations" / loc["id"]
        meta = json.loads((folder / "power_meta.json").read_text(encoding="utf-8"))
        df = pd.read_csv(folder / "power.csv", parse_dates=["date"])
        df["year"], df["month"], df["doy"] = df.date.dt.year, df.date.dt.month, df.date.dt.dayofyear

        last_full = int(df[df.date.dt.strftime("%m-%d") == "12-31"].year.max())
        recent = (last_full - 9, last_full)
        py = per_year(df, range(BASELINE[0], last_full + 1))
        base = py[(py.year >= BASELINE[0]) & (py.year <= BASELINE[1])]
        rec = py[py.year >= recent[0]]
        b, r = summary(base), summary(rec)

        dataset = "NASA POWER daily"
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
            "yearly": [{k: (None if pd.isna(v) else (int(v) if k != "t_mean" else v)) for k, v in row.items()}
                       for row in py[["year", "heat_days", "heavy_rain_days", "rain_mm", "t_mean",
                                      "last_spring_frost_doy", "first_autumn_frost_doy"]].to_dict("records")],
            # Filled by the Data role from other NASA datasets
            "slope_deg": None,
            "bare_months": None,
            "soil_moisture_anomaly": None,
            "sources": [{
                "dataset": dataset,
                "url": meta["source_url"],
                "dates": f"{meta['first_date']} to {meta['last_date']}",
                "used_for": "temperature, rain, heat days, frost dates, heavy-rain days, water balance (ET0: FAO-56 Hargreaves)",
            }],
            "pending": [
                {"indicator": "slope_deg", "dataset": "SRTM 30 m (NASA Earthdata / AppEEARS)"},
                {"indicator": "bare_months", "dataset": "MODIS NDVI MOD13Q1 250 m (ORNL DAAC)"},
                {"indicator": "soil_moisture_anomaly", "dataset": "SMAP 9 km (NASA Earthdata / AppEEARS)"},
            ],
        }
        (folder / "indicators.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{loc['id']}: base {b['t_mean']}°C {b['rain_mm']} mm, heat {b['heat_days']} -> recent "
              f"{r['t_mean']}°C {r['rain_mm']} mm, heat {r['heat_days']}; frost {r['last_spring_frost']}..{r['first_autumn_frost']}")


if __name__ == "__main__":
    main()
