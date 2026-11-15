"""Compare rotations for one field: run each through the 25 NASA seasons, score it, and write its card
(why it is suggested, evidence, benefits, information gaps, risks), as the challenge asks."""
from collections import defaultdict
import hashlib
import json

import numpy as np

import simulate
import smap

WEIGHTS = {"water": 1.0, "soil": 1.0, "pests": 1.5, "resilience": 1.0, "income": 1.0}
REPEAT_PENALTY = 50
KEEPS_CROP_BONUS = 5  # score points for keeping a crop the farmer already grows: known methods, buyers, machinery  # pest score points lost for each crop whose plant family comes back too soon
MKD_PER_EUR = 61.5
REPEAT_LOSS = 0.15  # assumed yield loss when a plant family returns too soon (rotation studies: about 10-30 %)


def _family_breaks(seasons: list[list[str]]) -> list[dict]:
    """Main crops whose plant family comes back sooner than the crop's minimum return interval (pest carry-over)."""
    cs = simulate.crops()
    main = [[c for c in s if not cs[c].get("cover_crop")] for s in seasons]
    L = len(main)
    out = []
    for i, crops_i in enumerate(main):
        for cid in crops_i:
            c = cs[cid]
            if c["kind"] == "perennial":
                continue
            for gap in range(1, c["min_return"]):
                prev = main[(i - gap) % L]
                # maize pests (rootworm) need maize itself; other crops share soil diseases across the family
                same = [p for p in prev if (p == cid if c.get("repeat_by") == "crop" else cs[p]["family"] == c["family"])]
                if same:
                    out.append({"season": i + 1, "crop": c["name"], "after": cs[same[0]]["name"], "gap": gap,
                                "family": c["family"], "min_return": c["min_return"]})
                    break
    return out


def _run_all(seasons, weather, soil, irrigation, slope_factor, t_offset):
    runs = [simulate.run(seasons, weather, soil, irrigation, phase=k, slope_factor=slope_factor, t_offset=t_offset)
            for k in range(len(seasons))]
    return runs


