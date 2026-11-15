"""Niva API: crop rotations for a field from NASA data and the field's own ESP32 soil sensor. See PLAN.md."""
import hashlib
import json
import logging
import math
import os
import secrets
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PField
from sqlmodel import Session, select

import climate
import health
import ndvi
import power
import rotations
import sensor
import simulate
import soil as soilmod
import terrain
from models import Device, Farm, FieldRow, Reading, SoilTest, engine, hash_key, init_db, utcnow

log = logging.getLogger("niva")
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if os.getenv("NIVA_WARM", "1") == "1":
        threading.Thread(target=warm_all, daemon=True).start()
    yield


app = FastAPI(title="Niva API", version="1.0.0", lifespan=lifespan)
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
           if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"],
                   allow_origin_regex=r"http://(localhost|127\.0\.0\.1|192\.168\.\d+\.\d+|10\.\d+\.\d+\.\d+)(:\d+)?")


def db():
    with Session(engine) as s:
        yield s


def iso(t: Optional[datetime]) -> Optional[str]:
    if t is None:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).isoformat()


# ---------- geometry ----------

def area_ha(poly: list) -> float:
    if not poly or len(poly) < 3:
        return 0.0
    lat0 = sum(p[0] for p in poly) / len(poly)
    k = 111320.0
    pts = [((p[1]) * k * math.cos(math.radians(lat0)), p[0] * k) for p in poly]
    s = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i - 1]
        x2, y2 = pts[i]
        s += x1 * y2 - x2 * y1
    return round(abs(s) / 2 / 10000, 2)


def centroid(poly: list) -> tuple[float, float]:
    return sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly)


def km(a, b) -> float:
    p = math.pi / 180
    h = math.sin((b[0] - a[0]) * p / 2) ** 2 + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin((b[1] - a[1]) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))


# ---------- schemas ----------

class ReadingIn(BaseModel):
    soil_pct: Optional[float] = PField(None, ge=0, le=100)
    soil2_pct: Optional[float] = PField(None, ge=0, le=100)
    soil_temp_c: Optional[float] = PField(None, ge=-55, le=125)
    air_temp_c: Optional[float] = PField(None, ge=-50, le=70)
    humidity_pct: Optional[float] = PField(None, ge=0, le=100)
    pressure_hpa: Optional[float] = PField(None, ge=300, le=1100)
    battery_v: Optional[float] = None
    soil_raw: Optional[int] = None
    age_s: int = PField(0, ge=0, le=86400)


class FieldIn(BaseModel):
    name: str = PField(min_length=1, max_length=80)
    polygon: list[list[float]] = PField(min_length=3, max_length=300)
    current_rotation: list[list[str]] = []
    irrigation: Optional[str] = "drip"
    priorities: dict[str, float] = {}
    sensor: Optional[dict] = None


class FieldPatch(BaseModel):
    name: Optional[str] = PField(None, min_length=1, max_length=80)
    polygon: Optional[list[list[float]]] = None
    current_rotation: Optional[list[list[str]]] = None
    chosen_rotation: Optional[str] = None
    irrigation: Optional[str] = None
    priorities: Optional[dict[str, float]] = None
    sensor: Optional[dict] = None
    soil_measured: Optional[dict] = None
    t_offset: Optional[float] = None


class FarmIn(BaseModel):
    name: str = PField(min_length=1, max_length=80)
    village: Optional[str] = None


class TestIn(BaseModel):
    water_ml: Optional[float] = PField(200, ge=0, le=10000)


class SimIn(BaseModel):
    soil: str = "fast"  # fast | slow | loam


class PairIn(BaseModel):
    device_id: str
    pair_code: str
    field_id: int


def field_out(f: FieldRow, s: Session | None = None) -> dict:
    d = f.model_dump()
    if s is not None:
        devs = s.exec(select(Device).where(Device.field_id == f.id)).all()
        d["devices"] = [{"id": x.id, "last_seen": iso(x.last_seen), "simulated": x.id.startswith("SIM-")}
                        for x in devs]
    return d


