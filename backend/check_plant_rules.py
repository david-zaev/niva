"""Does Niva's advice agree with the plant facts in data/rotation/plants_mk.json, and with the real NASA data?

For many places in North Macedonia, with and without the farmer's current crops, every rotation Niva offers is
checked for:
  never_after   a crop sown right after one it must not follow (pests, disease, nutrients)
  min_return    a crop back on the same field sooner than its minimum number of years
  irrigation    a crop that needs irrigation offered for a rain-fed field
  plant_next    the first crop to plant next clashes with the farmer's last crop
and, as warnings (the advice can still be right):
  soil          the field's soil is not one the crop prefers (MaSIS classes, from the 250 m soil map)
  ph            the field's pH is outside the crop's range
  sowing        NASA soil temperature in the sowing week is below the crop's minimum, in most years
It also compares the model's own crop parameters (Kc, minimum return) with the plant facts.

Run:  NIVA_DB=<temp file> python check_plant_rules.py
"""
import json
import os
import sys
import tempfile
from pathlib import Path

if "NIVA_DB" not in os.environ:
    os.environ["NIVA_DB"] = os.path.join(tempfile.mkdtemp(), "check.db")
sys.stdout.reconfigure(encoding="utf-8")

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import power  # noqa: E402
import simulate  # noqa: E402

PLANTS = json.loads((Path(__file__).resolve().parent.parent / "data/rotation/plants_mk.json").read_text(encoding="utf-8"))
BY_OURS = {p["ours"]: p for p in PLANTS["plants"] if p["ours"]}
BY_ID = {p["id"]: p for p in PLANTS["plants"]}

PLACES = [  # name, lat, lon, irrigation, current crops (empty = not given)
    ("Murtino, drip", 41.4145, 22.7274, "drip", []),
    ("Murtino, rain-fed", 41.4145, 22.7274, "none", []),
    ("Strumica, drip", 41.4378, 22.6427, "drip", []),
    ("Gevgelija, drip", 41.1392, 22.5025, "drip", []),
    ("Ovče Pole, rain-fed", 41.80, 21.95, "none", []),
    ("Pelagonija, rain-fed", 41.10, 21.45, "none", []),
    ("Pelagonija, sprinkler", 41.10, 21.45, "sprinkler", []),
    ("Prilep, rain-fed", 41.35, 21.55, "none", []),
    ("Kumanovo, rain-fed", 42.13, 21.71, "none", []),
    ("Kočani, furrow", 41.92, 22.41, "furrow", []),
    ("Tetovo, sprinkler", 42.01, 20.97, "sprinkler", []),
    ("Berovo, rain-fed", 41.70, 22.85, "none", []),
    ("Veles, rain-fed", 41.72, 21.78, "none", []),
    ("Murtino, drip, grows pepper-pepper-tomato", 41.4145, 22.7274, "drip", [["pepper"], ["pepper"], ["tomato"]]),
    ("Ovče Pole, rain-fed, grows wheat-wheat", 41.80, 21.95, "none", [["wheat"], ["wheat"]]),
    ("Prilep, rain-fed, grows tobacco-tobacco", 41.35, 21.55, "none", [["tobacco"], ["tobacco"]]),
    ("Pelagonija, sprinkler, grows maize-maize", 41.10, 21.45, "sprinkler", [["maize"], ["maize"]]),
]


def masis_class(soil: dict) -> str | None:
    """The MaSIS soil class the 250 m soil map can tell apart: heavy clay ~ smolnica, very sandy ~ sandy, else loam.
    Alluvial and terra rossa need a geology map, so they are never assigned here."""
    clay, sand = soil.get("clay_pct"), soil.get("sand_pct")
    if clay is None or sand is None:
        return None
    return "smolnica" if clay >= 40 else "sandy" if sand >= 70 else "loam"


def mains(season):
    cs = simulate.crops()
    return [c for c in season if not cs[c].get("cover_crop")]


def rule_breaks(seasons: list[list[str]], rainfed: bool) -> list[str]:
    cs = simulate.crops()
    out = []
    L = len(seasons)
    for k, season in enumerate(seasons):
        prev_main = mains(seasons[(k - 1) % L])
        for i, c in enumerate(season):
            p = BY_OURS.get(c)
            if not p:
                continue
            before = set(prev_main) | ({season[i - 1]} if i else set())
            perennial = cs[c]["kind"] == "perennial"
            for b in before:
                bp = BY_OURS.get(b)
                if b == c and perennial:  # alfalfa's second year is the same planting
                    continue
                if bp and bp["id"] in p["never_after"] and not cs[c].get("cover_crop"):
                    out.append(f"never_after: {cs[c]['name']} after {cs[b]['name']}")
            if rainfed and p["needs_irrigation"] and not cs[c].get("cover_crop"):
                out.append(f"irrigation: {cs[c]['name']} needs irrigation, field is rain-fed")
    # minimum return: distance between the starts of two plantings of the same main crop, going round the cycle
    for c in {c for s in seasons for c in mains(s)}:
        p = BY_OURS.get(c)
        if not p:
            continue
        perennial = cs[c]["kind"] == "perennial"  # an annual sown two years running is two plantings
        starts = [k for k in range(L) if c in seasons[k] and (not perennial or c not in seasons[(k - 1) % L])]
        if not starts:  # grown every season
            out.append(f"min_return: {cs[c]['name']} every year, needs {p['min_return_years']}")
            continue
        gaps = [((starts[(j + 1) % len(starts)] - starts[j]) % L) or L for j in range(len(starts))]
        if min(gaps) < p["min_return_years"]:
            out.append(f"min_return: {cs[c]['name']} back after {min(gaps)} year(s), needs {p['min_return_years']}")
    return sorted(set(out))


