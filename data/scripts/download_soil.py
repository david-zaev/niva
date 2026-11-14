"""Download daily top-soil moisture for the 3 demo locations.

SMAP needs an Earthdata login the team does not have yet, so this is the planned backup (PLAN.md, "Backup if SMAP
is late"): ERA5-Land volumetric soil water, 0-7 cm, from the Open-Meteo historical API (free, no login). ERA5-Land
is a ~9 km reanalysis, the same grid size as SMAP L4. Hourly values are averaged to one value per local day.

Writes data/locations/<id>/soil.csv (date, sm) in m3/m3 and soil_meta.json.
Usage: python data/scripts/download_soil.py [--start 2015-01-01]
"""
import argparse
import csv
import json
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent
URL = "https://archive-api.open-meteo.com/v1/archive"
VAR = "soil_moisture_0_to_7cm"


def fetch(lat: float, lon: float, start: str, end: str) -> dict[str, float]:
    q = urllib.parse.urlencode({"latitude": lat, "longitude": lon, "start_date": start, "end_date": end,
                                "hourly": VAR, "models": "era5_land", "timezone": "Europe/Skopje"})
    with urllib.request.urlopen(f"{URL}?{q}", timeout=120) as r:
        h = json.load(r)["hourly"]
    by_day = defaultdict(list)
    for t, v in zip(h["time"], h[VAR]):
        if v is not None:
            by_day[t[:10]].append(v)
    # keep only full days (24 hourly values), so the last, partial day is never half a day
    return {d: round(sum(v) / len(v), 4) for d, v in by_day.items() if len(v) == 24}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2015-01-01")
    args = ap.parse_args()
    end = (date.today() - timedelta(days=1)).isoformat()
    for loc in json.loads((DATA / "locations.json").read_text(encoding="utf-8")):
        days = {}
        y0 = int(args.start[:4])
        for y in range(y0, date.today().year + 1, 4):  # 4-year chunks keep each answer small
            s = args.start if y == y0 else f"{y}-01-01"
            e = min(f"{y + 3}-12-31", end)
            days.update(fetch(loc["lat"], loc["lon"], s, e))
        out = DATA / "locations" / loc["id"]
        with open(out / "soil.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["date", "sm"])
            for d in sorted(days):
                w.writerow([d, days[d]])
        meta = {"dataset": "ERA5-Land volumetric soil water, layer 0-7 cm (via Open-Meteo historical API)",
                "unit": "m3/m3", "grid_km": 9, "start": min(days), "end": max(days), "rows": len(days),
                "note": "Backup for NASA SMAP until an Earthdata login is available.",
                "retrieved": date.today().isoformat()}
        (out / "soil_meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        print(loc["id"], meta["start"], meta["end"], meta["rows"])


if __name__ == "__main__":
    main()