def get_field(s: Session, field_id: int) -> FieldRow:
    f = s.get(FieldRow, field_id)
    if not f:
        raise HTTPException(404, "field not found")
    return f


# ---------- slow pieces, cached ----------

_lock = threading.Lock()
_terrain: dict = {}
_evals: dict = {}
_ndvi_running: set = set()


def field_terrain(f: FieldRow) -> dict | None:
    key = (f.id, json.dumps(f.polygon))
    if key not in _terrain:
        try:
            _terrain[key] = terrain.for_field(f.lat, f.lon, f.polygon)
        except Exception as e:
            log.warning("terrain failed: %s", e)
            _terrain[key] = None
    return _terrain[key]


def field_ndvi(f: FieldRow, fetch_bg: bool = True) -> tuple[dict | None, str]:
    data = ndvi.series(f.lat, f.lon, f.polygon, fetch=False)
    if data:
        return data, "ready"
    if fetch_bg and f.id not in _ndvi_running:
        _ndvi_running.add(f.id)

        def go(lat=f.lat, lon=f.lon, poly=list(f.polygon), fid=f.id):
            try:
                ndvi.series(lat, lon, poly)
            finally:
                _ndvi_running.discard(fid)
        threading.Thread(target=go, daemon=True).start()
    return None, "loading" if f.id in _ndvi_running else "missing"


_soils: dict = {}


def soil_for(f: FieldRow) -> dict:
    """Soil of the field's location from the global soil map. The rotation plans use only this (never the
    sensor), so they come purely from data about the place."""
    key = (round(f.lat, 4), round(f.lon, 4))
    if key not in _soils:
        _soils[key] = soilmod.for_location(f.lat, f.lon)
    return _soils[key]


def health_soil(f: FieldRow) -> dict:
    """Soil used to read the sensor: the ESP32 soil test if one was applied, else the map soil."""
    return f.soil_measured or soil_for(f)


def ranking(f: FieldRow, priorities: dict | None = None) -> dict:
    """All library rotations plus the current one, simulated and scored for this field."""
    w = power.frame(f.lat, f.lon)
    soil = soil_for(f)
    ter = field_terrain(f)
    slope_factor = ter["erosion_factor"] if ter else 1.0
    t_off = f.t_offset or 0.0
    lib = simulate.library()
    cur = rotations.custom(f.current_rotation) if f.current_rotation else lib[0]
    match = next((r for r in lib if r["seasons"] == cur["seasons"]), None)
    if match:
        cur = {**match, "kind": "current"}
    # options: the farmer's rotation with a winter cover, and library rotations for the same kind of farm
    kind = rotations.farm_type(cur["seasons"])
    cover = rotations.with_cover(cur)
    brk = rotations.keep_and_break({**cur, "_irrigated": f.irrigation not in (None, "none")})
    cands = [cur] + [g for g in (cover, brk)
                     if g and g["seasons"] != cur["seasons"] and all(r["seasons"] != g["seasons"] for r in lib)]
    cands += [r for r in lib if r["seasons"] != cur["seasons"] and rotations.farm_type(r["seasons"]) == kind]
    irrigation = None if f.irrigation in (None, "none") else f.irrigation
    key = hashlib.sha1(json.dumps([f.lat, f.lon, soil, irrigation, slope_factor, t_off, cur["seasons"],
                                   str(w.index[-1])], sort_keys=True, default=str).encode()).hexdigest()
    with _lock:
        evs = _evals.get(key)
    if evs is None:
        evs = [rotations.evaluate(r, w, soil, irrigation, slope_factor, t_off) for r in cands]
        with _lock:
            _evals[key] = evs
    evs = [{k: v for k, v in e.items()} for e in evs]
    now_repeats = len(evs[0]["metrics"]["family_breaks"])
    for e in evs[1:]:
        dry = e["metrics"]["dry_year_yield_pct"]
        repeats = len(e["metrics"]["family_breaks"])
        if dry < rotations.MIN_DRY_YEAR_YIELD:
            why = (f"only {dry}% of normal yield in a dry year with "
                   + ("no irrigation" if irrigation is None else f"{irrigation} irrigation"))
        elif repeats > now_repeats:
            why = "brings pests and soil diseases back sooner than what you grow now"
        else:
            why = None
        e["offered"], e["not_offered_because"] = why is None, why
    rotations.score(evs, priorities if priorities is not None else f.priorities)
    cs = simulate.crops()
    now_crops = {c for s in cur["seasons"] for c in s if not cs[c].get("cover_crop")}
    for e in evs[1:]:
        kept = sorted({c for s in e["seasons"] for c in s} & now_crops)
        e["keeps"] = [cs[c]["name"] for c in kept]
        if kept:
            e["score"] = min(100, e["score"] + rotations.KEEPS_CROP_BONUS)
    return {"evals": evs, "farm_type": kind, "current": evs[0], "soil": soil, "terrain": ter, "weather": w}


