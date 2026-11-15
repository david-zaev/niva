"""Download NASA SMAP soil moisture for all of North Macedonia, one small window per day.

Dataset: SMAP Enhanced L3 Radiometer Global Daily 9 km EASE-Grid Soil Moisture (SPL3SMP_E), NSIDC.
Each daily file is ~600 MB, so instead of downloading it we ask NASA's OPeNDAP server for only the pixels that
cover North Macedonia (about 20 x 30 pixels, a few kB). Morning (6 am) and evening (6 pm) passes are both kept.

Needs EARTHDATA_TOKEN in .env (project folder) or in the environment.
Writes data/smap/smap_mk.npz: dates, lat, lon, am, pm (m3/m3, NaN where the satellite did not pass or the
retrieval was flagged). Already downloaded days are skipped, so the daily server job only fetches new days.

Usage: python data/scripts/download_smap.py [--start 2015-03-31] [--threads 8]
"""
import argparse
import math
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import numpy as np
import requests

DATA = Path(__file__).resolve().parent.parent
OUT = DATA / "smap" / "smap_mk.npz"
COLLECTION = "C2938664763-NSIDC_CPRD"  # SPL3SMP_E version 6, NSIDC cloud
OPENDAP = f"https://opendap.earthdata.nasa.gov/collections/{COLLECTION}/granules"
BBOX = (40.80, 20.40, 42.40, 23.10)  # lat_min, lon_min, lat_max, lon_max: North Macedonia with a small margin
NCOLS, NROWS, RES = 3856, 1624, 9008.055210146  # EASE-Grid 2.0 global, 9 km


def token() -> str:
    t = os.environ.get("EARTHDATA_TOKEN")
    for env in (DATA.parent / ".env", Path("/opt/niva/.env")):
        if not t and env.exists():
            for line in env.read_text().splitlines():
                if line.startswith("EARTHDATA_TOKEN="):
                    t = line.split("=", 1)[1].strip()
    if not t:
        sys.exit("EARTHDATA_TOKEN missing")
    return t


