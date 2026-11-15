"""Daily soil water balance (FAO-56 single crop coefficient) for a rotation, replayed over the NASA POWER years.

For every day:
    rain -> runoff (SCS curve number; bare soil sheds more) -> infiltration
    crop water use ETc = Kc(stage) x ET0 (Penman-Monteith from POWER), reduced by Ks when the root zone is dry
    bare soil loses water by evaporation from the top layer only
    water above field capacity drains, limited by the soil's drainage speed (else the field is waterlogged)
    irrigated crops are watered back to field capacity when depletion passes the crop's stress threshold (RAW)

The rotation repeats from 2001. It is run once from every starting season, so each crop meets every year's weather.
"""
from dataclasses import dataclass, field as dfield
from datetime import date, timedelta
import json
import math

import numpy as np
import pandas as pd

import nasa

_crops = None


def crops() -> dict[str, dict]:
    global _crops
    if _crops is None:
        d = json.loads((nasa.DATA_DIR / "rotation" / "crops.json").read_text(encoding="utf-8"))
        _crops = {c["id"]: c for c in d["crops"]}
    return _crops


def library() -> list[dict]:
    return json.loads((nasa.DATA_DIR / "rotation" / "rotations.json").read_text(encoding="utf-8"))["rotations"]


IRR_EFF = {"drip": 0.9, "sprinkler": 0.75, "furrow": 0.6}
BARE_Z = 0.5  # m of soil the bucket covers when nothing grows
EROSIVE_MM = 20  # a day with this much rain can wash bare soil


@dataclass
class Planting:
    crop: dict
    start: date
    end: date
    season: int  # index in the rotation (which season it belongs to)
    late_days: int = 0
    # filled by the simulation
    etc: float = 0.0
    eta: float = 0.0
    irr: float = 0.0
    stress_days: int = 0
    frost_hits: int = 0
    heat_days: int = 0

    @property
    def length(self):
        return (self.end - self.start).days


def _sow_date(crop: dict, season_start_year: int) -> date:
    m, d = (int(x) for x in crop["sow"].split("-"))
    return date(season_start_year if m >= 10 else season_start_year + 1, m, d)


def schedule(seasons: list[list[str]], first_year: int, last_year: int, phase: int) -> list[Planting]:
    """Plantings for a repeating rotation, season s starting 1 October of first_year + s."""
    cs = crops()
    out: list[Planting] = []
    busy_until = date(first_year, 10, 1)
    for k, y in enumerate(range(first_year, last_year)):
        idx = (k + phase) % len(seasons)
        for cid in seasons[idx]:
            c = cs[cid]
            sow = _sow_date(c, y)
            late = 0
            if sow < busy_until:
                late = (busy_until - sow).days + 3
                sow = busy_until + timedelta(days=3)
            end = sow + timedelta(days=sum(c["stages"]))
            out.append(Planting(c, sow, end, idx, late))
            busy_until = end
    return out


def stage_at(c: dict, day: int) -> tuple[str, float, float]:
    """(stage, Kc, ground cover fraction) on day `day` after sowing."""
    ini, dev, mid, late = c["stages"]
    kci, kcm, kce = c["kc"]
    cov = c["cover"]
    if day < ini:
        return "ini", kci, 0.1 * cov
    if day < ini + dev:
        f = (day - ini) / dev
        return "dev", kci + f * (kcm - kci), (0.1 + 0.9 * f) * cov
    if day < ini + dev + mid:
        return "mid", kcm, cov
    f = (day - ini - dev - mid) / late
    return "late", kcm + f * (kce - kcm), cov * (1 - 0.4 * f)


@dataclass
class Result:
    plantings: list[Planting]
    daily: pd.DataFrame
    yearly: pd.DataFrame
    monthly_irr: dict = dfield(default_factory=dict)