def warm(f: FieldRow) -> None:
    try:
        ranking(f)
        field_ndvi(f)
    except Exception as e:
        log.warning("warm field %s failed: %s", f.id, e)


def warm_all() -> None:
    with Session(engine) as s:
        for f in s.exec(select(FieldRow)).all():
            warm(f)


# ---------- basics ----------

@app.get("/health")
def health_check():
    return {"status": "ok", "service": "niva-api", "version": app.version, "time": utcnow().isoformat()}


@app.get("/crops")
def crops():
    return {"crops": list(simulate.crops().values())}


@app.get("/rotation-library")
def rotation_library():
    return {"rotations": simulate.library()}


# ---------- farms and fields ----------

@app.get("/demo")
def demo(s: Session = Depends(db)):
    farm = s.exec(select(Farm).order_by(Farm.id)).first()
    if not farm:
        raise HTTPException(404, "no demo farm: run python seed.py")
    last = s.exec(select(Reading).where(Reading.simulated == False).order_by(Reading.time.desc()).limit(1)).first()  # noqa: E712
    return {"farm_id": farm.id, "last_reading": iso(last.time) if last else None}


@app.post("/farms", status_code=201)
def create_farm(body: FarmIn, s: Session = Depends(db)):
    farm = Farm(**body.model_dump())
    s.add(farm)
    s.commit()
    s.refresh(farm)
    return farm.model_dump()


@app.get("/farms/{farm_id}")
def read_farm(farm_id: int, s: Session = Depends(db)):
    farm = s.get(Farm, farm_id)
    if not farm:
        raise HTTPException(404, "farm not found")
    fields = s.exec(select(FieldRow).where(FieldRow.farm_id == farm_id).order_by(FieldRow.id)).all()
    return {**farm.model_dump(), "fields": [field_out(f, s) for f in fields],
            "area_ha": round(sum(f.area_ha or 0 for f in fields), 2)}


@app.post("/farms/{farm_id}/fields", status_code=201)
def create_field(farm_id: int, body: FieldIn, bg: BackgroundTasks, s: Session = Depends(db)):
    if not s.get(Farm, farm_id):
        raise HTTPException(404, "farm not found")
    lat, lon = centroid(body.polygon)
    cs = simulate.crops()
    rot = [[c for c in season if c in cs] for season in body.current_rotation]
    f = FieldRow(farm_id=farm_id, name=body.name, lat=lat, lon=lon, polygon=body.polygon,
                 area_ha=area_ha(body.polygon), current_rotation=[r for r in rot if r],
                 irrigation=body.irrigation, priorities=body.priorities, sensor=body.sensor)
    s.add(f)
    s.commit()
    s.refresh(f)
    # the farm's ESP32 goes with the field just drawn: a sensor without a field joins it, together with the
    # readings it sent while it had no field, so the soil health card fills straight away
    for d in s.exec(select(Device).where(Device.field_id == None, ~Device.id.startswith("SIM-"))).all():  # noqa: E711
        d.field_id = f.id
        s.add(d)
        for r in s.exec(select(Reading).where(Reading.device_id == d.id, Reading.field_id == None)).all():  # noqa: E711
            r.field_id = f.id
            s.add(r)
    s.commit()
    s.refresh(f)
    bg.add_task(warm, f)
    return field_out(f, s)