def ease_rc(lat: float, lon: float) -> tuple[int, int]:
    """Row and column of the EASE-Grid 2.0 global 9 km pixel holding a point (EPSG:6933)."""
    a, e, phi1 = 6378137.0, 0.0818191908426, math.radians(30.0)
    k0 = math.cos(phi1) / math.sqrt(1 - e * e * math.sin(phi1) ** 2)
    s = math.sin(math.radians(lat))
    q = (1 - e * e) * (s / (1 - e * e * s * s) - 1 / (2 * e) * math.log((1 - e * s) / (1 + e * s)))
    x, y = a * k0 * math.radians(lon), a * q / (2 * k0)
    return int((NROWS / 2 * RES - y) // RES), int((x + NCOLS / 2 * RES) // RES)


def window() -> tuple[int, int, int, int]:
    r0, c0 = ease_rc(BBOX[2], BBOX[1])  # north-west corner
    r1, c1 = ease_rc(BBOX[0], BBOX[3])  # south-east corner
    return r0, r1, c0, c1


def granules(start: str, end: str) -> dict[str, str]:
    """date -> granule name, from NASA CMR."""
    out, after = {}, None
    while True:
        h = {"CMR-Search-After": after} if after else {}
        r = requests.get("https://cmr.earthdata.nasa.gov/search/granules.json", headers=h, timeout=120, params={
            "collection_concept_id": COLLECTION, "temporal": f"{start}T00:00:00Z,{end}T23:59:59Z",
            "page_size": 2000, "sort_key": "start_date"})
        r.raise_for_status()
        entries = r.json()["feed"]["entry"]
        for e in entries:
            out[e["time_start"][:10]] = e["title"]
        after = r.headers.get("CMR-Search-After")
        if len(entries) < 2000 or not after:
            return out


def parse_csv(text: str, name: str, shape: tuple[int, int]) -> np.ndarray:
    arr = np.full(shape, np.nan, dtype=np.float32)
    for line in text.splitlines():
        if line.startswith(f"/{name}["):
            i = int(line[line.index("[") + 1:line.index("]")])
            vals = [float(v) for v in line.split(",")[1:]]
            arr[i, :len(vals)] = vals
    arr[(arr < 0) | (arr > 1)] = np.nan  # -9999 fill and impossible values
    return arr


def fetch(session, title: str, win) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    r0, r1, c0, c1 = win
    sel = f"%5B{r0}:{r1}%5D%5B{c0}:{c1}%5D"
    am, pm = "Soil_Moisture_Retrieval_Data_AM", "Soil_Moisture_Retrieval_Data_PM"
    ce = f"/{am}/soil_moisture{sel};/{pm}/soil_moisture_pm{sel};/{am}/latitude{sel};/{am}/longitude{sel}"
    for attempt in range(5):
        try:
            r = session.get(f"{OPENDAP}/{title}.dap.csv?dap4.ce={ce}", timeout=180)
            if r.status_code == 200 and "soil_moisture" in r.text:
                shape = (r1 - r0 + 1, c1 - c0 + 1)
                lat = parse_csv(r.text, f"{am}/latitude", shape)  # lat/lon are outside 0..1 → NaN: re-parse raw
                return (parse_csv(r.text, f"{am}/soil_moisture", shape), parse_csv(r.text, f"{pm}/soil_moisture_pm", shape),
                        raw(r.text, f"{am}/latitude", shape), raw(r.text, f"{am}/longitude", shape))
        except requests.RequestException:
            pass
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed {title}")


def raw(text: str, name: str, shape) -> np.ndarray:
    arr = np.full(shape, np.nan, dtype=np.float32)
    for line in text.splitlines():
        if line.startswith(f"/{name}["):
            i = int(line[line.index("[") + 1:line.index("]")])
            vals = [float(v) for v in line.split(",")[1:]]
            arr[i, :len(vals)] = vals
    arr[arr < -900] = np.nan
    return arr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2015-03-31")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--threads", type=int, default=8)
    args = ap.parse_args()
    win = window()
    shape = (win[1] - win[0] + 1, win[3] - win[2] + 1)
    have = {}
    lat = lon = None
    if OUT.exists():
        with np.load(OUT) as z:  # read each array once: z["am"] decompresses the whole file on every access
            lat, lon, dates, am, pm = z["lat"], z["lon"], z["dates"], z["am"], z["pm"]
        for i, d in enumerate(dates):
            have[str(d)] = (am[i], pm[i])
    todo = {d: t for d, t in granules(args.start, args.end).items() if d not in have}
    if not todo:
        print(f"{len(have)} days on disk, nothing new", flush=True)
        return
    print(f"window rows {win[0]}-{win[1]} cols {win[2]}-{win[3]} ({shape[0]}x{shape[1]} pixels); "
          f"{len(have)} days on disk, {len(todo)} to fetch", flush=True)
    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {token()}"
    lock, done = threading.Lock(), 0

    def save():
        days = sorted(have)
        OUT.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(OUT, dates=np.array(days), lat=lat, lon=lon,
                            am=np.stack([have[d][0] for d in days]), pm=np.stack([have[d][1] for d in days]))

    with ThreadPoolExecutor(args.threads) as pool:
        futs = {pool.submit(fetch, session, t, win): d for d, t in todo.items()}
        for f in as_completed(futs):
            d = futs[f]
            try:
                am, pm, la, lo = f.result()
            except Exception as e:  # one bad day must not stop the rest
                print(f"{d}: {e}", flush=True)
                continue
            with lock:
                have[d] = (am, pm)
                if lat is None:
                    lat, lon = np.nanmean(la, axis=1), np.nanmean(lo, axis=0)
                done += 1
                if done % 200 == 0:
                    print(f"{done}/{len(todo)}", flush=True)
                    save()
    if done:  # nothing new: leave the file alone (rewriting it is the slow part on the 1/8-CPU server)
        save()
    print(f"wrote {OUT}: {len(have)} days", flush=True)


if __name__ == "__main__":
    main()