def warnings(seasons, soil, w) -> list[str]:
    cs = simulate.crops()
    out = []
    cls = masis_class(soil)
    for c in {c for s in seasons for c in mains(s)}:
        p = BY_OURS.get(c)
        if not p:
            continue
        if cls and cls not in p["soils"]:
            out.append(f"soil: {cs[c]['name']} prefers {'/'.join(p['soils'])}, field soil is {cls}")
        if soil.get("ph") and not p["ph"][0] - 0.3 <= soil["ph"] <= p["ph"][1] + 0.3:
            out.append(f"ph: {cs[c]['name']} wants pH {p['ph'][0]}-{p['ph'][1]}, field {soil['ph']}")
        m, d = (int(x) for x in cs[c]["sow"].split("-")[:2])
        cold = 0
        years = sorted(set(w.index.year))[1:-1]
        for y in years:
            wk = w.loc[f"{y}-{m:02d}-{d:02d}":].head(7)["soil_t"]
            if len(wk) and wk.mean() < p["min_sow_soil_c"]:
                cold += 1
        if years and cold / len(years) > 0.5:
            out.append(f"sowing: {cs[c]['name']} sown {m:02d}-{d:02d}: soil below {p['min_sow_soil_c']} °C in "
                       f"{cold} of {len(years)} years (NASA POWER)")
    return sorted(set(out))


def compare_parameters():
    cs = simulate.crops()
    print("== Model parameters vs plant facts")
    for c, p in BY_OURS.items():
        o = cs[c]
        diff = [f"Kc {k} {a}→{b}" for k, a, b in zip(("ini", "mid", "end"), o["kc"], p["kc"]) if abs(a - b) > 0.15]
        if not o.get("cover_crop") and o["min_return"] != p["min_return_years"]:
            diff.append(f"min return {o['min_return']}→{p['min_return_years']}")
        if p["family"] != o["family"]:
            diff.append(f"family {o['family']}→{p['family']}")
        print(f"  {o['name']:16} {'; '.join(diff) if diff else 'agrees'}")
    missing = [p["name_mk"] for p in PLANTS["plants"] if not p["ours"]]
    print(f"  in the plant facts but not in the model (no yield/price data): {', '.join(missing)}")


def main_check():
    compare_parameters()
    c = TestClient(main.app)
    errors = warns = offered = 0
    with c:
        farm = c.post("/farms", json={"name": "check"}).json()["id"]
        for name, lat, lon, irr, cur in PLACES:
            d = 0.002
            poly = [[lat, lon], [lat + d, lon], [lat + d, lon + d], [lat, lon + d]]
            fid = c.post(f"/farms/{farm}/fields", json={"name": name, "polygon": poly, "irrigation": irr,
                                                       "current_rotation": cur}).json()["id"]
            r = c.get(f"/fields/{fid}/rotations")
            if r.status_code != 200:
                print(f"\n== {name}: HTTP {r.status_code} {r.text[:200]}")
                errors += 1
                continue
            j = r.json()
            soil, w = j["soil"], power.frame(lat, lon)
            print(f"\n== {name}  (soil {masis_class(soil)}, pH {soil.get('ph')})")
            for o in j["rotations"]:
                if o.get("kind") == "current":
                    continue
                offered += 1
                br = rule_breaks(o["seasons"], irr == "none")
                if cur:
                    first = [s["crop"] for s in o["plant_next"][0]["steps"] if not s["cover"]]
                    last = mains(cur[-1])
                    for f_ in first:
                        fp = BY_OURS.get(f_)
                        for l_ in last:
                            if fp and BY_OURS.get(l_) and BY_OURS[l_]["id"] in fp["never_after"]:
                                br.append(f"plant_next: {f_} right after the farmer's {l_}")
                wn = warnings(o["seasons"], soil, w)
                errors += len(br)
                warns += len(wn)
                nxt = " → ".join(" + ".join(s["name"] for s in p["steps"]) for p in o["plant_next"])
                print(f"  {'FAIL' if br else 'ok  '} {o['name']}   [next: {nxt}]")
                for x in br:
                    print(f"         ✗ {x}")
                for x in wn:
                    print(f"         · {x}")
            if not [o for o in j["rotations"] if o.get("kind") != "current"]:
                print("  (no options offered)")
    print(f"\n{offered} options checked: {errors} rule breaks, {warns} warnings")
    return errors


if __name__ == "__main__":
    sys.exit(1 if main_check() else 0)