@app.get("/fields/{field_id}")
def read_field(field_id: int, s: Session = Depends(db)):
    return field_out(get_field(s, field_id), s)


@app.patch("/fields/{field_id}")
def update_field(field_id: int, body: FieldPatch, bg: BackgroundTasks, s: Session = Depends(db)):
    f = get_field(s, field_id)
    data = body.model_dump(exclude_unset=True)
    if "polygon" in data and data["polygon"]:
        f.lat, f.lon = centroid(data["polygon"])
        f.area_ha = area_ha(data["polygon"])
    for k, v in data.items():
        setattr(f, k, v)
    s.add(f)
    s.commit()
    s.refresh(f)
    bg.add_task(warm, f)
    return field_out(f, s)


@app.delete("/fields/{field_id}", status_code=204)
def delete_field(field_id: int, s: Session = Depends(db)):
    f = get_field(s, field_id)
    for d in s.exec(select(Device).where(Device.field_id == field_id)).all():
        d.field_id = None
        s.add(d)
    for r in s.exec(select(Reading).where(Reading.field_id == field_id)).all():
        r.field_id = None
        s.add(r)
    for t in s.exec(select(SoilTest).where(SoilTest.field_id == field_id)).all():
        s.delete(t)
    s.delete(f)
    s.commit()


# ---------- NASA evidence for a field ----------

@app.get("/fields/{field_id}/profile")
def profile(field_id: int, s: Session = Depends(db)):
    f = get_field(s, field_id)
    w = power.frame(f.lat, f.lon)
    cl = climate.profile(w, f.t_offset or 0.0)
    nd, status = field_ndvi(f)
    return {
        "field_id": field_id,
        "power_cell": power.cell(f.lat, f.lon),
        "climate": cl,
        "today": climate.today_vs_history(w),
        "terrain": field_terrain(f),
        "soil": soil_for(f),
        "ndvi": ndvi.analyse(nd, cl["rain_apr_aug_pct"]) if nd else None,
        "ndvi_status": status,
    }


@app.get("/fields/{field_id}/rotations")
def field_rotations(field_id: int, show: int = Query(3, ge=2, le=10), s: Session = Depends(db)):
    """The current rotation and the best `show` alternatives, each with its card. Location data only."""
    f = get_field(s, field_id)
    r = ranking(f)
    evs, cur = r["evals"], r["current"]
    w = r["weather"]
    nd, _ = field_ndvi(f, fetch_bg=False)
    cl = climate.profile(w, f.t_offset or 0.0)
    ctx = {"climate": cl, "t_offset": f.t_offset or 0.0, "terrain": r["terrain"], "soil": r["soil"],
           "ndvi": ndvi.analyse(nd, cl["rain_apr_aug_pct"]) if nd else None,
           "smap_check": rotations.smap_check(cur["_runs"][0], f.lat, f.lon)}
    alts = sorted([e for e in evs[1:] if e["offered"]], key=lambda e: -e["score"])
    picked = [cur] + alts[:show]
    out = []
    for e in picked:
        o = {k: v for k, v in e.items() if not k.startswith("_")}
        o["card"] = rotations.card(e, cur, ctx)
        o["plant_next"] = rotations.plant_next(e["seasons"], cur["seasons"])
        if e.get("keeps"):
            o["card"]["why"].append(f"Keeps {' and '.join(k.lower() for k in e['keeps'])}, which you already grow: "
                                    "you know the methods, the buyers and have the machinery.")
        o["rank"] = 1 + sorted(evs, key=lambda x: -x["score"]).index(e)
        out.append(o)
    others = [{"id": e["id"], "name": e["name"], "score": e["score"], "scores": e["scores"]} for e in alts[show:]]
    dropped = [{"id": e["id"], "name": e["name"], "because": e["not_offered_because"]}
               for e in evs[1:] if not e["offered"]]
    return {"field_id": field_id, "soil": r["soil"], "terrain": r["terrain"], "irrigation": f.irrigation,
            "priorities": {**rotations.WEIGHTS, **(f.priorities or {})}, "rotations": out, "others": others,
            "not_offered": dropped, "farm_type": r["farm_type"],
            "smap_check": ctx["smap_check"], "chosen": f.chosen_rotation,
            "climate_years": cl["years"]}


