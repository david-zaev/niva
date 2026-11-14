"""Train and test the soil-moisture forecast (backend/forecast.py explains the model).

Reads data/locations/<id>/power.csv (NASA POWER) and soil.csv (ERA5-Land 0-7 cm, daily, since 2015).
Test rule (DESIGN.md): train on 2015-2022, test on 2023-2024 data the model never saw, and save that error in
data/model/model_report.json so the app and the slides show the same number. The saved model is then trained again
on all years, so it knows the latest seasons.

The test feeds the model the weather that really fell in the coming days. On the server those days come from a
weather forecast, which is good for 3-5 days and weaker after, so day-10 errors in real use will be larger than
the test says. The report says so too.

Train on the PC, then copy data/model/ to the server. A joblib model only loads in the scikit-learn version that
wrote it, so the PC must have the version pinned in backend/requirements.txt (the script refuses to run otherwise):
    python data/scripts/train_model.py
"""
import json
import sys
from datetime import date
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance

DATA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATA.parent / "backend"))
import forecast  # noqa: E402  (shared feature code)
import smap  # noqa: E402

TRAIN_END, TEST_START, TEST_END = "2022-12-31", "2023-01-01", "2024-12-31"
LABELS = {"sm": "Soil moisture now", "sm_rel": "Soil moisture now", "sm_d3": "Recent drying or wetting",
          "sm_d7": "Recent drying or wetting", "rain_1": "Rain in the last days", "rain_3": "Rain in the last days",
          "rain_7": "Rain in the last days", "rain_30": "Rain, last 30 days", "et0_7": "Recent crop water use",
          "et0_30": "Recent crop water use", "balance_30": "Rain, last 30 days",
          "tmax_7": "Recent heat", "tmin_7": "Recent heat", "hum_7": "Air humidity", "solar_7": "Recent heat",
          "wind_7": "Wind", "doy_sin": "Time of year", "doy_cos": "Time of year", "h": "Days ahead",
          "fut_rain": "Rain in the coming days", "fut_rain_last3": "Rain in the coming days",
          "fut_rain_max": "Rain in the coming days", "fut_et0": "Crop water use in the coming days",
          "fut_balance": "Rain minus water use, coming days", "fut_tmax": "Heat in the coming days"}


def new_model(quantile=None):
    kw = dict(max_iter=400, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40, l2_regularization=1.0,
              random_state=0)
    if quantile is None:
        return HistGradientBoostingRegressor(loss="absolute_error", **kw)
    return HistGradientBoostingRegressor(loss="quantile", quantile=quantile, **kw)


def fit_all(X, y):
    return {"mid": new_model().fit(X, y), "low": new_model(0.05).fit(X, y), "high": new_model(0.95).fit(X, y)}


def load(loc_id: str) -> pd.DataFrame:
    folder = DATA / "locations" / loc_id
    power = pd.read_csv(folder / "power.csv", parse_dates=["date"], index_col="date")
    soil = pd.read_csv(folder / "soil.csv", parse_dates=["date"], index_col="date")
    return power.join(soil, how="inner")


def long_rows(df, sm_range, loc_id):
    """One row per (day, horizon): features, target (change in sm) and the place and anchor date."""
    past = forecast.build_frame(df, sm_range)
    sm = df["sm"].asfreq("D")
    parts = []
    for h in range(1, forecast.H + 1):
        part = past.join(forecast.future_frame(df, h))
        part["target"] = sm.shift(-h) - sm
        part["loc"], part["anchor"] = loc_id, part.index
        parts.append(part.dropna())
    return pd.concat(parts, ignore_index=True)


