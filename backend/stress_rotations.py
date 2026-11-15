"""Stress test for the rotation advice: many fields across North Macedonia, each with the advice an agronomist
would expect, checked against what Niva recommends.

    python stress_rotations.py            # uses a throw-away database in the system temp folder

Every case states what a good answer looks like (from standard rotation practice for the region). The general
checks run on every field: options fit the farm type, survive a dry year, and nothing crashes or hangs.
"""
import logging
import os
import sys
import tempfile
import time

os.environ.setdefault("NIVA_DB", os.path.join(tempfile.gettempdir(), "niva_stress.db"))
os.environ["NIVA_WARM"] = "0"
logging.disable(logging.WARNING)

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session  # noqa: E402

import main  # noqa: E402
import rotations  # noqa: E402
import simulate  # noqa: E402
from models import Farm, FieldRow, engine, init_db  # noqa: E402

CS = simulate.crops()
LEGUMES = {k for k, c in CS.items() if c["family"] == "Fabaceae" and not c.get("cover_crop")}
CEREALS = {k for k, c in CS.items() if c["family"] == "Poaceae"}


def square(lat, lon, m=150):
    d_lat, d_lon = m / 111320 / 2, m / (111320 * 0.75) / 2
    return [[lat + d_lat, lon - d_lon], [lat + d_lat, lon + d_lon], [lat - d_lat, lon + d_lon], [lat - d_lat, lon - d_lon]]


def crops_of(r):
    return {c for s in r["seasons"] for c in s}


def mains_of(r):
    return {c for s in r["seasons"] for c in s if not CS[c].get("cover_crop")}


# what a good answer looks like, as checks on the top option (t) against the current rotation (c)
def breaks_family(t, c):
    return len(t["metrics"]["family_breaks"]) < len(c["metrics"]["family_breaks"]), "top option breaks the pest cycle"


def adds_legume(t, c):
    return bool(crops_of(t) & (LEGUMES | {"vetch_oat"})) and t["metrics"]["n_credit_kg_ha"] > c["metrics"]["n_credit_kg_ha"], \
        "top option adds a legume (nitrogen)"


def more_cover(t, c):
    return t["metrics"]["living_cover_pct"] > c["metrics"]["living_cover_pct"], "top option covers the soil longer"


def less_erosion(t, c):
    return t["metrics"]["erosion_index"] < c["metrics"]["erosion_index"] * 0.9, "top option cuts erosion by 10%+"


def no_new_breaks(t, c):
    return len(t["metrics"]["family_breaks"]) <= len(c["metrics"]["family_breaks"]), "top option adds no pest repeats"


def keeps_a_crop(t, c):
    return bool(mains_of(t) & mains_of(c)), "top option keeps one of the farmer's crops"


def not_much_poorer(t, c):
    # pepper and tomato share a family that needs 3 years between plantings, so a pest-safe vegetable rotation
    # grows vegetables one year in three: about 40-45% of the gross income of nightshades every year (before the
    # vegetables' much higher costs). Less than that means the option gave away more income than the pest rule needs.
    return t["metrics"]["gross_eur_ha"] >= 0.4 * c["metrics"]["gross_eur_ha"], "top option keeps at least 40% of gross income"


def less_water(t, c):
    return t["metrics"]["irrigation_mm"] < c["metrics"]["irrigation_mm"], "top option needs less irrigation"


CASES = [
    # name, lat, lon, current rotation, irrigation, checks on the top option
    ("Murtino peppers, drip", 41.4145, 22.7274, [["pepper"], ["pepper"], ["tomato"]], "drip",
     [breaks_family, more_cover, keeps_a_crop, not_much_poorer]),
    ("Gevgelija tomato every year, drip", 41.140, 22.505, [["tomato"]], "drip",
     [breaks_family, more_cover, keeps_a_crop]),
    ("Strumica tomato -> pepper, furrow", 41.437, 22.640, [["tomato"], ["pepper"]], "furrow",
     [breaks_family, keeps_a_crop, not_much_poorer]),
    ("Ovce Pole wheat every year, rain-fed", 41.870, 21.940, [["wheat"]], "none",
     [breaks_family, adds_legume, keeps_a_crop]),
    ("Ovce Pole wheat -> sunflower, rain-fed", 41.800, 21.990, [["wheat"], ["sunflower"]], "none",
     [adds_legume, keeps_a_crop, no_new_breaks]),
    ("Pelagonija wheat -> maize, sprinkler", 41.030, 21.360, [["wheat"], ["maize"]], "sprinkler",
     [adds_legume, keeps_a_crop, no_new_breaks]),
    ("Pelagonija maize every year, sprinkler", 41.080, 21.400, [["maize"]], "sprinkler",
     [breaks_family, adds_legume, keeps_a_crop]),
    ("Prilep tobacco every year, furrow", 41.330, 21.580, [["tobacco"]], "furrow",
     [breaks_family, keeps_a_crop]),
    ("Kumanovo barley -> wheat, rain-fed", 42.120, 21.700, [["barley"], ["wheat"]], "none",
     [breaks_family, adds_legume]),
    ("Belasica foothill peppers, drip (slope)", 41.372, 22.745, [["pepper"], ["tomato"]], "drip",
     [less_erosion, more_cover, keeps_a_crop]),
    ("Kocani maize -> wheat, sprinkler", 41.910, 22.410, [["maize"], ["wheat"]], "sprinkler",
     [adds_legume, keeps_a_crop, no_new_breaks]),
    ("Already good: pepper -> wheat -> bean, drip", 41.420, 22.700, [["vetch_oat", "pepper"], ["wheat"], ["bean"]], "drip",
     [no_new_breaks]),
]