# ---------- ESP32 ----------

@app.post("/readings", status_code=201)
def post_reading(body: ReadingIn, x_device_id: str = Header(...), x_device_key: str = Header(...),
                 s: Session = Depends(db)):
    dev = s.get(Device, x_device_id)
    if not dev or not secrets.compare_digest(dev.key_hash, hash_key(x_device_key)):
        raise HTTPException(401, "unknown device or wrong key")
    now = utcnow()
    measured = now - timedelta(seconds=body.age_s)
    r = Reading(device_id=dev.id, field_id=dev.field_id, time=measured,
                **body.model_dump(exclude={"battery_v", "age_s", "soil_raw"}))
    dev.last_seen = now
    s.add(r)
    s.add(dev)
    s.commit()
    return {"ok": True, "time": iso(measured), "field_id": dev.field_id}


@app.post("/devices/pair")
def pair_device(body: PairIn, s: Session = Depends(db)):
    f = get_field(s, body.field_id)
    dev = s.get(Device, body.device_id.strip().upper())
    if not dev or not secrets.compare_digest(dev.pair_code, body.pair_code.strip().upper()):
        raise HTTPException(404, "unknown device or wrong pair code")
    dev.field_id = f.id
    s.add(dev)
    s.commit()
    return {"device_id": dev.id, "field_id": f.id}


def readings_since(s: Session, field_id: int, since: datetime, include_sim: bool = True):
    q = select(Reading).where(Reading.field_id == field_id, Reading.time >= since)
    if not include_sim:
        q = q.where(Reading.simulated == False)  # noqa: E712
    return s.exec(q.order_by(Reading.time)).all()


def reading_out(r: Reading) -> dict:
    return {"time": iso(r.time), "soil_pct": r.soil_pct, "soil2_pct": r.soil2_pct, "soil_temp_c": r.soil_temp_c,
            "air_temp_c": r.air_temp_c, "humidity_pct": r.humidity_pct, "pressure_hpa": r.pressure_hpa,
            "simulated": r.simulated}


def current_crop(f: FieldRow) -> dict | None:
    """The crop most likely in the field now, from the current rotation's first season and today's date."""
    if not f.current_rotation:
        return None
    cs = simulate.crops()
    today = utcnow().date()
    season = f.current_rotation[0]
    y = today.year if today.month >= 10 else today.year - 1
    for cid in season:
        c = cs.get(cid)
        if not c:
            continue
        start = simulate._sow_date(c, y)
        end = start + timedelta(days=sum(c["stages"]))
        if start <= today <= end:
            return c
    main = [cs[c] for c in season if c in cs and not cs[c].get("cover_crop")]
    return main[0] if main else None


@app.get("/fields/{field_id}/live")
def live(field_id: int, minutes: int = Query(120, ge=5, le=60 * 24 * 14), s: Session = Depends(db)):
    f = get_field(s, field_id)
    now = utcnow()
    recent = readings_since(s, field_id, now - timedelta(minutes=minutes))
    df = sensor.frame(recent)
    long = sensor.frame(readings_since(s, field_id, now - timedelta(days=14), include_sim=False))
    w = power.frame(f.lat, f.lon)
    crop = current_crop(f)
    soil = health_soil(f)
    lt = s.exec(select(SoilTest).where(SoilTest.field_id == field_id).order_by(SoilTest.id.desc())).first()
    last = s.exec(select(Reading).where(Reading.field_id == field_id).order_by(Reading.time.desc()).limit(1)).first()
    devs = s.exec(select(Device).where(Device.field_id == field_id)).all()
    return {
        "field_id": field_id,
        "reading": reading_out(last) if last else None,
        "age_s": round((now - (last.time if last.time.tzinfo else last.time.replace(tzinfo=timezone.utc)))
                       .total_seconds()) if last else None,
        "devices": [{"id": d.id, "last_seen": iso(d.last_seen)} for d in devs],
        "series": [reading_out(r) for r in recent[-720:]],
        "alerts": sensor.alerts(df, crop, soil) if not df.empty else [],
        "health": health.health(df, long, soil, crop, w, {**lt.result, "simulated": lt.simulated}
                                if lt and lt.result else None),
        "crop_now": {"id": crop["id"], "name": crop["name"], "p": crop["p"]} if crop else None,
        "soil": {"fc": soil["fc"], "wp": soil["wp"], "measured": soil["measured"], "label": soil["label"]},
        "dew_point": sensor.dew_point(last.air_temp_c, last.humidity_pct) if last and last.air_temp_c is not None
        and last.humidity_pct is not None else None,
        "microclimate": sensor.microclimate(long, w) if not long.empty else {"ok": False},
        "season_log": sensor.season_log(long),
        "nasa_today": climate.today_vs_history(w),
        "t_offset": f.t_offset,
    }


