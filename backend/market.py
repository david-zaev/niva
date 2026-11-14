"""Regional market view (Main_Prompt section 4): ZPIS prices + MakStat production per region and year.

What is real: ZPIS farm-gate / wholesale prices (data/prices.json) and MakStat sown area and production per
municipality, summed per region (data/production.json). What is not published anywhere we could find: tonnes
actually sold or bought out per region. That column stays empty and the app says so; the "trend" below is
about how much the region grows, not how much it sells.
"""
import math

import nasa

# approximate centre of each market region's farmland (for picking the region nearest a field)
REGION_POINTS = {"strumica": (41.44, 22.64), "pelagonija": (41.15, 21.45), "ovche-pole": (41.865, 21.94),
                 "polog": (41.9, 20.95), "tikvesh": (41.45, 22.0), "kochani": (41.9, 22.4),
                 "skopje": (41.95, 21.55)}


def region_for(lat: float, lon: float) -> tuple[str, float]:
    best = min(REGION_POINTS, key=lambda r: nasa.km_between(lat, lon, *REGION_POINTS[r]))
    return best, round(nasa.km_between(lat, lon, *REGION_POINTS[best]), 1)


def trend(series: list[dict]) -> dict | None:
    """Last 3 years vs the 3 before: change in production and sown area, in %."""
    s = [x for x in series if x.get("production_t") is not None]
    if len(s) < 4:
        return None
    last, before = s[-3:], s[-6:-3]
    avg = lambda rows, k: sum(r.get(k) or 0 for r in rows) / len(rows)
    p1, p0 = avg(last, "production_t"), avg(before, "production_t")
    a1, a0 = avg(last, "area_ha"), avg(before, "area_ha")
    pc = None if p0 == 0 else round((p1 - p0) / p0 * 100)
    ac = None if a0 == 0 else round((a1 - a0) / a0 * 100)
    direction = "steady" if pc is None or abs(pc) < 10 else "up" if pc > 0 else "down"
    return {"production_change_pct": pc, "area_change_pct": ac, "direction": direction,
            "last_years": f"{last[0]['year']}-{last[-1]['year']}", "before_years": f"{before[0]['year']}-{before[-1]['year']}",
            "production_t": round(p1), "area_ha": round(a1),
            "yield_t_ha": round(p1 / a1, 1) if a1 else None}


def regional_trends(region: str) -> dict:
    prod = nasa.read_data_file("production.json") or {"regions": {}}
    crops = prod["regions"].get(region, {}).get("crops", {})
    return {c: trend(v) for c, v in crops.items()}


def sell_places(lat: float, lon: float, p: dict, coords: dict) -> list[dict]:
    """Every ZPIS place that reported this product, with road-free distance from the field. Real names only."""
    out = []
    for x in p.get("places", []):
        c = coords.get(x["place"])
        km = round(nasa.km_between(lat, lon, c["lat"], c["lon"])) if c else None
        out.append({"place": x["place"], "price": x["price"], "km": km, "lat": c and c["lat"], "lon": c and c["lon"]})
    return out


def view(lat: float, lon: float) -> dict:
    region, km = region_for(lat, lon)
    prod = nasa.read_data_file("production.json") or {"regions": {}, "years": []}
    prices = nasa.read_data_file("prices.json") or {"prices": []}
    crops = {c["id"]: c for c in (nasa.read_data_file("crops.json") or {"crops": []})["crops"]}
    loc, _, _ = nasa.location_for(lat, lon, None)
    coords = (nasa.read_data_file("zpis_places.json") or {}).get("places", {})
    price_by_crop = {}
    for p in prices.get("prices", []):
        price_by_crop.setdefault(p["crop"], []).append(p)
    reg = prod["regions"].get(region, {})
    rows = []
    for cid, series in reg.get("crops", {}).items():
        t = trend(series)
        ps = price_by_crop.get(cid, [])
        local = next((p["local"].get(loc["id"]) for p in ps if p.get("local", {}).get(loc["id"]) is not None), None)
        places = sell_places(lat, lon, ps[0], coords) if ps else []
        near = [x for x in places if x["km"] is not None and x["km"] <= 60]
        if local is None and near:
            local = min(near, key=lambda x: x["km"])["price"]
        rows.append({"crop": cid, "name": crops.get(cid, {}).get("name", cid), "name_mk": crops.get(cid, {}).get("name_mk"),
                     "series": series, "trend": t, "sold_t": None,
                     "prices": [{"price": p["price"], "market": p["market"], "scope": p.get("scope"), "url": p.get("url"),
                                 "product": p.get("product")} for p in ps],
                     "places": places,
                     "local_price": local})
    for cid, ps in price_by_crop.items():
        if cid not in reg.get("crops", {}):
            rows.append({"crop": cid, "name": crops.get(cid, {}).get("name", cid), "name_mk": crops.get(cid, {}).get("name_mk"),
                         "series": [], "trend": None, "sold_t": None,
                         "prices": [{"price": p["price"], "market": p["market"], "scope": p.get("scope"), "url": p.get("url"),
                                     "product": p.get("product")} for p in ps],
                         "places": sell_places(lat, lon, ps[0], coords), "local_price": None})
    rows.sort(key=lambda r: -((r["trend"] or {}).get("production_t") or 0))
    buyers = nasa.read_data_file("buyers.json") or {}
    return {
        "region": region, "region_name": reg.get("name"), "region_name_mk": reg.get("name_mk"),
        "distance_km": km, "municipalities": reg.get("municipalities", []), "crops": rows,
        "sold_note": prod.get("sold_note"), "currency": prices.get("currency", "MKD/kg"),
        "price_retrieved": prices.get("retrieved"),
        "buyers": [b for b in buyers.get("buyers", []) if region in b.get("regions", [region])],
        "sources": [
            {"dataset": "MakStat area and production of crops by municipality (PxWeb)",
             "dates": f"{prod['years'][0]}-{prod['years'][-1]}, retrieved {prod.get('retrieved')}" if prod.get("years") else "not downloaded"},
            {"dataset": "ZPIS prices (Ministry of Agriculture)", "dates": f"retrieved {prices.get('retrieved')}"},
            {"dataset": "Place locations: OpenStreetMap Nominatim", "dates": "town / municipality centres"},
        ],
    }