def run(seasons: list[list[str]], weather: pd.DataFrame, soil: dict, irrigation: str | None,
        phase: int = 0, slope_factor: float = 1.0, t_offset: float = 0.0,
        first_year: int | None = None) -> Result:
    w = weather
    y0 = first_year or max(2001, w.index[0].year)
    y1 = w.index[-1].year if w.index[-1].month >= 10 else w.index[-1].year - 1
    plantings = schedule(seasons, y0, y1, phase)
    start, end = date(y0, 10, 1), date(y1, 9, 30)
    w = w.loc[str(start):str(end)]
    n = len(w)
    days = w.index.date
    rain = w["rain"].to_numpy()
    et0 = w["et0"].to_numpy()
    tmin = w["t_min"].to_numpy() + t_offset
    tmax = w["t_max"].to_numpy()

    fc, wp = soil["fc"], soil["wp"]
    cn0, drain_cap = soil["cn"], soil["drain_mm_day"]
    eff = IRR_EFF.get(irrigation or "", 0)

    # which planting is active each day
    active = np.full(n, -1)
    idx0 = {d: i for i, d in enumerate(days)}
    for k, p in enumerate(plantings):
        a = idx0.get(p.start)
        if a is None:
            continue
        b = min(n, a + p.length)
        active[a:b] = k

    z_prev = BARE_Z
    dr = 0.0  # root-zone depletion below field capacity, mm
    days_since_rain = 5
    out = {k: np.zeros(n) for k in ("dr_frac", "eta", "irr", "runoff", "drain", "cover", "bare", "erosion",
                                   "waterlog", "stress")}
    for i in range(n):
        k = active[i]
        if k >= 0:
            p = plantings[k]
            c = p.crop
            day = (days[i] - p.start).days
            stage, kc, cover = stage_at(c, day)
            z = c["root_m"] * (0.4 + 0.6 * min(1.0, day / max(1, c["stages"][0] + c["stages"][1])))
        else:
            p = c = None
            stage, kc, cover, z = None, 0.0, 0.0, BARE_Z
        taw = 1000 * (fc - wp) * z
        if z != z_prev:  # root zone grew or a crop ended: keep the same relative dryness
            dr = dr / (1000 * (fc - wp) * z_prev) * taw
            z_prev = z
        # runoff: bare soil sheds more, wet soil sheds more (antecedent moisture)
        P = rain[i]
        cn = cn0 - 8 * cover
        wet = 1 - min(1.0, dr / taw) if taw > 0 else 1
        cn = min(97.0, cn + 6 * (wet - 0.5))
        S = 25400 / cn - 254
        q = (P - 0.2 * S) ** 2 / (P + 0.8 * S) if P > 0.2 * S else 0.0
        infil = P - q
        days_since_rain = 0 if P >= 2 else days_since_rain + 1
        # evapotranspiration
        if c is not None:
            raw = c["p"] * taw
            ks = 1.0 if dr <= raw else max(0.0, (taw - dr) / ((1 - c["p"]) * taw))
            etc = kc * et0[i]
            eta = ks * etc
            # bare soil between rows still evaporates while the crop is small
            if stage == "ini":
                eta += max(0, 0.3 - kc) * et0[i] * math.exp(-days_since_rain / 3)
            p.etc += etc
            p.eta += eta
            if ks < 0.8:
                p.stress_days += 1
                out["stress"][i] = 1
            if c["frost_c"] is not None and stage in c["frost_stages"] and tmin[i] < c["frost_c"]:
                p.frost_hits += 1
            if c["heat_c"] is not None and stage in c["heat_stages"] and tmax[i] > c["heat_c"]:
                p.heat_days += 1
        else:
            tew = 25.0
            ke = 1.0 * math.exp(-days_since_rain / 2.5) if dr < tew else 0.05
            eta = max(0.05, ke) * et0[i]
        dr = dr - infil + eta
        # irrigation back to field capacity when past the stress threshold
        irr = 0.0
        if c is not None and eff and c["irrigated"] and dr > c["p"] * taw:
            irr = dr / eff
            p.irr += irr
            dr = 0.0
        drain = 0.0
        if dr < 0:
            excess = -dr
            drain = min(excess, drain_cap)
            if excess > drain_cap:
                out["waterlog"][i] = 1
                q += 0.5 * (excess - drain_cap)  # what cannot drain partly ponds and runs off
            dr = 0.0
        dr = min(dr, taw)
        out["dr_frac"][i] = dr / taw if taw else 0
        out["eta"][i] = eta
        out["irr"][i] = irr
        out["runoff"][i] = q
        out["drain"][i] = drain
        out["cover"][i] = cover
        out["bare"][i] = 1 if cover < 0.3 else 0
        if P >= EROSIVE_MM:
            out["erosion"][i] = P * (1 - cover) * slope_factor
    daily = pd.DataFrame(out, index=w.index)
    daily["season"] = [d.year if d.month >= 10 else d.year - 1 for d in days]
    yearly = daily.groupby("season").agg(
        irr=("irr", "sum"), runoff=("runoff", "sum"), drain=("drain", "sum"), bare_days=("bare", "sum"),
        erosion=("erosion", "sum"), waterlog_days=("waterlog", "sum"), stress_days=("stress", "sum"),
        live_cover=("cover", lambda x: float((x >= 0.3).mean())))
    yearly["rain"] = w.groupby(daily["season"].to_numpy())["rain"].sum().to_numpy()
    monthly = daily["irr"].groupby(daily.index.month).sum() / max(1, len(yearly))
    return Result(plantings, daily, yearly, {int(m): round(float(v), 1) for m, v in monthly.items()})
