"""Plant facts for Macedonian crops (data/rotation/plants_mk.json): which crop may follow which, how long before a
crop may come back, which crops need irrigation, and which soils and pH suit them. Used to keep the advice within
agronomic rules; the water, yield and income numbers still come from the NASA-driven simulation."""
import json
from functools import lru_cache
from pathlib import Path

import simulate

PATH = Path(__file__).resolve().parent.parent / "data" / "rotation" / "plants_mk.json"


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def source() -> str:
    return _data()["source"]


@lru_cache(maxsize=1)
def by_crop() -> dict:
    """Plant facts keyed by the model's crop id."""
    return {p["ours"]: p for p in _data()["plants"] if p["ours"]}


def _mains(season):
    cs = simulate.crops()
    return [c for c in season if not cs[c].get("cover_crop")]


def masis_class(soil: dict) -> str | None:
    """The MaSIS soil class a 250 m soil map can tell apart: heavy clay ~ smolnica, very sandy ~ sandy, else loam.
    Alluvial soil and terra rossa need a geology map, so they are never assigned."""
    clay, sand = soil.get("clay_pct"), soil.get("sand_pct")
    if clay is None or sand is None:
        return None
    return "smolnica" if clay >= 40 else "sandy" if sand >= 70 else "loam"


SOIL_WORDS = {"smolnica": "heavy clay (smolnica)", "sandy": "sandy soil", "loam": "loam",
              "alluvial": "alluvial soil", "terra_rossa": "terra rossa"}


def rule_breaks(seasons: list[list[str]], rainfed: bool) -> list[str]:
    """Plain sentences for every rule the rotation breaks; empty when it keeps them all."""
    cs, pf = simulate.crops(), by_crop()
    out = []
    L = len(seasons)
    for k, season in enumerate(seasons):
        for c in _mains(season):
            p = pf.get(c)
            if not p:
                continue
            perennial = cs[c]["kind"] == "perennial"
            for b in _mains(seasons[(k - 1) % L]):
                # a perennial (alfalfa) in its second year is the same planting, not a crop after itself
                if (b != c or not perennial) and pf.get(b) and pf[b]["id"] in p["never_after"]:
                    out.append(f"{cs[c]['name']} must not follow {cs[b]['name'].lower()}: pests, diseases or "
                               f"nutrients carry over.")
            if rainfed and p["needs_irrigation"]:
                out.append(f"{cs[c]['name']} needs irrigation, and this field has none.")
    # a cover crop counts too: it is a planting of its own, and a legume cover right after a legume crop (vetch
    # after beans) keeps their shared root rots and pests alive, as does a legume crop right after a legume cover
    flat = [c for s in seasons for c in s]
    for i, c in enumerate(flat):
        b = flat[i - 1]
        if b == c or not (cs[c].get("cover_crop") or cs[b].get("cover_crop")):
            continue
        pc, pb = pf.get(c), pf.get(b)
        if cs[b]["family"] == cs[c]["family"] or (pc and pb and pb["id"] in pc["never_after"]):
            out.append(f"{cs[c]['name']} must not follow {cs[b]['name'].lower()}: pests, diseases or "
                       f"nutrients carry over.")
    for c in {c for s in seasons for c in _mains(s)}:
        p = pf.get(c)
        if not p:
            continue
        # each season is a new planting of an annual; a perennial's planting runs over its consecutive seasons
        perennial = cs[c]["kind"] == "perennial"
        starts = [k for k in range(L) if c in seasons[k] and (not perennial or c not in seasons[(k - 1) % L])]
        gap = min((((starts[(j + 1) % len(starts)] - starts[j]) % L) or L for j in range(len(starts))), default=1)
        if gap < p["min_return_years"]:
            out.append(f"{cs[c]['name']} comes back after {gap} year(s); it needs {p['min_return_years']} years "
                       f"between crops on the same field.")
    return sorted(set(out))


def good_pairs(seasons: list[list[str]]) -> list[str]:
    """Crop pairs where the crop follows one its plant facts list as a best predecessor, e.g. 'wheat after alfalfa'."""
    cs, pf = simulate.crops(), by_crop()
    out = []
    L = len(seasons)
    for k, season in enumerate(seasons):
        for c in _mains(season):
            p = pf.get(c)
            for b in _mains(seasons[(k - 1) % L]):
                if p and b != c and pf.get(b) and pf[b]["id"] in p["best_after"]:
                    out.append(f"{cs[c]['name'].lower()} after {cs[b]['name'].lower()}")
    return list(dict.fromkeys(out))


def site_warnings(seasons: list[list[str]], soil: dict) -> list[str]:
    """Crops whose preferred soil class or pH does not match the field's soil map."""
    cs, pf = simulate.crops(), by_crop()
    cls = masis_class(soil)
    ph = soil.get("ph")
    out = []
    for c in dict.fromkeys(c for s in seasons for c in _mains(s)):
        p = pf.get(c)
        if not p:
            continue
        if cls and cls not in p["soils"]:
            out.append(f"{cs[c]['name']} grows best on {', '.join(SOIL_WORDS[s] for s in p['soils'])}; the soil map "
                       f"shows {SOIL_WORDS[cls]} here.")
        if ph and not p["ph"][0] - 0.3 <= ph <= p["ph"][1] + 0.3:
            out.append(f"{cs[c]['name']} wants a soil pH of {p['ph'][0]}–{p['ph'][1]}; the soil map shows {ph} here.")
    return out