@app.post("/fields/{field_id}/microclimate/apply")
def apply_microclimate(field_id: int, s: Session = Depends(db)):
    f = get_field(s, field_id)
    now = utcnow()
    df = sensor.frame(readings_since(s, field_id, now - timedelta(days=14), include_sim=False))
    m = sensor.microclimate(df, power.frame(f.lat, f.lon)) if not df.empty else {"ok": False}
    if not m.get("ok") or m.get("offset_c") is None:
        raise HTTPException(409, "not enough full days that overlap NASA POWER yet")
    f.t_offset = m["offset_c"]
    s.add(f)
    s.commit()
    return {"t_offset": f.t_offset}


# ---------- soil test ----------

def test_out(t: SoilTest, s: Session) -> dict:
    df = sensor.frame(readings_since(s, t.field_id, (t.started_at if t.started_at.tzinfo else
                                                     t.started_at.replace(tzinfo=timezone.utc)) - timedelta(minutes=3)))
    if t.ended_at:
        end = t.ended_at if t.ended_at.tzinfo else t.ended_at.replace(tzinfo=timezone.utc)
        df = df[df.index <= end]
    res = sensor.analyse_test(df, t.started_at, t.ended_at) if not df.empty else {"ok": False,
                                                                                   "message": "No readings yet."}
    pots = sensor.compare_pots(df, t.started_at, t.ended_at) if not df.empty else None
    return {"id": t.id, "field_id": t.field_id, "started_at": iso(t.started_at), "ended_at": iso(t.ended_at),
            "water_ml": t.water_ml, "simulated": t.simulated, "running": t.ended_at is None,
            "analysis": res, "pots": pots}


@app.post("/fields/{field_id}/soil-test", status_code=201)
def start_test(field_id: int, body: TestIn, s: Session = Depends(db)):
    get_field(s, field_id)
    for old in s.exec(select(SoilTest).where(SoilTest.field_id == field_id, SoilTest.ended_at == None)).all():  # noqa
        old.ended_at = utcnow()
        s.add(old)
    t = SoilTest(field_id=field_id, water_ml=body.water_ml)
    s.add(t)
    s.commit()
    s.refresh(t)
    return test_out(t, s)


@app.get("/fields/{field_id}/soil-test")
def latest_test(field_id: int, s: Session = Depends(db)):
    t = s.exec(select(SoilTest).where(SoilTest.field_id == field_id).order_by(SoilTest.id.desc())).first()
    return {"test": test_out(t, s) if t else None}


@app.post("/soil-tests/{test_id}/stop")
def stop_test(test_id: int, s: Session = Depends(db)):
    t = s.get(SoilTest, test_id)
    if not t:
        raise HTTPException(404, "test not found")
    if t.ended_at is None:
        t.ended_at = utcnow()
    out = test_out(t, s)
    t.result = out["analysis"]
    s.add(t)
    s.commit()
    return out


