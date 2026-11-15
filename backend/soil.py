"""Soil water properties for the simulator: the regional default, and what the ESP32 soil test measured.

Field capacity (FC) and wilting point (WP) per texture class follow FAO-56 table 19 (middle of each range).
Runoff uses the USDA SCS curve number for bare row-crop land, by hydrologic soil group (A fast-draining to
D slow); drain_mm_day is how much water above field capacity can drain out of the root zone in a day.

The ESP32's capacitive probe is calibrated in the firmware so that 0 % = dry air and 100 % = standing in water.
Water-saturated soil is close to its porosity (about 0.45 m3/m3 for loams), so we read soil_pct as
theta = 0.02 + soil_pct / 100 * (0.45 - 0.02). This is an approximation: the soil test's ranking of soils
(fast/slow, holds more/less) is more reliable than its absolute numbers.
"""
THETA_RES, THETA_SAT = 0.02, 0.45

CLASSES = {
    "sandy-loam": {"name": "Sandy loam", "fc": 0.18, "wp": 0.08, "cn": 72, "drain_mm_day": 60, "hsg": "A"},
    "loam":       {"name": "Loam",       "fc": 0.27, "wp": 0.12, "cn": 80, "drain_mm_day": 25, "hsg": "B"},
    "clay-loam":  {"name": "Clay loam",  "fc": 0.33, "wp": 0.20, "cn": 85, "drain_mm_day": 10, "hsg": "C"},
    "clay":       {"name": "Clay",       "fc": 0.38, "wp": 0.25, "cn": 89, "drain_mm_day": 4,  "hsg": "D"},
}

# Strumica valley floor: alluvial soils (Fluvisols) of loam texture are the most common class on the MASIS /
# FAO soil maps of the valley. A field without a sensor test uses this and is marked "estimated".
DEFAULT = {**CLASSES["loam"], "texture": "loam", "measured": False,
           "label": "Estimated: alluvial loam (Fluvisol), typical of the Strumica valley floor",
           "source": "FAO-56 table 19 values for loam; soil class from the Macedonian soil map (MASIS), not measured"}


def theta(soil_pct: float) -> float:
    return THETA_RES + max(0.0, min(100.0, soil_pct)) / 100 * (THETA_SAT - THETA_RES)


def from_test(rise_s: float | None, drain_pct_h: float | None, settle_pct: float | None,
              settled: bool) -> dict:
    """Soil properties from a soil test: how fast water soaked in, how fast it drained, where it settled."""
    # drainage speed picks the texture class
    if drain_pct_h is None:
        texture = "loam"
    elif drain_pct_h > 20:
        texture = "sandy-loam"
    elif drain_pct_h > 8:
        texture = "loam"
    elif drain_pct_h > 3:
        texture = "clay-loam"
    else:
        texture = "clay"
    c = dict(CLASSES[texture])
    # infiltration (soak-in speed) sets the runoff curve number: compacted or crusted soil sheds rain
    if rise_s is not None:
        if rise_s <= 60:
            infil, cn = "fast", c["cn"] - 4
        elif rise_s <= 300:
            infil, cn = "moderate", c["cn"]
        else:
            infil, cn = "slow", min(94, c["cn"] + 6)
    else:
        infil, cn = "unknown", c["cn"]
    fc = c["fc"]
    if settled and settle_pct is not None:
        # where the moisture settled after the fast drainage approaches field capacity. A pot test lasts minutes,
        # real drainage takes a day or two, so the reading may only move the texture's value by up to ±20 %
        fc = round(max(c["fc"] * 0.8, min(c["fc"] * 1.2, theta(settle_pct))), 3)
    return {**c, "texture": texture, "fc": fc, "cn": cn, "infiltration": infil, "measured": True,
            "label": f"Measured by the ESP32 soil test: behaves like {c['name'].lower()}, {infil} infiltration",
            "source": "ESP32 capacitive probe soil test; wilting point from FAO-56 table 19 for that texture"}


# ---------- soil for a location (no sensor): ISRIC SoilGrids 250 m ----------

SOILGRIDS = "https://rest.isric.org/soilgrids/v2.0/properties/query"
SOILGRIDS_NAME = "ISRIC SoilGrids 2.0, 250 m (global soil map, FAO-supported), 0-60 cm"
DEPTHS = [("0-5cm", 5), ("5-15cm", 10), ("15-30cm", 15), ("30-60cm", 30)]


