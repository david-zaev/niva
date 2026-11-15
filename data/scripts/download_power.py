"""Download NASA POWER daily data for each demo location (no login needed).

    python data/scripts/download_power.py            # 1991-01-01 .. 2025-12-31
    python data/scripts/download_power.py 2026-01-01 2026-11-13   # extra range, appended

Writes data/locations/<id>/power.csv and power_meta.json (dataset, dates, request URL).
"""
import csv
import json
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent
API = "https://power.larc.nasa.gov/api/temporal/daily/point"
# community=AG gives radiation in MJ/m^2/day, which the FAO formulas expect
PARAMS = {
    "T2M_MAX": "t_max",            # °C
    "T2M_MIN": "t_min",            # °C
    "PRECTOTCORR": "rain_mm",      # mm/day, bias-corrected
    "RH2M": "humidity",            # %
    "ALLSKY_SFC_SW_DWN": "solar",  # MJ/m^2/day at the surface
    "WS2M": "wind",                # m/s at 2 m
    "TOA_SW_DWN": "ra",            # MJ/m^2/day at the top of the atmosphere (for ET0)
}
FILL = -999.0


def fetch(lat: float, lon: float, start: str, end: str) -> tuple[dict, str]:
    url = (f"{API}?parameters={','.join(PARAMS)}&community=AG&longitude={lon}&latitude={lat}"
           f"&start={start.replace('-', '')}&end={end.replace('-', '')}&format=JSON")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=180) as r:
                return json.load(r), url
        except Exception as e:  # POWER sometimes times out under load: retry
            print(f"  retry {attempt + 1}: {e}")
            time.sleep(5 * (attempt + 1))
    raise SystemExit(f"POWER request failed: {url}")


def hargreaves_et0(t_max, t_min, ra_mj) -> float | None:
    """FAO-56 Hargreaves reference evapotranspiration, mm/day (ra converted with 0.408)."""
    if None in (t_max, t_min, ra_mj) or t_max < t_min:
        return None
    t_mean = (t_max + t_min) / 2
    return round(0.0023 * 0.408 * ra_mj * (t_mean + 17.8) * (t_max - t_min) ** 0.5, 2)


def main(start="1991-01-01", end=None) -> None:
    end = end or (date.today() - timedelta(days=1)).isoformat()
    locations = json.loads((DATA / "locations.json").read_text(encoding="utf-8"))
    for loc in locations:
        print(f"{loc['id']}: {start} .. {end}")
        d, url = fetch(loc["lat"], loc["lon"], start, end)
        p = d["properties"]["parameter"]
        rows = []
        for day in sorted(p["T2M_MAX"]):
            row = {"date": f"{day[:4]}-{day[4:6]}-{day[6:]}"}
            for key, col in PARAMS.items():
                v = p[key].get(day)
                row[col] = None if v is None or v == FILL else v
            row["et0"] = hargreaves_et0(row["t_max"], row["t_min"], row["ra"])
            del row["ra"]
            rows.append(row)

        out = DATA / "locations" / loc["id"]
        out.mkdir(parents=True, exist_ok=True)
        path = out / "power.csv"
        existing = {}
        if path.exists() and start != "1991-01-01":
            with path.open(encoding="utf-8") as f:
                existing = {r["date"]: r for r in csv.DictReader(f)}
        has_data = lambda r: any(r[c] not in (None, "") for c in ("t_max", "t_min", "rain_mm"))
        merged = {k: r for k, r in {**existing, **{r["date"]: r for r in rows}}.items() if has_data(r)}
        cols = ["date", *PARAMS.values()]
        cols = [c for c in cols if c != "ra"] + ["et0"]
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for k in sorted(merged):
                w.writerow({c: ("" if merged[k][c] is None else merged[k][c]) for c in cols})

        dates = sorted(merged)
        meta = {
            "dataset": "NASA POWER daily (MERRA-2 / CERES SYN1deg), community AG",
            "source_url": "https://power.larc.nasa.gov/",
            "request_url": url,
            "lat": loc["lat"], "lon": loc["lon"],
            "first_date": dates[0], "last_date": dates[-1], "days": len(dates),
            "columns": {"t_max": "°C", "t_min": "°C", "rain_mm": "mm/day (PRECTOTCORR)", "humidity": "% (RH2M)",
                        "solar": "MJ/m²/day (ALLSKY_SFC_SW_DWN)", "wind": "m/s (WS2M)",
                        "et0": "mm/day, FAO-56 Hargreaves from T2M_MAX, T2M_MIN, TOA_SW_DWN"},
            "downloaded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        (out / "power_meta.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  {len(dates)} days -> {path}")


if __name__ == "__main__":
    main(*sys.argv[1:3])