def evaluate(rot: dict, weather, soil: dict, irrigation: str | None, slope_factor: float, t_offset: float) -> dict:
    cs = simulate.crops()
    seasons = rot["seasons"]
    runs = _run_all(seasons, weather, soil, irrigation, slope_factor, t_offset)
    breaks = _family_breaks(seasons)
    repeat = {(b["season"] - 1, b["crop"]) for b in breaks}
    yearly = np.concatenate([r.yearly[["irr", "bare_days", "erosion", "live_cover", "runoff", "waterlog_days"]]
                             .to_numpy() for r in runs])
    irr, bare, eros, cover, runoff, wlog = yearly.T
    last_season = max(r.yearly.index.max() for r in runs)
    per_crop = defaultdict(list)
    for r in runs:
        for p in r.plantings:
            if p.etc <= 0 or p.end.year > last_season + 1 or p.length <= 0:
                continue
            ratio = max(0.0, 1 - p.crop["ky"] * (1 - p.eta / p.etc)) if p.crop["ky"] else 1.0
            if p.frost_hits and p.crop["frost_c"] is not None and p.crop["kind"] != "winter":
                ratio *= 0.7  # a late frost after transplanting usually means replanting or a big loss
            if (p.season, p.crop["name"]) in repeat:
                ratio *= 1 - REPEAT_LOSS  # soil-borne pests and diseases build up when a family comes back too soon
            per_crop[p.crop["id"]].append({"ratio": ratio, "irr": p.irr, "frost": p.frost_hits > 0,
                                           "heat": p.heat_days, "stress": p.stress_days, "year": p.end.year})
    crops_out = []
    for cid, l in per_crop.items():
        c = cs[cid]
        ratios = sorted(x["ratio"] for x in l)
        worst = min(l, key=lambda x: x["ratio"])
        sens = c["frost_c"] is not None
        crops_out.append({
            "id": cid, "name": c["name"], "family": c["family"], "seasons_simulated": len(l),
            "irrigation_mm": round(float(np.mean([x["irr"] for x in l]))),
            "yield_pct_typical": round(100 * float(np.median(ratios))),
            "yield_pct_dry_years": round(100 * float(np.mean(ratios[:max(1, len(ratios) // 10)]))),
            "worst_year": worst["year"], "worst_year_yield_pct": round(100 * worst["ratio"]),
            "frost_seasons_pct": round(100 * float(np.mean([x["frost"] for x in l]))) if sens else None,
            "heat_days": round(float(np.mean([x["heat"] for x in l])), 1),
            "irrigated": bool(c["irrigated"] and irrigation),
            "cover_crop": bool(c.get("cover_crop")),
        })
    L = len(seasons)
    n_credit = sum(cs[c]["n_credit"] for s in seasons for c in s) / L
    residue = sum(cs[c]["residue_t"] for s in seasons for c in s) / L
    breaks = _family_breaks(seasons)
    # gross income per hectare per year: sum over a whole cycle of seasons divided by its length
    gross = float(sum(np.mean([x["ratio"] for x in per_crop[c]]) * cs[c]["yield_kg_ha"] * cs[c]["price_mkd_kg"]
                      for s in seasons for c in s if c in per_crop) / L)
    gross_dry = float(sum(np.mean(sorted(x["ratio"] for x in per_crop[c])[:max(1, len(per_crop[c]) // 10)])
                          * cs[c]["yield_kg_ha"] * cs[c]["price_mkd_kg"] for s in seasons for c in s if c in per_crop) / L)
    main_crops = [cs[c] for s in seasons for c in s if not cs[c].get("cover_crop")]
    frost_l = [x["frost_seasons_pct"] for x in crops_out if x["frost_seasons_pct"] is not None]
    return {
        "id": rot["id"], "name": rot["name"], "kind": rot.get("kind", "custom"), "idea": rot.get("idea"),
        "seasons": seasons, "length_years": L,
        "season_names": [" + ".join(cs[c]["name"] for c in s) for s in seasons],
        "metrics": {
            "irrigation_mm": round(float(np.mean(irr))),
            "irrigation_mm_dry_year": round(float(np.percentile(irr, 90))),
            "irrigation_m3_ha": round(float(np.mean(irr)) * 10),
            "bare_days": round(float(np.mean(bare))),
            "living_cover_pct": round(100 * float(np.mean(cover))),
            "erosion_index": round(float(np.mean(eros))),
            "runoff_mm": round(float(np.mean(runoff))),
            "waterlog_days": round(float(np.mean(wlog)), 1),
            "n_credit_kg_ha": round(n_credit),
            "residue_t_ha": round(residue, 1),
            "family_breaks": breaks,
            "families": sorted({c["family"] for c in main_crops}),
            "frost_risk_pct": max(frost_l) if frost_l else 0,
            "heat_days": round(float(sum(x["heat_days"] for x in crops_out if not x["cover_crop"]) / L), 1),
            "dry_year_yield_pct": round(float(np.mean([x["yield_pct_dry_years"] for x in crops_out
                                                     if not x["cover_crop"]]))) if crops_out else 100,
            "gross_mkd_ha": round(gross, -3), "gross_eur_ha": round(gross / MKD_PER_EUR, -1),
            "gross_dry_mkd_ha": round(gross_dry, -3),
            "seasons_simulated": len(irr),
        },
        "crops": sorted(crops_out, key=lambda x: x["cover_crop"]),
        "monthly_irrigation_mm": {m: round(float(np.mean([r.monthly_irr.get(m, 0) for r in runs])), 1)
                                  for m in range(1, 13)},
        "_runs": runs,
    }


def _norm(vals, higher_better=True):
    a = np.asarray(vals, float)
    lo, hi = a.min(), a.max()
    if hi - lo < 1e-9:
        return np.full(len(a), 75.0)
    s = (a - lo) / (hi - lo)
    return 100 * (s if higher_better else 1 - s)


def score(evals: list[dict], priorities: dict | None) -> None:
    m = [e["metrics"] for e in evals]
    water = _norm([x["irrigation_mm"] + 0.5 * x["irrigation_mm_dry_year"] for x in m], False)
    soil_parts = (0.35 * _norm([x["living_cover_pct"] for x in m])
                  + 0.25 * _norm([x["erosion_index"] for x in m], False)
                  + 0.15 * _norm([x["n_credit_kg_ha"] for x in m])
                  + 0.15 * _norm([x["residue_t_ha"] for x in m])
                  + 0.10 * _norm([-len(x["family_breaks"]) for x in m]))
    resil = (0.5 * _norm([x["dry_year_yield_pct"] for x in m])
             + 0.2 * _norm([x["frost_risk_pct"] for x in m], False)
             + 0.1 * _norm([x["heat_days"] for x in m], False)
             + 0.2 * _norm([x["gross_dry_mkd_ha"] for x in m]))
    income = _norm([x["gross_mkd_ha"] for x in m])
    w = {**WEIGHTS, **{k: float(v) for k, v in (priorities or {}).items() if k in WEIGHTS}}
    tot = sum(w.values()) or 1
    for i, e in enumerate(evals):
        # pest and disease cycle: absolute, so a rotation that keeps repeating a family never scores well
        pests = max(0, 100 - REPEAT_PENALTY * len(m[i]["family_breaks"]))
        e["scores"] = {"water": round(water[i]), "soil": round(soil_parts[i]), "pests": pests,
                       "resilience": round(resil[i]),
                       "income": round(income[i])}
        e["score"] = round(sum(e["scores"][k] * w[k] for k in w) / tot)


def _pct(a, b):
    return round(100 * (a - b) / b) if b else 0


def card(e: dict, cur: dict | None, ctx: dict) -> dict:
    """Why, evidence, benefits, gaps and risks, in plain words. With `cur` the reasons compare against the farmer's
    current rotation; without it they describe the rotation on this field on its own."""
    m = e["metrics"]
    c = cur["metrics"] if cur else m
    is_current = cur is not None and e["id"] == cur["id"]
    why, benefits, risks, gaps, evidence = [], [], [], [], []
    climate = ctx["climate"]
    nyears = climate["n_years"]
    src_power = "NASA POWER daily, " + climate["years"]

    if cur is None:
        if not m["family_breaks"]:
            why.append("No plant family comes back too soon: pests and soil diseases lose their host.")
        if m["n_credit_kg_ha"]:
            why.append(f"Legumes add about {m['n_credit_kg_ha']} kg of nitrogen per hectare a year.")
        if m["living_cover_pct"] >= 45:
            why.append(f"Living roots cover the soil {m['living_cover_pct']}% of the year.")
        if m["dry_year_yield_pct"] >= 75:
            why.append(f"Holds up in dry years: {m['dry_year_yield_pct']}% of normal yield in the driest years.")
        why.append("Needs no irrigation." if not m["irrigation_mm"]
                   else f"Needs about {m['irrigation_mm']} mm of irrigation water a year.")
    elif not is_current:
        if m["irrigation_mm"] < c["irrigation_mm"] * 0.9:
            why.append(f"Needs {abs(_pct(m['irrigation_mm'], c['irrigation_mm']))}% less irrigation water than your "
                       f"current rotation ({m['irrigation_mm']} vs {c['irrigation_mm']} mm a year).")
        if m["living_cover_pct"] > c["living_cover_pct"] + 8:
            why.append(f"Living roots cover the soil {m['living_cover_pct']}% of the year instead of "
                       f"{c['living_cover_pct']}%.")
        if len(m["family_breaks"]) < len(c["family_breaks"]):
            why.append("Breaks the pest and disease cycle: the same plant family does not come back too soon.")
        if m["n_credit_kg_ha"] > c["n_credit_kg_ha"]:
            why.append(f"Legumes add about {m['n_credit_kg_ha']} kg of nitrogen per hectare a year.")
        if m["erosion_index"] < c["erosion_index"] * 0.85:
            why.append(f"{abs(_pct(m['erosion_index'], c['erosion_index']))}% less soil exposed to heavy rain.")
        if m["dry_year_yield_pct"] > c["dry_year_yield_pct"] + 3:
            why.append(f"Holds up better in dry years ({m['dry_year_yield_pct']}% of normal yield vs "
                       f"{c['dry_year_yield_pct']}%).")
        if m["gross_mkd_ha"] > c["gross_mkd_ha"] * 1.05:
            why.append(f"Higher gross income per hectare ({_pct(m['gross_mkd_ha'], c['gross_mkd_ha'])}%).")
        if not why:
            why.append(e.get("idea") or "A balanced alternative to compare.")
    else:
        why.append("This is what the field grows now: the baseline every other option is compared with.")

    # evidence, each with its data source
    evidence.append({"text": f"Replayed over all {nyears} seasons of real weather at this field, each crop in every season "
                             f"({climate['years']}): typical year {m['irrigation_mm']} mm irrigation, driest 1 in 10 "
                             f"years {m['irrigation_mm_dry_year']} mm.", "source": src_power + " + FAO-56 water balance"})
    dry = climate["driest_summers"][0] if climate["driest_summers"] else None
    if dry:
        evidence.append({"text": f"In the driest summer ({dry['year']}, crop demand exceeded rain by "
                                 f"{dry['summer_deficit']:.0f} mm) the main crops reached {m['dry_year_yield_pct']}% of "
                                 f"normal yield in the worst years.", "source": src_power})
    if m["frost_risk_pct"]:
        evidence.append({"text": f"A frost-sensitive crop met a damaging frost in {m['frost_risk_pct']}% of seasons "
                                 f"(last spring frost usually {climate['frost']['last_spring_median']}, "
                                 f"1 year in 10 after {climate['frost']['last_spring_late_1_in_10']}).",
                         "source": src_power + (" with the field's measured night offset" if ctx["t_offset"] else "")})
    ter = ctx.get("terrain")
    if ter:
        evidence.append({"text": f"Field slope {ter['slope_deg']}° ({ter['class']}): heavy rain on bare soil "
                                 f"weighs {ter['erosion_factor']}x a gentle 2% slope.", "source": ter["source"]["dataset"]})
    nd = ctx.get("ndvi")
    if nd and nd.get("typically_bare_months"):
        months = ", ".join(_MONTHS[k - 1] for k in nd["typically_bare_months"])
        covers = any(simulate.crops()[x].get("cover_crop") for s in e["seasons"] for x in s)
        evidence.append({"text": f"Satellite greenness shows this field bare in {months} in most years"
                                 + ("; the winter cover crop in this rotation fills that gap." if covers else "."),
                         "source": nd["source"]["dataset"]})
    sm = ctx.get("smap_check")
    if sm and sm.get("r") is not None:
        evidence.append({"text": f"The simulated soil water follows NASA SMAP satellite soil moisture at this "
                                 f"field (correlation {sm['r']:.2f} over {sm['days']} days, {sm['period']}).",
                         "source": smap.DATASET})
    evidence.append({"text": ctx["soil"]["label"] + ".", "source": ctx["soil"]["source"]})

    # benefits
    if m["n_credit_kg_ha"]:
        benefits.append(f"About {m['n_credit_kg_ha']} kg N/ha a year from legumes: less fertiliser.")
    if m["residue_t_ha"] >= 2.5:
        benefits.append(f"{m['residue_t_ha']} t/ha of crop residue a year feeds soil organic matter.")
    if m["living_cover_pct"] >= 55:
        benefits.append("Soil covered most of the year: less erosion, better infiltration, more soil life.")
    if not m["family_breaks"]:
        benefits.append("No plant family repeats too soon: pests and soil diseases lose their host.")
    if m["irrigation_mm"] < 300:
        benefits.append("Low irrigation need: safer when wells or canals run short.")
    if cur is None or m["gross_mkd_ha"] >= c["gross_mkd_ha"]:
        benefits.append(f"Gross income about {m['gross_eur_ha']:.0f} € per hectare a year.")
    if not benefits:
        benefits.append("Familiar crops and markets.")

    # risks for local review
    for b in m["family_breaks"][:2]:
        risks.append(f"{b['crop']} follows {b['after']} ({b['family']}) after {b['gap']} season(s): needs "
                     f"{b['min_return']} for soil-borne pests and diseases to die down.")
    if m["gross_mkd_ha"] < c["gross_mkd_ha"] * 0.9 and not is_current:
        risks.append(f"Gross income about {abs(_pct(m['gross_mkd_ha'], c['gross_mkd_ha']))}% lower than now: "
                     f"check whether lower costs and soil gains make up for it.")
    new = {x["name"] for x in e["crops"]} - {x["name"] for x in cur["crops"]} if cur else set()
    if new and not is_current:
        risks.append(f"New crops for this farm ({', '.join(sorted(new))}): check buyers, seed and machinery locally.")
    if m["frost_risk_pct"] >= 15:
        risks.append(f"Late frost hits a sensitive crop in {m['frost_risk_pct']}% of seasons: transplant later or "
                     f"protect seedlings.")
    if m["dry_year_yield_pct"] < MIN_DRY_YEAR_YIELD:
        risks.append(f"In the driest years this rotation keeps only {m['dry_year_yield_pct']}% of a normal harvest: "
                     f"keep a reserve or insure the crop.")
    if m["waterlog_days"] >= 3:
        risks.append(f"About {m['waterlog_days']} waterlogged days a year on this soil: check drainage.")
    if any(x["id"] == "alfalfa" for x in e["crops"]):
        risks.append("Alfalfa ties the field up for two years and needs a hay buyer or livestock.")
    if not risks:
        risks.append("Check timing between harvest and the next sowing with local practice.")

    # information gaps
    if ctx["soil"].get("from_map"):
        gaps.append("Soil comes from a 250 m global soil map, not a sample from this field: a lab soil test would "
                    "confirm texture, organic matter and pH.")
    else:
        gaps.append("Soil map unavailable here: a typical valley loam is assumed.")
    est = sorted({simulate.crops()[x["id"]]["name"] for x in e["crops"]
                  if "estimate" in simulate.crops()[x["id"]]["price_source"]})
    if est:
        gaps.append(f"Prices for {', '.join(est)} are estimates: no official market price was found.")
    gaps.append("Crop water and yield responses are FAO table values, not calibrated for local varieties.")
    if m["family_breaks"]:
        gaps.append(f"The yield loss from repeating a plant family is assumed ({round(100 * REPEAT_LOSS)}%), not measured "
                    f"on this field.")
    if nd and nd.get("pixels", 0) <= 2:
        gaps.append("Satellite greenness is from a 250 m pixel, which also sees neighbouring fields.")

    return {"why": why, "evidence": evidence, "benefits": benefits, "risks": risks, "gaps": gaps}


_MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def smap_check(run: simulate.Result, lat: float, lon: float) -> dict | None:
    """Does the simulated soil water rise and fall with NASA SMAP at this field? (correlation of daily series)"""
    try:
        px = smap.pixel(lat, lon)
    except Exception:
        return None
    if not px:
        return None
    dates, vals = px
    import pandas as pd
    s = pd.Series(vals, index=pd.to_datetime(dates)).dropna()
    sim = 1 - run.daily["dr_frac"]
    j = pd.concat([s.rename("smap"), sim.rename("sim")], axis=1, join="inner").dropna()
    if len(j) < 100:
        return None
    # compare 7-day means: SMAP sees the top 5 cm, the simulation the whole root zone
    j = j.resample("7D").mean().dropna()
    r = float(np.corrcoef(j["smap"], j["sim"])[0, 1])
    return {"r": round(r, 2), "days": int(len(j) * 7), "period": f"{j.index[0].year}-{j.index[-1].year}"}


VEGETABLES = {"pepper", "tomato"}
MIN_DRY_YEAR_YIELD = 50  # % of normal yield: below this a rotation is not offered for the field's water
MIN_DRY_YEAR_YIELD_FALLBACK = 40  # rain-fed fields with too few options: offered down to here, with a warning


def farm_type(seasons: list[list[str]]) -> str:
    """'vegetable', 'tobacco' or 'field crop': options stay with the kind of farm, its machinery and its buyers."""
    crops = {c for s in seasons for c in s}
    return "vegetable" if crops & VEGETABLES else "tobacco" if "tobacco" in crops else "field crop"


def with_cover(rot: dict) -> dict | None:
    """The farmer's own rotation with a winter vetch + oat cover before every spring-sown crop."""
    cs = simulate.crops()
    seasons, added = [], False
    for s in rot["seasons"]:
        main = [c for c in s if not cs[c].get("cover_crop")]
        if main and len(main) == len(s) and all(cs[c].get("kind") != "winter" for c in main):
            seasons.append(["vetch_oat", *s]); added = True
        else:
            seasons.append(list(s))
    if not added:
        return None
    name = rot["name"].replace(" (now)", "")
    name = f"{name}, vetch every winter" if "vetch" in name else f"{name}, with winter vetch"
    return {"id": f"{rot['id']}-cover", "name": name, "kind": "suggested",
            "seasons": seasons, "idea": "What you grow now, plus a vetch and oat cover crop over each winter."}


def keep_and_break(rot: dict) -> dict | None:
    """The farmer's main crop kept, followed by wheat and a legume: the textbook way to break a pest cycle."""
    cs = simulate.crops()
    mains = [c for s in rot["seasons"] for c in s if not cs[c].get("cover_crop")]
    if not mains:
        return None
    top = max(set(mains), key=mains.count)
    if cs[top]["family"] in ("Poaceae", "Fabaceae") or cs[top]["kind"] == "perennial":
        return None  # cereal and legume farms are served by the field-crop rotations
    legume = "bean" if rot.get("_irrigated", True) else "chickpea"
    seasons = [["vetch_oat", top], ["wheat"], [legume]]
    return {"id": f"keep-{top}-wheat-{legume}", "kind": "suggested", "seasons": seasons,
            "name": f"{cs[top]['name']} → wheat → {cs[legume]['name'].lower()}, vetch before {cs[top]['name'].lower()}",
            "idea": f"Keeps your {cs[top]['name'].lower()}, then two years of other families so its pests and soil "
                    f"diseases die down; the legume adds nitrogen."}


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
          "November", "December"]


def plant_next(seasons: list[list[str]], now_seasons: list[list[str]], n: int = 3) -> list[dict]:
    """The next n seasons of a rotation, started where it does not follow the farmer's last crop with the same
    plant family, each with what to sow and when."""
    cs = simulate.crops()

    def mains(s):
        return [c for c in s if not cs[c].get("cover_crop")]

    last = [cs[c] for c in mains(now_seasons[-1])] if now_seasons else []
    L = len(seasons)

    def clashes(k):
        return any(cs[c]["family"] == p["family"] and (p["id"] == c if cs[c].get("repeat_by") == "crop" else True)
                   for c in mains(seasons[k % L]) for p in last)

    start = next((k for k in range(L) if not clashes(k)), 0)
    out = []
    for i in range(n):
        season = seasons[(start + i) % L]
        prev = seasons[(start + i - 1) % L] if i or L > 1 else []
        steps = []
        for c in season:
            m = int(cs[c]["sow"].split("-")[0])
            kept = cs[c]["kind"] == "perennial" and c in prev and i > 0
            steps.append({"crop": c, "name": cs[c]["name"], "sow_month": None if kept else MONTHS[m - 1],
                          "cover": bool(cs[c].get("cover_crop")), "kept": kept})
        out.append({"steps": steps})
    return out


def custom(seasons: list[list[str]], name: str | None = None) -> dict:
    cs = simulate.crops()
    seasons = [[c for c in s if c in cs] for s in seasons if s]
    seasons = [s for s in seasons if s]
    nm = name or " → ".join(" + ".join(cs[c]["name"] for c in s) for s in seasons)
    key = hashlib.sha1(json.dumps(seasons).encode()).hexdigest()[:8]
    return {"id": f"current-{key}", "name": nm, "kind": "current", "seasons": seasons,
            "idea": "The rotation you grow now."}