@app.post("/soil-tests/{test_id}/apply")
def apply_test(test_id: int, s: Session = Depends(db)):
    """Use the measured soil for this field's simulations from now on."""
    t = s.get(SoilTest, test_id)
    if not t:
        raise HTTPException(404, "test not found")
    out = test_out(t, s)
    a = out["analysis"]
    if not a.get("ok"):
        raise HTTPException(409, a.get("message", "test has no usable curve"))
    f = get_field(s, t.field_id)
    f.soil_measured = {**a["soil"], "test_id": t.id, "simulated": t.simulated,
                       "measured_at": out["started_at"],
                       **({"label": a["soil"]["label"].replace("Measured by the ESP32 soil test",
                                                              "Simulated soil test (no sensor)")}
                          if t.simulated else {})}
    s.add(f)
    s.commit()
    threading.Thread(target=warm, args=(f,), daemon=True).start()
    return {"soil": f.soil_measured}


@app.delete("/fields/{field_id}/soil")
def reset_soil(field_id: int, s: Session = Depends(db)):
    f = get_field(s, field_id)
    f.soil_measured = None
    s.add(f)
    s.commit()
    return {"soil": soilmod.DEFAULT}


SIM_CURVES = {  # (soak-in time constant s, peak %, drain %/h, settle %): clearly labelled as simulated
    "fast": (20, 78, 30, 41), "loam": (90, 82, 12, 56), "slow": (420, 86, 3, 70)}


@app.post("/fields/{field_id}/soil-test/simulate", status_code=201)
def simulate_test(field_id: int, body: SimIn, s: Session = Depends(db)):
    """No sensor at hand: write a simulated 12-minute test curve (flagged simulated everywhere)."""
    f = get_field(s, field_id)
    dev_id = f"SIM-{field_id}"
    dev = s.get(Device, dev_id)
    if not dev:
        dev = Device(id=dev_id, key_hash=hash_key(secrets.token_urlsafe(16)), pair_code="SIMULA", field_id=field_id)
        s.add(dev)
    tau, peak, drain, settle = SIM_CURVES.get(body.soil, SIM_CURVES["fast"])
    now = utcnow()
    start = now - timedelta(minutes=12)
    base = 34.0
    import random
    rnd = random.Random(field_id)
    for k in range(-24, 12 * 12 + 1):
        t = start + timedelta(seconds=5 * k)
        sec = 5 * k
        if sec < 0:
            v = base
        else:
            rise = base + (peak - base) * (1 - math.exp(-sec / tau))
            fall = peak - (drain / 3600) * max(0, sec - 4 * tau) * 1.0
            v = min(rise, max(settle, fall)) if sec > 4 * tau else rise
        s.add(Reading(device_id=dev_id, field_id=field_id, time=t, soil_pct=round(v + rnd.uniform(-0.4, 0.4), 1),
                      air_temp_c=12.0, humidity_pct=70.0, pressure_hpa=990.0, simulated=True))
    test = SoilTest(field_id=field_id, started_at=start, ended_at=now, water_ml=200, simulated=True)
    s.add(test)
    s.commit()
    s.refresh(test)
    out = test_out(test, s)
    test.result = out["analysis"]
    s.add(test)
    s.commit()
    return out


# ---------- farm plan ----------

