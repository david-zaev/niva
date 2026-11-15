"""Download NASA NASADEM elevation (SRTM reprocessed, 1 arc-second ≈ 30 m) for North Macedonia.

Dataset: NASADEM_HGT v001, NASA LP DAAC (Earthdata login). Nine 1°x1° tiles cover the country (~14 MB each zipped).
Each tile is unzipped to data/dem/<tile>.hgt (3601 x 3601 big-endian int16 metres), which backend/terrain.py reads
directly to get elevation and slope under any field.

Needs EARTHDATA_TOKEN in .env or the environment.
Usage: python data/scripts/download_dem.py
"""
import io
import zipfile
from pathlib import Path

import requests

from download_smap import token

DATA = Path(__file__).resolve().parent.parent
OUT = DATA / "dem"
URL = "https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/NASADEM_HGT.001/NASADEM_HGT_{t}/NASADEM_HGT_{t}.zip"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["Authorization"] = f"Bearer {token()}"
    for lat in (40, 41, 42):
        for lon in (20, 21, 22):
            tile = f"n{lat:02d}e{lon:03d}"
            if (OUT / f"{tile}.hgt").exists():
                print(f"{tile}: already here")
                continue
            r = s.get(URL.format(t=tile), timeout=600)
            if r.status_code == 404:
                print(f"{tile}: no tile (all water)")
                continue
            r.raise_for_status()
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                name = next(n for n in z.namelist() if n.endswith(".hgt"))
                (OUT / f"{tile}.hgt").write_bytes(z.read(name))
            print(f"{tile}: {len(r.content) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
