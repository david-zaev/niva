"""The field's climate profile from 25 years of NASA POWER: when it is dry, frost, heat, heavy rain, dry years,
and how today compares with the same date in every past year."""
from datetime import date

import numpy as np
import pandas as pd

import power


def _r(x, n=1):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def _doy_str(doy: float) -> str:
    return (pd.Timestamp(2001, 1, 1) + pd.Timedelta(days=int(round(doy)) - 1)).strftime("%d %b")


def _trend_per_decade(years, values):
    if len(years) < 8:
        return None
    k = np.polyfit(np.asarray(years, float), np.asarray(values, float), 1)[0]
    return round(float(k * 10), 1)


def profile(w: pd.DataFrame, t_offset: float = 0.0) -> dict:
    last_full = w.index[-1].year - 1
    full = w.loc[:str(last_full)]
    years = sorted(set(full.index.year))
    tmin = full["t_min"] + t_offset

    # month by month: rain against crop water demand (reference ET0)
    m = full.groupby([full.index.year, full.index.month]).agg(rain=("rain", "sum"), et0=("et0", "sum"),
                                                              tmax=("t_max", "mean"))
    mm = m.groupby(level=1).mean()
    tmin_m = tmin.groupby([tmin.index.year, tmin.index.month]).mean().groupby(level=1).mean()
    monthly = [{"month": int(k), "rain": _r(r.rain, 0), "et0": _r(r.et0, 0), "t_max": _r(r.tmax),
                "t_min": _r(tmin_m.get(k)), "gap": _r(r.et0 - r.rain, 0)} for k, r in mm.iterrows()]
    dry_months = [x["month"] for x in monthly if x["gap"] and x["gap"] > 60]

    # frost
    last_spring, first_autumn = [], []
    for y in years:
        s = tmin[(tmin.index.year == y)]
        spring = s[(s.index.month < 7) & (s < 0)]
        autumn = s[(s.index.month >= 8) & (s < 0)]
        if len(spring):
            last_spring.append(spring.index[-1].dayofyear)
        if len(autumn):
            first_autumn.append(autumn.index[0].dayofyear)
    frost = {
        "last_spring_median": _doy_str(np.median(last_spring)) if last_spring else None,
        "last_spring_late_1_in_10": _doy_str(np.percentile(last_spring, 90)) if last_spring else None,
        "first_autumn_median": _doy_str(np.median(first_autumn)) if first_autumn else None,
        "first_autumn_early_1_in_10": _doy_str(np.percentile(first_autumn, 10)) if first_autumn else None,
        "frost_free_days_median": int(np.median(first_autumn) - np.median(last_spring)) if last_spring and first_autumn else None,
        "late_frost_after_20_april_years": [y for y, d in zip(years, last_spring) if d > 110],
    }

    # heat and heavy rain per year, with the trend
    by_year = []
    for y in years:
        s = full[full.index.year == y]
        summer = s[(s.index.month >= 4) & (s.index.month <= 9)]
        by_year.append({"year": y, "heat_days": int((s["t_max"] > 35).sum()),
                        "heavy_rain_days": int((s["rain"] >= 20).sum()),
                        "rain": _r(s["rain"].sum(), 0), "et0": _r(s["et0"].sum(), 0),
                        "summer_deficit": _r(summer["et0"].sum() - summer["rain"].sum(), 0)})
    yrs = [b["year"] for b in by_year]
    heat = [b["heat_days"] for b in by_year]
    heavy = [b["heavy_rain_days"] for b in by_year]
    driest = sorted(by_year, key=lambda b: -b["summer_deficit"])[:3]

    # rain April-August as % of normal, used next to NDVI to explain a stressed summer
    aa = full[(full.index.month >= 4) & (full.index.month <= 8)]["rain"].groupby(
        full[(full.index.month >= 4) & (full.index.month <= 8)].index.year).sum()
    rain_apr_aug = {int(y): int(round(100 * v / aa.mean())) for y, v in aa.items()}

    return {
        "years": f"{years[0]}-{years[-1]}", "n_years": len(years),
        "rain_year_mm": _r(np.mean([b["rain"] for b in by_year]), 0),
        "et0_year_mm": _r(np.mean([b["et0"] for b in by_year]), 0),
        "monthly": monthly, "dry_months": dry_months,
        "frost": frost,
        "heat": {"days_per_year": _r(np.mean(heat)), "last_5_years": _r(np.mean(heat[-5:])),
                 "trend_per_decade": _trend_per_decade(yrs, heat)},
        "heavy_rain": {"days_per_year": _r(np.mean(heavy)), "trend_per_decade": _trend_per_decade(yrs, heavy)},
        "driest_summers": driest, "by_year": by_year, "rain_apr_aug_pct": rain_apr_aug,
        "t_offset": t_offset,
        "source": power.source(),
    }


def today_vs_history(w: pd.DataFrame, when: date | None = None) -> dict:
    """The latest NASA POWER day and where it sits among the same dates (±7 days) of all past years."""
    last = w.index[-1]
    when = when or last.date()
    doy = pd.Timestamp(when).dayofyear
    window = w[(abs(w.index.dayofyear - doy) <= 7) & (w.index.year < last.year)]
    row = w.iloc[-1]

    def pct(col, v):
        vals = window[col].dropna()
        return None if v is None or np.isnan(v) or not len(vals) else int(round(100 * (vals < v).mean()))
    rain30 = w["rain"].iloc[-30:].sum()
    past30 = [w["rain"].loc[str(pd.Timestamp(y, last.month, last.day) - pd.Timedelta(days=29)):
                            str(pd.Timestamp(y, last.month, last.day))].sum()
              for y in range(w.index[0].year + 1, last.year) if not (last.month == 2 and last.day == 29)]
    return {
        "date": last.date().isoformat(),
        "root_wetness": _r(row["wet_root"], 2), "root_wetness_pct": pct("wet_root", row["wet_root"]),
        "t_mean": _r(row["t_mean"]), "t_mean_normal": _r(window["t_mean"].mean()),
        "t_min_normal": _r(window["t_min"].mean()), "t_max_normal": _r(window["t_max"].mean()),
        "rh_normal": _r(window["rh"].mean(), 0), "ps_normal_hpa": _r(window["ps_kpa"].mean() * 10),
        "soil_t_normal": _r(window["soil_t"].mean()),
        "rain_30d": _r(rain30, 0), "rain_30d_pct": int(round(100 * np.mean(np.array(past30) < rain30))) if past30 else None,
        "source": power.source(),
    }