def main():
    req = (DATA.parent / "backend" / "requirements.txt").read_text(encoding="utf-8")
    pinned = next(l.split("==")[1] for l in req.splitlines() if l.startswith("scikit-learn=="))
    if sklearn.__version__ != pinned:
        raise SystemExit(f"scikit-learn {sklearn.__version__} here, server runs {pinned}: the model would not load")
    old = forecast.report() or {"locations": {}}

    locs = json.loads((DATA / "locations.json").read_text(encoding="utf-8"))
    frames, stats = {}, {}
    for loc in locs:
        df = load(loc["id"])
        frames[loc["id"]] = df
        tr = df.loc[df.index <= TRAIN_END, "sm"]
        stats[loc["id"]] = (float(tr.quantile(0.1)), float(tr.quantile(0.9)))
    rows = pd.concat([long_rows(frames[l], stats[l], l) for l in frames], ignore_index=True)
    # no training row may look into the test years: its targets and coming weather reach H days ahead
    train = rows["anchor"] <= pd.Timestamp(TRAIN_END) - pd.Timedelta(days=forecast.H)
    test = (rows["anchor"] >= TEST_START) & (rows["anchor"] <= TEST_END)
    X, y = rows[forecast.FEATURES], rows["target"]
    print(f"{int(train.sum())} training rows, {int(test.sum())} test rows")

    models = fit_all(X[train], y[train])
    pred = {k: m.predict(X[test]) for k, m in models.items()}
    t = rows[test].assign(err=y[test] - pred["mid"], lo=pred["low"], hi=pred["high"])
    t["covered"] = (t["target"] >= np.minimum(t["lo"], t["hi"])) & (t["target"] <= np.maximum(t["lo"], t["hi"]))

    imp = permutation_importance(models["mid"], X[test].sample(20000, random_state=0),
                                 y[test].sample(20000, random_state=0), n_repeats=3, random_state=0,
                                 scoring="neg_mean_absolute_error")
    merged = {}
    for f, v in zip(forecast.FEATURES, imp.importances_mean):
        merged[LABELS[f]] = merged.get(LABELS[f], 0) + max(0.0, float(v))
    total = sum(merged.values()) or 1
    importance = [{"input": k, "share": round(v / total, 3)} for k, v in sorted(merged.items(), key=lambda p: -p[1])]

    report = {
        "model": "Gradient-boosted trees (scikit-learn HistGradientBoosting), one model for all places and "
                 "horizons; two more for the 5th and 95th percentile band (aims to hold 80-90% of real values)",
        "version": 2,
        "scikit_learn": sklearn.__version__,
        "target": "Change in ERA5-Land volumetric soil water 0-7 cm (~9 km) 1-14 days ahead. ERA5-Land has a "
                  "value every day since 2015; NASA SMAP passes every 2-3 days, so it is used to check ERA5 "
                  "(smap_agreement per place) and shown next to the forecast",
        "inputs": "Soil moisture now and over the last 7 days; NASA POWER rain, temperature, humidity, sun, wind "
                  "and FAO-56 Hargreaves ET0 over the last 1-30 days; the same weather for the coming days "
                  "(observed in the test, Open-Meteo forecast on the server); time of year",
        "caveat": "The test used the weather that really fell in the coming days. On the server the coming days "
                  "come from a forecast, so errors beyond about day 5 will be larger than shown.",
        "train": f"2015-01-31 to {TRAIN_END}", "test": f"{TEST_START} to {TEST_END}",
        "unit": "volumetric %, m3/m3 x 100", "horizon_days": forecast.H,
        "trained": date.today().isoformat(), "importance": importance, "locations": {},
    }
    for lid, df in frames.items():
        g = t[t["loc"] == lid]
        by_h = g.groupby("h")
        mae = (by_h["err"].apply(lambda e: e.abs().mean()) * 100).tolist()
        base = (by_h["target"].apply(lambda e: e.abs().mean()) * 100).tolist()
        q = by_h["err"].quantile([0.1, 0.9]).unstack().to_numpy()
        cover = by_h["covered"].mean().tolist()
        v1 = old["locations"].get(lid, {}).get("test", {}).get("mae_pct_points")
        season = df.loc[(df.index.month >= 4) & (df.index.month <= 9) & (df.index <= TEST_END), "sm"]
        px = smap.pixel(*next((l["lat"], l["lon"]) for l in locs if l["id"] == lid))
        agree = None
        if px:
            sat = pd.Series(px[1], index=pd.to_datetime(px[0])).dropna()
            j = pd.concat([sat, df["sm"]], axis=1, keys=["smap", "era"], sort=True).dropna()
            if len(j) > 100:
                agree = {"days": int(len(j)), "r": round(float(j["smap"].corr(j["era"])), 2),
                         "dataset": smap.DATASET, "dates": f"{j.index[0].date()} to {j.index[-1].date()}"}
        report["locations"][lid] = {
            "smap_agreement": agree,
            "rows_test": int(len(g)), "sm_range": [round(v, 4) for v in stats[lid]],
            "test": {
                "mae_pct_points": [round(float(v), 2) for v in mae],
                "mae_no_change_baseline": [round(float(v), 2) for v in base],
                "mae_previous_model": v1 if old.get("version") != 2 else
                                      old["locations"][lid]["test"].get("mae_previous_model"),
                "error_quantiles": [[round(float(a), 4), round(float(b), 4)] for a, b in q],
                "band_coverage": [round(float(v), 2) for v in cover],
            },
            "importance": importance,
            # dry: the driest 20% of April-September days in 2015-2024
            "dry_threshold_pct": round(float(season.quantile(0.2)) * 100, 1),
            "wet_threshold_pct": round(float(season.quantile(0.8)) * 100, 1),
        }
        prev = report["locations"][lid]["test"]["mae_previous_model"]
        print(f"{lid}: MAE day 1/7/14 = {mae[0]:.2f} / {mae[6]:.2f} / {mae[13]:.2f} points; "
              f"no-change {base[0]:.2f} / {base[6]:.2f} / {base[13]:.2f}"
              + (f"; old model {prev[0]:.2f} / {prev[6]:.2f} / {prev[13]:.2f}" if prev else "")
              + f"; band holds {cover[6]:.0%} at day 7")
    print("top inputs:", ", ".join(f"{i['input']} {i['share']:.0%}" for i in importance[:5]))

    final = fit_all(X, y)  # all years, for the forecasts the app shows
    (DATA / "model").mkdir(exist_ok=True)
    joblib.dump(final, DATA / "model" / "soil_forecast.joblib", compress=3)
    for p in (DATA / "model").glob("soil_forecast_*.joblib"):
        p.unlink()  # v1 per-place forests
    (DATA / "model" / "model_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
