"""North Macedonia's border. Niva's prices, crop calendar, plant rules and soil fallback are Macedonian, so a field
outside the country would get advice that looks real but is not. The same border (data/geo/mk_border.json, from
OpenStreetMap) limits the web map."""
import json

import nasa

_ring = None


def ring() -> list[list[float]]:
    global _ring
    if _ring is None:
        d = json.loads((nasa.DATA_DIR / "geo" / "mk_border.json").read_text(encoding="utf-8"))
        _ring = d["ring_lat_lon"]
    return _ring


def inside(lat: float, lon: float) -> bool:
    """Ray casting: is the point inside the border?"""
    r = ring()
    hit = False
    for i in range(len(r)):
        (y1, x1), (y2, x2) = r[i - 1], r[i]
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def polygon_inside(poly: list[list[float]]) -> bool:
    return all(inside(p[0], p[1]) for p in poly)


MESSAGE = "Niva works only for fields in North Macedonia: its prices, sowing dates and plant rules are Macedonian."
MESSAGE_MK = "Нива работи само за ниви во Северна Македонија: цените, роковите за сеидба и правилата за растенијата се македонски."