def general(case, data):
    """Checks every answer must pass, whatever the field."""
    cur, opts = data["rotations"][0], data["rotations"][1:]
    kind = rotations.farm_type(cur["seasons"])
    out = []
    out.append((len(opts) >= 2, f"at least 2 options ({len(opts)})"))
    out.append((all(rotations.farm_type(o["seasons"]) == kind for o in opts), f"all options fit a {kind} farm"))
    out.append((all(o["metrics"]["dry_year_yield_pct"] >= rotations.MIN_DRY_YEAR_YIELD for o in opts),
                "every option keeps half the harvest in a dry year"))
    out.append((all(o["seasons"] != cur["seasons"] for o in opts), "current rotation not offered again"))
    out.append((all(o["card"]["why"] for o in opts), "every option says why"))
    return out


def main_():
    init_db()
    c = TestClient(main.app)
    with Session(engine) as s:
        farm = Farm(name="Stress test", village="-")
        s.add(farm)
        s.commit()
        s.refresh(farm)
        fid = farm.id
    failures, rows = 0, []
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, lat, lon, rot, irr, checks in CASES:
        if only and only.lower() not in name.lower():
            continue
        poly = square(lat, lon)
        with Session(engine) as s:
            f = FieldRow(farm_id=fid, name=name, lat=lat, lon=lon, polygon=poly, area_ha=main.area_ha(poly),
                         current_rotation=rot, irrigation=irr)
            s.add(f)
            s.commit()
            s.refresh(f)
            field_id = f.id
        t0 = time.time()
        res = c.get(f"/fields/{field_id}/rotations")
        dt = time.time() - t0
        print(f"\n== {name}  ({dt:.1f} s)")
        if res.status_code != 200:
            print("   FAIL: HTTP", res.status_code, res.text[:200])
            failures += 1
            continue
        d = res.json()
        cur, top = d["rotations"][0], d["rotations"][1] if len(d["rotations"]) > 1 else None
        slope = d["terrain"]["slope_deg"] if d.get("terrain") else None
        print(f"   soil {d['soil'].get('name')}, slope {slope}°, farm type {d['farm_type']}")
        for r in d["rotations"]:
            m = r["metrics"]
            print(f"   {'now' if r['kind'] == 'current' else '   '} {r['score']:>3}  {r['name'][:58]:58} "
                  f"irr {m['irrigation_mm']:>4}  cover {m['living_cover_pct']:>2}%  eros {m['erosion_index']:>3}  "
                  f"N {m['n_credit_kg_ha']:>3}  dry {m['dry_year_yield_pct']:>3}%  €{m['gross_eur_ha']:>6,.0f}  "
                  f"repeats {len(m['family_breaks'])}")
        if d["not_offered"]:
            print("   not offered:", "; ".join(f"{o['name']} ({o['because']})" for o in d["not_offered"]))
        results = general(name, d) + ([chk(top, cur) for chk in checks] if top else [(False, "has a top option")])
        for ok, what in results:
            if not ok:
                failures += 1
            print(f"   {'ok  ' if ok else 'FAIL'} {what}")
        rows.append((name, top["name"] if top else "-", all(ok for ok, _ in results)))
    print("\n== summary")
    for name, top, ok in rows:
        print(f"   {'ok  ' if ok else 'FAIL'} {name:45} -> {top}")
    print(f"\n{failures} failed check(s)")
    return failures


if __name__ == "__main__":
    sys.exit(1 if main_() else 0)
