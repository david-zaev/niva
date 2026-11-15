"""Create the Murtino demo farm and pre-download its NASA data so the demo works without waiting (or wifi).

    python seed.py            # create the farm if missing, then cache POWER, slope, NDVI and rotations
    python seed.py --reset    # delete the database first

The outlines follow field edges visible on the Esri World Imagery photo of Murtino (traced by hand). The rotations
and settings are examples for the demo, not a real farmer's records.
"""
import sys
import threading

from sqlmodel import Session, select

import main
import power
from models import DB_PATH, Farm, FieldRow, engine, init_db


def px(x0, y0, step):
    return lambda pts: [[round(y0 - y * step, 6), round(x0 + x * step, 6)] for x, y in pts]


north = px(22.722, 41.428, 0.000012)   # zoomed photo north of the village, 12 µ° per pixel
south = px(22.730, 41.3925, 0.000015)  # zoomed photo of the Belasica foothills

FIELDS = [
    dict(name="Field by the road", polygon=north([(475, 92), (535, 92), (537, 158), (474, 158)]),
         current_rotation=[["pepper"], ["pepper"], ["tomato"]], irrigation="drip",
         sensor={"note": "ESP32 in the middle of the field"},
         notes="Small vegetable plot north of the village, like most in the valley."),
    dict(name="Big field", polygon=north([(865, 2), (998, 2), (998, 330), (940, 325), (762, 290), (800, 200),
                                          (840, 100)]),
         current_rotation=[["wheat"], ["maize"]], irrigation="sprinkler",
         notes="Part of the large open field east of the road."),
    dict(name="Hillside field", polygon=south([(762, 122), (822, 120), (824, 160), (764, 162)]),
         current_rotation=[["tomato"], ["pepper"]], irrigation="drip",
         notes="At the foot of Belasica, 4-5° slope: erosion matters here."),
]


def run(reset: bool = False) -> None:
    if reset and DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    with Session(engine) as s:
        farm = s.exec(select(Farm).order_by(Farm.id)).first()
        if not farm:
            farm = Farm(name="Demo farm, Murtino", village="Murtino, Strumica")
            s.add(farm)
            s.commit()
            s.refresh(farm)
        for d in FIELDS:
            if s.exec(select(FieldRow).where(FieldRow.farm_id == farm.id, FieldRow.name == d["name"])).first():
                continue
            lat, lon = main.centroid(d["polygon"])
            s.add(FieldRow(farm_id=farm.id, lat=lat, lon=lon, area_ha=main.area_ha(d["polygon"]), **d))
        s.commit()
        fields = s.exec(select(FieldRow).where(FieldRow.farm_id == farm.id)).all()
        print(f"farm {farm.id}: {[(f.id, f.name, f.area_ha) for f in fields]}")
        print("NASA POWER:", power.ensure(fields[0].lat, fields[0].lon))
        threads = []
        for f in fields:
            print(f"field {f.id}: slope", main.field_terrain(f))
            main.ranking(f)
            t = threading.Thread(target=lambda f=f: print(f"field {f.id}: NDVI",
                                                          bool(main.ndvi.series(f.lat, f.lon, f.polygon))))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
    print("done")


if __name__ == "__main__":
    run("--reset" in sys.argv)
