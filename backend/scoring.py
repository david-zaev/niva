"""Rotation scoring (DESIGN.md "Scoring rules"). Pure functions: no database, easy to test.

score_rotation(rotation, crops, indicators, yields, prices, priorities, what_if) ->
  six scores 0-100, a weighted total, a 12-month strip per year, and the text for the five card headings.
Every rule that fires adds one line under "why" or "risks", so the score explains itself.
"""
from dataclasses import dataclass, field

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
SCORES = ["water", "soil", "erosion", "pest", "climate", "income"]
SCORE_NAMES = {"water": "Water", "soil": "Soil health", "erosion": "Erosion", "pest": "Pest break",
               "climate": "Climate fit", "income": "Income"}
SOIL_STORE_MM = 100       # water a crop can draw from the soil profile (rough, no soil test yet)
HEAT_PENALTY = {"LOW": 3.0, "MED": 1.5, "HIGH": 0.5}   # points per heat day while the crop grows in Jun-Aug


@dataclass
class Planting:
    crop: dict
    year: int
    start: int   # absolute month index from the start of year 1 (0 = Jan year 1), may be negative
    end: int     # inclusive


@dataclass
class Notes:
    good: list = field(default_factory=list)
    risks: list = field(default_factory=list)
    gaps: list = field(default_factory=list)
    evidence: list = field(default_factory=list)


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def build_plantings(rotation: dict, crops: dict) -> tuple[list[Planting], int]:
    """Turn {crop, year} entries into month ranges on a cyclic N*12 calendar."""
    out = []
    for p in rotation["plantings"]:
        c = crops[p["crop"]]
        y0 = (p["year"] - 1) * 12
        sow, harvest = c["sow_months"][0] - 1, c["harvest_months"][-1] - 1
        if c["cycle"] == "PERENNIAL":
            start, end = y0 + sow, y0 + 12 * (c.get("stand_years", 1) - 1) + harvest
        else:
            start, end = y0 + sow, y0 + harvest
            if sow > harvest:  # sown in the autumn before
                start -= 12
        out.append(Planting(c, p["year"], start, end))
    n_years = max(max(p.year for p in out), max((p.end // 12) + 1 for p in out))
    out.sort(key=lambda p: p.start)
    return out, n_years


def months_covered(plantings, n):
    cover = [None] * (n * 12)
    for p in plantings:
        for m in range(p.start, p.end + 1):
            cover[m % (n * 12)] = p.crop["id"]
    return cover


def main_sequence(plantings):
    return [p for p in plantings if not p.crop["cover_crop"]]


def season_months(p: Planting):
    return [m % 12 for m in range(p.start, p.end + 1)]


def score_rotation(rotation, crops, ind, yields, prices, priorities=None, what_if=None, current=None):
    what_if = what_if or {}
    rain_factor = 1 + what_if.get("rain", 0) / 100
    warm = int(round(clamp(what_if.get("temp", 0), 0, 3)))
    plantings, n = build_plantings(rotation, crops)
    seq = main_sequence(plantings)
    all_seq = plantings
    notes = Notes()
    loc = ind["location"]
    period = ind["periods"]["recent"]
    monthly = ind["monthly"]["recent"]
    rain = [m["rain_mm"] * rain_factor for m in monthly]
    et0 = [m["et0_mm"] for m in monthly]
    t_mean = sum((m["t_max"] + m["t_min"]) / 2 for m in monthly) / 12
    et0_factor = (t_mean + warm + 17.8) / (t_mean + 17.8)   # Hargreaves: ET0 grows with mean temperature
    heat_days = ind["what_if_warming"][str(warm)]["heat_days"]
    src = f"NASA POWER {period}"

    # ---------- sequence checks (blocked / tight) ----------
    cyc = n * 12
    for a, b in zip(all_seq, all_seq[1:] + all_seq[:1]):
        b_start = b.start if b.start > a.start else b.start + cyc
        gap = b_start - a.end + (len(b.crop["sow_months"]) - 1)   # the latest sowing month still works
        if gap < 0:
            notes.risks.append(f"Blocked: {b.crop['name']} must be sown before {a.crop['name']} is harvested.")
        elif gap == 0:
            notes.risks.append(f"Tight: {a.crop['name']} harvest and {b.crop['name']} sowing fall in the same month "
                               f"({MONTHS[a.end % 12]}).")

    # ---------- pest break ----------
    pest_pts, transitions = 0, 0
    for a, b in zip(seq, seq[1:] + seq[:1]):
        transitions += 1
        ca, cb = a.crop, b.crop
        if ca["family"] != cb["family"]:
            pest_pts += 20
        else:
            pest_pts -= 30
            notes.risks.append(f"{ca['name']} → {cb['name']}: same plant family ({ca['family']}), pests carry over.")
        shared = set(ca["shared_pathogens"]) & set(cb["shared_pathogens"])
        if shared and ca["family"] != cb["family"]:
            pest_pts -= 25
            notes.risks.append(f"{ca['name']} → {cb['name']}: share {', '.join(s.replace('_', ' ') for s in shared)}.")
        if (ca["cycle"] == "WINTER_ANNUAL") != (cb["cycle"] == "WINTER_ANNUAL"):
            pest_pts += 15
    # return interval: years between two plantings of the same crop
    by_crop = {}
    for p in seq:
        by_crop.setdefault(p.crop["id"], []).append(p.year)
    for cid, years in by_crop.items():
        c = crops[cid]
        stand = c.get("stand_years", 1)
        gaps = [(b - a) for a, b in zip(years, years[1:])] + [years[0] + n - years[-1]]
        if min(gaps) - (stand - 1) < c["min_return_years"]:
            pest_pts -= 30
            notes.risks.append(f"{c['name']} comes back every {min(gaps)} year(s); it needs {c['min_return_years']} "
                               f"to break its diseases.")
    pest = clamp(40 + 1.5 * pest_pts / max(1, transitions))
    if pest >= 70:
        notes.good.append("Different plant families follow each other, which breaks pest and disease cycles.")

    # ---------- soil health ----------
    soil_pts = 0
    n_credit = 0
    for a, b in zip(all_seq, all_seq[1:] + all_seq[:1]):
        ca, cb = a.crop, b.crop
        if ca["nitrogen_role"] == "NITROGEN_FIXER" and cb["nitrogen_role"] in ("HEAVY_FEEDER", "MODERATE_FEEDER"):
            soil_pts += 20 if cb["nitrogen_role"] == "HEAVY_FEEDER" else 12
            notes.good.append(f"{ca['name']} leaves about {ca['n_credit_kg_ha']} kg N/ha for the {cb['name'].lower()} after it.")
        if ca["root_type"] != cb["root_type"]:
            soil_pts += 15
    for p in all_seq:
        n_credit += p.crop["n_credit_kg_ha"]
        if p.crop["cover_crop"]:
            soil_pts += 20
            notes.good.append(f"{p.crop['name']} protects and feeds the soil between cash crops.")
    if len({p.crop["id"] for p in seq}) == 1:
        soil_pts -= 30
    soil = clamp(25 + 2.0 * soil_pts / n)

    # ---------- water ----------
    deficit_total, need_total, rain_total = 0.0, 0.0, 0.0
    worst = None
    for p in seq:
        months = season_months(p)
        if p.crop["cycle"] == "PERENNIAL":
            months = [m % 12 for m in range(p.start, p.end + 1) if 2 <= m % 12 <= 9]  # growing months Mar-Oct
        season_rain = sum(rain[m] for m in months)
        stand = p.crop.get("stand_years", 1)
        need = p.crop["water_mm"] * et0_factor * stand
        supply = season_rain + SOIL_STORE_MM * stand
        deficit = max(0.0, need - supply)
        deficit_total += deficit
        need_total += need
        rain_total += season_rain
        if worst is None or deficit > worst[1]:
            worst = (p.crop, deficit, season_rain, need)
    deficit_year = deficit_total / n
    water = clamp(100 - deficit_year / 3)
    if worst and worst[1] > 50:
        notes.evidence.append(f"{worst[0]['name']} needs about {worst[3]:.0f} mm; rain in its season is "
                              f"{worst[2]:.0f} mm ({src}).")
    if deficit_year < 60:
        notes.good.append("Crops mostly live on rain and stored soil water.")
    else:
        notes.risks.append(f"About {deficit_year:.0f} mm of irrigation a year would be needed for full yields.")

    # ---------- erosion (rain on bare soil) ----------
    cover = months_covered(all_seq, n)
    heavy = [m["heavy_rain_days"] for m in monthly]
    risky_months = set(sorted(range(12), key=lambda i: (-heavy[i], -rain[i]))[:4])   # the 4 stormiest months
    bare_rain = sum(rain[i % 12] for i, c in enumerate(cover) if c is None)
    total_rain = sum(rain) * n
    bare_months_year = sum(1 for c in cover if c is None) / n
    # Slope (NASA NASADEM 30 m): the RUSLE steepness factor against a gentle 2 % slope. Square-rooted so one
    # input cannot swamp the bare-soil timing, which the farmer can change; the slope cannot be changed.
    terrain = ind.get("terrain") or {}
    slope_factor = terrain.get("erosion_factor") or 1.0
    erosion = clamp(100 - 160 * bare_rain / total_rain * slope_factor ** 0.5)
    if terrain:
        notes.evidence.append(f"Field slope about {terrain['slope_deg']}° ({terrain['slope_pct']} %), {terrain['class']}: "
                              f"bare soil washes off {slope_factor:.1f}x as fast as on a 2 % slope "
                              f"(NASA NASADEM 30 m, RUSLE slope factor).")
        if terrain["slope_deg"] >= 5:
            notes.risks.append(f"Slope of {terrain['slope_deg']}°: plough across the slope and keep winter cover.")
    strip = []
    for y in range(n):
        row = []
        for m in range(12):
            c = cover[y * 12 + m]
            row.append({"month": m + 1, "crop": c,
                        "state": "crop" if c else ("risk" if m in risky_months else "bare")})
        strip.append(row)
    risk_bare = sum(1 for row in strip for cell in row if cell["state"] == "risk") / n
    if risk_bare >= 1.5:
        notes.risks.append(f"Soil is bare in {risk_bare:.1f} of the stormiest months a year "
                           f"({', '.join(MONTHS[i] for i in sorted(risky_months))}).")
    notes.evidence.append(f"Bare soil {bare_months_year:.1f} months a year; stormiest months "
                          f"{', '.join(MONTHS[i] for i in sorted(risky_months))} ({src}, days over 20 mm).")

    # ---------- climate fit ----------
    climate_scores = []
    lsf = ind["recent"]["last_spring_frost"] or "04-15"
    last_frost_m = int(lsf[:2]) - 1
    last_frost_txt = f"{int(lsf[3:])} {MONTHS[last_frost_m]}"
    for p in seq:
        c = p.crop
        s = 100.0
        months = set(season_months(p))
        if months & {5, 6, 7}:
            pen = heat_days * HEAT_PENALTY[c["heat_tolerance"]]
            s -= pen
            if c["heat_tolerance"] == "LOW" and heat_days >= 8:
                notes.risks.append(f"{c['name']} suffers above 35 °C: {heat_days:.0f} such days a year in summer "
                                   f"({src}{', +' + str(warm) + ' °C' if warm else ''}).")
        if c["frost_tolerance"] == "SENSITIVE" and c["sow_months"][0] - 1 <= last_frost_m:
            s -= 15
            notes.risks.append(f"Sowing {c['name'].lower()} in {MONTHS[c['sow_months'][0] - 1]} risks the last spring "
                               f"frost (median {last_frost_txt}, {src}).")
        if c["base_temp_c"] >= 10:
            available = ind["recent"]["gdd_base10"] + warm * 150
            if c["gdd_to_maturity"] > 0.85 * available:
                s -= 40
                notes.risks.append(f"{c['name']} needs {c['gdd_to_maturity']} growing degree days; the field gets "
                                   f"about {available:.0f} ({src}).")
        climate_scores.append(clamp(s))
    climate = sum(climate_scores) / len(climate_scores)
    notes.evidence.append(f"{heat_days:.1f} days a year above 35 °C in Jun–Aug ({src}"
                          f"{', shifted +' + str(warm) + ' °C' if warm else ''}).")

    # ---------- income (gross revenue: official yield × ZPIS price) ----------
    price_by = {p["crop"]: p for p in prices.get("prices", [])}
    yld = yields["locations"].get(loc["id"], {}).get("crops", {})
    revenue, known_years, missing = 0.0, 0, set()
    for p in seq:
        cid = p.crop["id"]
        pr, y = price_by.get(cid), yld.get(cid)
        stand = p.crop.get("stand_years", 1)
        if pr and y:
            local = pr.get("local", {}).get(loc["id"])
            mkd = (local or pr["price"]) * y["yield_kg_ha"]
            revenue += mkd * stand
            known_years += stand
        else:
            missing.add(p.crop["name"])
    income = None
    revenue_year = None
    if known_years >= 0.6 * sum(p.crop.get("stand_years", 1) for p in seq):
        revenue_year = revenue / known_years
    if missing:
        notes.gaps.append(f"No verified price or local yield for {', '.join(sorted(missing))}: income left out for "
                          f"{'it' if len(missing) == 1 else 'them'}.")

    scores = {"water": round(water), "soil": round(soil), "erosion": round(erosion), "pest": round(pest),
              "climate": round(climate), "income": None}
    return {
        "plantings": plantings, "years": n, "scores": scores, "revenue_year": revenue_year,
        "strip": strip, "notes": notes,
        "metrics": {"irrigation_mm_year": round(deficit_year), "bare_months_year": round(bare_months_year, 1),
                    "n_added_kg_ha_year": round(n_credit / n), "heat_days": heat_days},
    }


def finish(results: list[dict], priorities: dict | None, current_id: str, ind: dict, yields: dict, prices: dict):
    """Income relative to the best rotation, weighted totals, confidence and the five headings."""
    best_rev = max((r["revenue_year"] or 0) for r in results) or None
    for r in results:
        if r["revenue_year"] is not None and best_rev:
            # Gross revenue ignores costs, and vegetables cost far more to grow than grain:
            # compress the scale so a 20x higher gross does not read as 20x better.
            r["scores"]["income"] = round(100 * (r["revenue_year"] / best_rev) ** 0.4)
    w = {k: 1.0 for k in SCORES}
    for k, v in (priorities or {}).items():
        if k in w and isinstance(v, (int, float)):
            w[k] = max(0.0, float(v))
    for r in results:
        used = {k: v for k, v in r["scores"].items() if v is not None}
        total_w = sum(w[k] for k in used) or 1
        r["total"] = round(sum(v * w[k] for k, v in used.items()) / total_w)

    current = next(r for r in results if r["id"] == current_id)
    loc = ind["location"]
    for r in results:
        notes: Notes = r["notes"]
        deltas = {k: (r["scores"][k] or 0) - (current["scores"][k] or 0) for k in SCORES
                  if r["scores"][k] is not None and current["scores"][k] is not None}
        top = sorted(deltas.items(), key=lambda kv: -kv[1])[:2]
        if r["id"] == current_id:
            why = "This is what you grow now: the other rotations are compared with it."
        elif top and top[0][1] > 0:
            parts = [f"{SCORE_NAMES[k].lower()} (+{d})" for k, d in top if d > 0]
            why = f"Better than your current rotation for {' and '.join(parts)}."
        else:
            why = "Close to your current rotation overall; see the scores for where it differs."

        evidence = list(notes.evidence)
        y = yields["locations"].get(loc["id"], {})
        price_by = {p["crop"]: p for p in prices.get("prices", [])}
        seen = set()
        for p in r["plantings"]:
            cid = p.crop["id"]
            if cid in seen or p.crop["cover_crop"]:
                continue
            seen.add(cid)
            yy, pr = y.get("crops", {}).get(cid), price_by.get(cid)
            if yy and pr:
                local = pr.get("local", {}).get(loc["id"])
                evidence.append(f"{p.crop['name']}: {yy['yield_kg_ha']:,} kg/ha in {y['municipality']} "
                                f"(MakStat {yy['years']}) × {local or pr['price']} MKD/kg "
                                f"({'ZPIS ' + pr['market']}, {prices['retrieved']}).")
        if r["revenue_year"] is not None:
            evidence.append(f"Gross revenue about {r['revenue_year'] / 1000:,.0f} thousand MKD/ha a year, before costs.")

        cur_m, m = current["metrics"], r["metrics"]
        benefits = []
        if r["id"] != current_id:
            saved = cur_m["irrigation_mm_year"] - m["irrigation_mm_year"]
            if saved > 10:
                benefits.append(f"Needs about {saved} mm less irrigation water a year.")
            bare = cur_m["bare_months_year"] - m["bare_months_year"]
            if bare >= 0.5:
                benefits.append(f"{bare:.1f} fewer months of bare soil a year.")
            if m["n_added_kg_ha_year"] > cur_m["n_added_kg_ha_year"]:
                benefits.append(f"Adds about {m['n_added_kg_ha_year']} kg N/ha a year from legumes: less fertiliser to buy.")
        benefits += notes.good[:3]
        if not benefits:
            benefits.append("No clear gain over your current rotation.")

        gaps = list(notes.gaps) + [
            "No lab soil test yet: soil water and nutrients are estimates.",
            "NASA POWER rain is an average over a cell about 50 km wide, not this exact field.",
            *([] if ind.get("terrain") else ["Field slope (NASA NASADEM) could not be read at this point."]),
            "Crop numbers are approximate.",
        ]
        risks = list(dict.fromkeys(notes.risks))
        priced = {p["crop"] for p in prices.get("prices", [])}
        new_crops = {p.crop["name"] for p in r["plantings"] if not p.crop["cover_crop"] and p.crop["id"] not in priced} -             {p.crop["name"] for p in current["plantings"]}
        for name in sorted(new_crops):
            risks.append(f"Ask local buyers about {name.lower()} before sowing: market not checked here.")
        risks = risks[:5] + ["Check with a local agronomist before changing your rotation."]

        # Medium: 35 years of NASA data but no SMAP/sensor comparison yet. Low: income or region unknown.
        confidence = "medium"
        if r["scores"]["income"] is None or ind.get("_distance_km", 0) > 60:
            confidence = "low"
        r["card"] = {"why": why, "evidence": evidence, "benefits": benefits, "gaps": gaps, "risks": risks}
        r["confidence"] = confidence


def to_json(r: dict) -> dict:
    return {
        "id": r["id"], "name": r["name"], "kind": r["kind"], "years": r["years"],
        "crops": [{"crop": p.crop["id"], "name": p.crop["name"], "name_mk": p.crop["name_mk"], "year": p.year,
                   "cover_crop": p.crop["cover_crop"]} for p in r["plantings"]],
        "scores": r["scores"], "total": r["total"], "confidence": r["confidence"],
        "metrics": r["metrics"], "revenue_mkd_ha_year": round(r["revenue_year"]) if r["revenue_year"] else None,
        "strip": r["strip"], **r["card"],
    }


def rank(library: list[dict], crops: dict, ind: dict, yields: dict, prices: dict, current: dict,
         priorities: dict | None = None, what_if: dict | None = None, top_n: int = 3) -> dict:
    """Score the current rotation and every rotation in the library; return current + top N."""
    results = []
    for rot in [current] + [r for r in library if r["id"] != current["id"]]:
        res = score_rotation(rot, crops, ind, yields, prices, priorities, what_if)
        res.update(id=rot["id"], name=rot["name"], kind="current" if rot is current else rot.get("kind", "suggested"))
        results.append(res)
    finish(results, priorities, current["id"], ind, yields, prices)
    cur = results[0]
    region = ind["location"]["id"]
    others = sorted(results[1:], key=lambda r: (-r["total"],))
    # prefer rotations meant for this region, but never hide a much better one
    preferred = [r for r in others if region in next((l.get("regions", []) for l in library if l["id"] == r["id"]), [])]
    picked = (preferred + [r for r in others if r not in preferred])[:top_n]
    picked.sort(key=lambda r: -r["total"])
    return {"current": to_json(cur), "suggestions": [to_json(r) for r in picked]}