def texture_class(sand: float, clay: float) -> str:
    """USDA texture class (sand and clay in %)."""
    silt = 100 - sand - clay
    if clay >= 40:
        return "clay" if sand <= 45 and silt < 40 else "silty clay" if silt >= 40 else "sandy clay"
    if clay >= 27:
        return "clay loam" if 20 < sand <= 45 else "silty clay loam" if sand <= 20 else "sandy clay loam"
    if clay >= 20 and sand > 45:
        return "sandy clay loam"
    if silt >= 50:
        return "silt loam" if clay >= 12 or silt < 80 else "silt"
    if sand >= 85:
        return "sand"
    if sand >= 70:
        return "loamy sand"
    if sand >= 52 or (clay < 7 and silt < 50):
        return "sandy loam"
    return "loam"


def saxton_rawls(sand: float, clay: float, om: float) -> tuple[float, float]:
    """Field capacity (33 kPa) and wilting point (1500 kPa), m3/m3, Saxton & Rawls (2006) pedotransfer."""
    S, C, OM = sand / 100, clay / 100, om
    t1500 = -0.024 * S + 0.487 * C + 0.006 * OM + 0.005 * S * OM - 0.013 * C * OM + 0.068 * S * C + 0.031
    wp = t1500 + (0.14 * t1500 - 0.02)
    t33 = -0.251 * S + 0.195 * C + 0.011 * OM + 0.006 * S * OM - 0.027 * C * OM + 0.452 * S * C + 0.299
    fc = t33 + (1.283 * t33 ** 2 - 0.374 * t33 - 0.015)
    return round(fc, 3), round(wp, 3)


def from_soilgrids(data: dict) -> dict | None:
    layers = {l["name"]: l for l in data.get("properties", {}).get("layers", [])}
    if not {"sand", "clay", "soc"} <= set(layers):
        return None

    def avg(name):
        l = layers[name]
        f = l["unit_measure"]["d_factor"]
        vals = {d["label"]: d["values"]["mean"] for d in l["depths"]}
        pairs = [(vals.get(lbl), w) for lbl, w in DEPTHS if vals.get(lbl) is not None]
        if not pairs:
            return None
        return sum(v / f * w for v, w in pairs) / sum(w for _, w in pairs)
    sand, clay = avg("sand"), avg("clay")  # %
    soc = avg("soc")  # g/kg
    if sand is None or clay is None:
        return None
    om = (soc or 10) / 10 * 1.724  # organic matter %
    ph = avg("phh2o") if "phh2o" in layers else None
    fc, wp = saxton_rawls(sand, clay, om)
    tex = texture_class(sand, clay)
    hsg = "D" if clay >= 40 else "C" if clay >= 27 else "A" if sand >= 70 else "B"
    cn = {"A": 72, "B": 80, "C": 85, "D": 89}[hsg]
    drain = {"A": 60, "B": 25, "C": 10, "D": 4}[hsg]
    return {"name": tex.capitalize(), "texture": tex, "fc": fc, "wp": wp, "cn": cn, "drain_mm_day": drain, "hsg": hsg,
            "sand_pct": round(sand), "clay_pct": round(clay), "silt_pct": round(100 - sand - clay),
            "organic_matter_pct": round(om, 1), "ph": round(ph, 1) if ph else None,
            "measured": False, "from_map": True,
            "label": f"{tex.capitalize()} ({round(sand)}% sand, {round(clay)}% clay, {round(om, 1)}% organic matter"
                     + (f", pH {ph:.1f}" if ph else "") + ") from the global soil map at this field",
            "source": SOILGRIDS_NAME + "; water holding by Saxton & Rawls (2006)"}


def for_location(lat: float, lon: float) -> dict:
    """Soil for the simulation at a field, from SoilGrids (cached). SoilGrids leaves some pixels empty (built-up,
    water); then the nearest pixels around the field are tried, and the regional default is the last resort."""
    for dlat, dlon in ((0, 0), (0.003, 0), (-0.003, 0), (0, 0.004), (0, -0.004), (0.006, 0.006), (-0.006, -0.006)):
        out = _for_point(round(lat + dlat, 4), round(lon + dlon, 4))
        if out:
            if dlat or dlon:
                out["label"] += " (nearest mapped pixel)"
            return out
    return DEFAULT


def _for_point(lat: float, lon: float) -> dict | None:
    import httpx
    from sqlmodel import Session
    from models import Cache, engine
    key = f"soilgrids:{lat:.4f},{lon:.4f}"
    with Session(engine) as s:
        c = s.get(Cache, key)
        data = c.data if c else None
        if data is None:
            try:
                q = [("lat", lat), ("lon", lon), ("value", "mean")] + \
                    [("property", p) for p in ("sand", "clay", "silt", "soc", "phh2o")] + \
                    [("depth", d) for d, _ in DEPTHS]
                r = httpx.get(SOILGRIDS, params=q, timeout=60)
                r.raise_for_status()
                data = r.json()
                s.add(Cache(key=key, data=data))
                s.commit()
            except Exception:
                data = None
    return from_soilgrids(data) if data else None
