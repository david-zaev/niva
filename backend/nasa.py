"""NASA data for fields: reads the files the data scripts write into data/ (see data/scripts/).

A field uses the demo location in its region, or the nearest demo location (marked lower confidence).
"""
import csv
import json
import math
import os
from functools import lru_cache
from pathlib import Path

# Server: /opt/niva/data. Locally: <repo>/data
DATA_DIR = Path(os.getenv("NIVA_DATA", Path(__file__).resolve().parent.parent / "data"))


@lru_cache
def locations() -> list[dict]:
    return json.loads((DATA_DIR / "locations.json").read_text(encoding="utf-8"))


def km_between(lat1, lon1, lat2, lon2) -> float:
    p = math.pi / 180
    a = (math.sin((lat2 - lat1) * p / 2) ** 2
         + math.cos(lat1 * p) * math.cos(lat2 * p) * math.sin((lon2 - lon1) * p / 2) ** 2)
    return 12742 * math.asin(math.sqrt(a))


def location_for(lat: float, lon: float, region: str | None) -> tuple[dict, float, bool]:
    """(location, distance_km, exact). exact = the field is in a demo region."""
    locs = locations()
    by_id = {l["id"]: l for l in locs}
    if region in by_id:
        l = by_id[region]
        return l, round(km_between(lat, lon, l["lat"], l["lon"]), 1), True
    l = min(locs, key=lambda l: km_between(lat, lon, l["lat"], l["lon"]))
    return l, round(km_between(lat, lon, l["lat"], l["lon"]), 1), False


def indicators(location_id: str) -> dict | None:
    path = DATA_DIR / "locations" / location_id / "indicators.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def latest_power(location_id: str) -> dict | None:
    """Most recent day in power.csv with temperature data, plus its source line."""
    path = DATA_DIR / "locations" / location_id / "power.csv"
    if not path.exists():
        return None
    last = None
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["t_max"]:
                last = row
    if not last:
        return None
    num = lambda k: float(last[k]) if last.get(k) else None
    return {
        "date": last["date"],
        "t_max": num("t_max"), "t_min": num("t_min"),
        "rain_mm": num("rain_mm"), "humidity_pct": num("humidity"),
        "dataset": "NASA POWER daily",
    }


def read_data_file(name: str):
    """crops.json, prices.json, buyers.json: hand-made by the Data role. None until they exist."""
    path = DATA_DIR / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
