"""Train and test the soil-moisture forecast for each demo location.

Reads data/locations/<id>/power.csv (NASA POWER) and soil.csv (ERA5-Land 0-7 cm, the SMAP backup).
Test rule (DESIGN.md): train on 2015-2022, test on 2023-2024 data the model never saw, and save that error in
data/model/model_report.json so the app and the slides show the same number. The model that is then saved is
trained again on all years, so it knows the latest seasons.

Train on the PC, then copy data/model/ to the server, which only loads the model and forecasts. A joblib model
file only loads in the scikit-learn version that wrote it, so the PC must have the version pinned in
backend/requirements.txt (the script refuses to run otherwise):
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
from sklearn.ensemble import RandomForestRegressor

DATA = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DATA.parent / "backend"))
import forecast  # noqa: E402  (shared feature code)

TRAIN_END, TEST_START, TEST_END = "2022-12-31", "2023-01-01", "2024-12-31"
LABELS = {"sm": "Soil moisture today", "sm_d3": "Change over the last 3 days", "sm_d7": "Change over the last 7 days",
          "rain_1": "Rain yesterday", "rain_3": "Rain, last 3 days", "rain_7": "Rain, last 7 days",
          "rain_30": "Rain, last 30 days", "et0_7": "Crop water use, last 7 days",
          "et0_30": "Crop water use, last 30 days", "balance_30": "Rain minus water use, last 30 days",
          "tmax_7": "Daytime heat, last 7 days", "tmin_7": "Night temperature, last 7 days",
          "hum_7": "Air humidity, last 7 days", "solar_7": "Sunshine, last 7 days", "wind_7": "Wind, last 7 days",
          "doy_sin": "Time of year", "doy_cos": "Time of year"}


def new_model():
    # 100 trees with leaves of at least 12 days: about 4 MB a file for the 1 GB free server
    return RandomForestRegressor(n_estimators=100, min_samples_leaf=12, max_features=0.5, n_jobs=-1, random_state=0)


def load(loc_id: str) -> pd.DataFrame:
    folder = DATA / "locations" / loc_id
    power = pd.read_csv(folder / "power.csv", parse_dates=["date"], index_col="date")
    soil = pd.read_csv(folder / "soil.csv", parse_dates=["date"], index_col="date")
    return power.join(soil, how="inner")


def main():
    req = (DATA.parent / "backend" / "requirements.txt").read_text(encoding="utf-8")
    pinned = next(l.split("==")[1] for l in req.splitlines() if l.startswith("scikit-learn=="))
    if sklearn.__version__ != pinned:
        raise SystemExit(f"scikit-learn {sklearn.__version__} here, server runs {pinned}: the model would not load")
    report = {
        "model": "Random forest (scikit-learn), 100 trees, predicts the change in soil moisture 1-14 days ahead",
        "scikit_learn": sklearn.__version__,
        "target": "ERA5-Land volumetric soil water 0-7 cm, ~9 km (backup for NASA SMAP, which needs an "
                  "Earthdata login we do not have yet)",
        "inputs": "NASA POWER daily rain, temperature, humidity, sun, wind and FAO-56 Hargreaves ET0; "
                  "soil moisture now and over the last 7 days; time of year",
        "train": f"2015-01-31 to {TRAIN_END}", "test": f"{TEST_START} to {TEST_END}",
        "unit": "volumetric %, m3/m3 x 100", "horizon_days": forecast.H,
        "trained": date.today().isoformat(), "locations": {},
    }
    (DATA / "model").mkdir(exist_ok=True)
    for loc in json.loads((DATA / "locations.json").read_text(encoding="utf-8")):
        lid = loc["id"]
        df = load(lid)
        X, Y = forecast.build_frame(df), forecast.build_targets(df)
        rows = X.join(Y).dropna()
        X, Y = rows[forecast.FEATURES], rows[Y.columns]
        # no training row may look into the test years: its targets reach H days ahead
        train = X.index <= pd.Timestamp(TRAIN_END) - pd.Timedelta(days=forecast.H)
        test = (X.index >= TEST_START) & (X.index <= TEST_END)

        m = new_model().fit(X[train], Y[train])
        pred = m.predict(X[test])
        err = Y[test].to_numpy() - pred                    # true change - predicted change
        mae = np.abs(err).mean(axis=0) * 100               # % points, per horizon
        mae_persist = np.abs(Y[test].to_numpy()).mean(axis=0) * 100  # "no change" baseline
        q = np.percentile(err, [10, 90], axis=0).T         # error band per horizon
        per_tree = np.stack([t.predict(X[test].to_numpy()) for t in m.estimators_])  # trees were fit on arrays
        lo, hi = np.percentile(per_tree, [10, 90], axis=0)
        truth = Y[test].to_numpy()
        tree_cover = ((truth >= lo) & (truth <= hi)).mean(axis=0)

        imp = sorted(zip(forecast.FEATURES, m.feature_importances_), key=lambda p: -p[1])
        merged = {}
        for f, v in imp:  # the two time-of-year columns are one input for people
            merged[LABELS[f]] = merged.get(LABELS[f], 0) + v
        importance = [{"input": k, "share": round(float(v), 3)} for k, v in
                      sorted(merged.items(), key=lambda p: -p[1])]

        season = df.loc[(df.index.month >= 4) & (df.index.month <= 9) & (df.index <= TEST_END), "sm"]
        report["locations"][lid] = {
            "rows_train": int(train.sum()), "rows_test": int(test.sum()),
            "test": {
                "mae_pct_points": [round(float(v), 2) for v in mae],
                "mae_no_change_baseline": [round(float(v), 2) for v in mae_persist],
                "error_quantiles": [[round(float(a), 4), round(float(b), 4)] for a, b in q],
                "tree_spread_coverage": [round(float(v), 2) for v in tree_cover],
            },
            "importance": importance,
            # dry: the driest 20% of April-September days in 2015-2024
            "dry_threshold_pct": round(float(season.quantile(0.2)) * 100, 1),
            "wet_threshold_pct": round(float(season.quantile(0.8)) * 100, 1),
        }
        print(f"{lid}: test MAE day 1 {mae[0]:.2f}, day 7 {mae[6]:.2f}, day 14 {mae[13]:.2f} points "
              f"(no-change {mae_persist[0]:.2f} / {mae_persist[6]:.2f} / {mae_persist[13]:.2f}); "
              f"trees cover {tree_cover[6]:.0%} at day 7; top: {importance[0]['input']}")

        final = new_model().fit(X, Y)  # all years, for the forecasts the app shows
        joblib.dump(final, DATA / "model" / f"soil_forecast_{lid}.joblib", compress=3)
    (DATA / "model" / "model_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