@app.get("/farms/{farm_id}/plan")
def farm_plan(farm_id: int, s: Session = Depends(db)):
    """All fields together: water by month, plant families per season, neighbours, income spread."""
    fields = s.exec(select(FieldRow).where(FieldRow.farm_id == farm_id).order_by(FieldRow.id)).all()
    cs = simulate.crops()
    rows, water = [], {m: 0.0 for m in range(1, 13)}
    next_season = utcnow().year if utcnow().month >= 10 else utcnow().year - 1
    for f in fields:
        r = ranking(f)
        evs = r["evals"]
        chosen = next((e for e in evs if e["id"] == f.chosen_rotation), None) or r["current"]
        L = len(chosen["seasons"])
        seasons = []
        for k in range(3):
            crops_k = chosen["seasons"][k % L]
            seasons.append({"season": f"{next_season + k}/{(next_season + k + 1) % 100:02d}",
                            "crops": [{"id": c, "name": cs[c]["name"], "family": cs[c]["family"],
                                       "cover": bool(cs[c].get("cover_crop"))} for c in crops_k]})
        for m, v in chosen["monthly_irrigation_mm"].items():
            water[int(m)] += v * 10 * (f.area_ha or 0)
        rows.append({"field_id": f.id, "name": f.name, "area_ha": f.area_ha, "rotation": chosen["name"],
                     "rotation_id": chosen["id"], "is_current": chosen["id"] == r["current"]["id"],
                     "irrigation_m3": round(chosen["metrics"]["irrigation_mm"] * 10 * (f.area_ha or 0)),
                     "gross_eur": round(chosen["metrics"]["gross_eur_ha"] * (f.area_ha or 0)),
                     "seasons": seasons, "centre": [f.lat, f.lon], "polygon": f.polygon,
                     "soil_measured": bool(f.soil_measured)})
    total = sum(f.area_ha or 0 for f in fields) or 1
    found: dict = {}  # same warning in several seasons -> one line listing the seasons

    def warn(kind, key, text_fn, label):
        found.setdefault((kind, key), {"kind": kind, "text_fn": text_fn, "seasons": []})["seasons"].append(label)
    for k in range(3):
        fam_area, crop_area = {}, {}
        for row in rows:
            for c in row["seasons"][k]["crops"]:
                if c["cover"]:
                    continue
                fam_area[c["family"]] = fam_area.get(c["family"], 0) + (row["area_ha"] or 0)
                crop_area[c["name"]] = crop_area.get(c["name"], 0) + (row["area_ha"] or 0)
        label = rows[0]["seasons"][k]["season"] if rows else ""
        if len(rows) > 1:
            for fam, a in fam_area.items():
                if a / total >= 0.6:
                    pct = round(100 * a / total)
                    warn("pests", fam, lambda ss, fam=fam, pct=pct: f"{pct}% of the farm is {fam} in {ss}: pests and "
                         f"diseases of that family can build up across fields.", label)
            for name, a in crop_area.items():
                if a / total >= 0.6:
                    pct = round(100 * a / total)
                    warn("income", name, lambda ss, name=name, pct=pct: f"About {pct}% of the farm in "
                         f"{name.lower()} in {ss}: one bad price or one disease hits most of the income.", label)
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a, b = rows[i], rows[j]
                common = ({c["family"] for c in a["seasons"][k]["crops"] if not c["cover"]}
                          & {c["family"] for c in b["seasons"][k]["crops"] if not c["cover"]})
                d = km(a["centre"], b["centre"])
                if common and d < 1.0:
                    fams = ", ".join(sorted(common))
                    warn("neighbours", (a["name"], b["name"], fams),
                         lambda ss, a=a, b=b, d=d, fams=fams: f"{a['name']} and {b['name']} ({round(d * 1000)} m apart) "
                         f"both grow {fams} in {ss}: pests move between them.", label)
    warnings = []
    for w in found.values():
        ss = w["seasons"]
        when = ss[0] if len(ss) == 1 else ("every season" if len(ss) == 3 else " and ".join(ss))
        warnings.append({"kind": w["kind"], "seasons": ss, "text": w["text_fn"](when)})
    # an income warning about a crop that is the whole of a flagged family says the same thing twice
    pest_text = {tuple(w["seasons"]) for w in warnings if w["kind"] == "pests"}
    warnings = [w for w in warnings if not (w["kind"] == "income" and len(w["seasons"]) == 1
                                            and tuple(w["seasons"]) in pest_text)] or warnings
    peak = max(water.items(), key=lambda kv: kv[1]) if fields else (7, 0)
    return {"farm_id": farm_id, "fields": rows, "area_ha": round(total, 2),
            "water_m3_by_month": {m: round(v) for m, v in water.items()},
            "water_m3_year": round(sum(water.values())), "peak_month": peak[0], "peak_m3": round(peak[1]),
            "gross_eur_year": sum(r["gross_eur"] for r in rows), "warnings": warnings}
