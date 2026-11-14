"""Niva backend: FastAPI app. Endpoints follow DESIGN.md "API"."""
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PField
from sqlmodel import Session, select

import forecast
import jobs
import nasa
import scoring
from models import Device, FieldRow, Forecast, Reading, engine, hash_key, init_db, utcnow


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    sched = jobs.start() if os.getenv("NIVA_JOBS", "1") == "1" else None
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="Niva API", version="0.3.0", lifespan=lifespan)

# Comma-separated list in .env, e.g. "https://<org>.github.io,http://localhost:5173"
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
# Date is exposed so the app can tell a fresh answer from the service worker's saved copy (OfflineBanner)
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"],
                   expose_headers=["Date"])


def db():
    with Session(engine) as s:
        yield s


def iso(t: Optional[datetime]) -> Optional[str]:
    if t is None:
        return None
    return (t if t.tzinfo else t.replace(tzinfo=timezone.utc)).isoformat()  # SQLite drops the zone: it is UTC


# ---------- schemas ----------

class ReadingIn(BaseModel):
    soil_pct: Optional[float] = PField(None, ge=0, le=100)
    soil_temp_c: Optional[float] = PField(None, ge=-55, le=125)
    air_temp_c: Optional[float] = PField(None, ge=-50, le=70)
    humidity_pct: Optional[float] = PField(None, ge=0, le=100)
    pressure_hpa: Optional[float] = PField(None, ge=300, le=1100)
    battery_v: Optional[float] = None  # accepted, not stored yet
    age_s: int = PField(0, ge=0, le=86400)  # seconds since measured (readings queued while offline)


class FieldIn(BaseModel):
    name: str = PField(min_length=1, max_length=80)
    lat: float = PField(ge=-90, le=90)
    lon: float = PField(ge=-180, le=180)
    region: Optional[str] = None
    current_rotation: list[str] = []
    priorities: dict[str, float] = {}


class FieldPatch(BaseModel):
    name: Optional[str] = PField(None, min_length=1, max_length=80)
    current_rotation: Optional[list[str]] = None
    priorities: Optional[dict[str, float]] = None


class PairIn(BaseModel):
    device_id: str
    pair_code: str
    field_id: int


def field_out(f: FieldRow) -> dict:
    return f.model_dump(exclude={"owner_token"})


def reading_out(r: Reading) -> dict:
    return {
        "time": iso(r.time),
        "device_id": r.device_id,
        "soil_pct": r.soil_pct,
        "soil_temp_c": r.soil_temp_c,
        "air_temp_c": r.air_temp_c,
        "humidity_pct": r.humidity_pct,
        "pressure_hpa": r.pressure_hpa,
    }


def get_field(s: Session, field_id: int) -> FieldRow:
    f = s.get(FieldRow, field_id)
    if not f:
        raise HTTPException(404, "field not found")
    return f


def check_owner(f: FieldRow, token: Optional[str]) -> None:
    if not token or not secrets.compare_digest(token, f.owner_token):
        raise HTTPException(403, "owner token required")


# ---------- endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok", "service": "niva-api", "time": datetime.now(timezone.utc).isoformat()}


@app.post("/readings", status_code=201)
def post_reading(
    body: ReadingIn,
    x_device_id: str = Header(...),
    x_device_key: str = Header(...),
    s: Session = Depends(db),
):
    dev = s.get(Device, x_device_id)
    if not dev or not secrets.compare_digest(dev.key_hash, hash_key(x_device_key)):
        raise HTTPException(401, "unknown device or wrong key")
    now = utcnow()
    measured = now - timedelta(seconds=body.age_s)
    r = Reading(device_id=dev.id, field_id=dev.field_id, time=measured,
                **body.model_dump(exclude={"battery_v", "age_s"}))
    dev.last_seen = now
    s.add(r)
    s.add(dev)
    s.commit()
    return {"ok": True, "time": iso(measured), "field_id": dev.field_id}


@app.post("/fields", status_code=201)
def create_field(body: FieldIn, bg: BackgroundTasks, s: Session = Depends(db)):
    f = FieldRow(**body.model_dump())
    s.add(f)
    s.commit()
    s.refresh(f)
    bg.add_task(jobs.run_one, f.id)  # its first soil forecast, without waiting for 06:00
    return {**field_out(f), "owner_token": f.owner_token}


@app.get("/fields/{field_id}")
def read_field(field_id: int, s: Session = Depends(db)):
    return field_out(get_field(s, field_id))


@app.patch("/fields/{field_id}")
def update_field(field_id: int, body: FieldPatch, x_owner_token: Optional[str] = Header(None),
                 s: Session = Depends(db)):
    f = get_field(s, field_id)
    check_owner(f, x_owner_token)
    for k, v in body.model_dump(exclude_none=True).items():
        setattr(f, k, v)
    s.add(f)
    s.commit()
    s.refresh(f)
    return field_out(f)


@app.post("/devices/pair")
def pair_device(body: PairIn, x_owner_token: Optional[str] = Header(None), s: Session = Depends(db)):
    f = get_field(s, body.field_id)
    check_owner(f, x_owner_token)
    dev = s.get(Device, body.device_id.strip().upper())
    if not dev or not secrets.compare_digest(dev.pair_code, body.pair_code.strip().upper()):
        raise HTTPException(404, "unknown device or wrong pair code")
    dev.field_id = f.id
    s.add(dev)
    s.commit()
    return {"device_id": dev.id, "field_id": f.id}


@app.get("/fields/{field_id}/live")
def live(field_id: int, s: Session = Depends(db)):
    f = get_field(s, field_id)
    r = s.exec(select(Reading).where(Reading.field_id == field_id)
               .order_by(Reading.time.desc()).limit(1)).first()
    devices = s.exec(select(Device).where(Device.field_id == field_id)).all()
    loc, km, _ = nasa.location_for(f.lat, f.lon, f.region)
    return {
        "field_id": field_id,
        "reading": reading_out(r) if r else None,
        "devices": [{"id": d.id, "last_seen": iso(d.last_seen)} for d in devices],
        "server_time": datetime.now(timezone.utc).isoformat(),
        # NASA values for the same place; SMAP joins when the Data role adds it
        "nasa": {"location": loc["id"], "distance_km": km,
                 "power": nasa.latest_power(loc["id"]), "smap": None},
    }


@app.get("/fields/{field_id}/history")
def history(field_id: int, days: float = Query(7, gt=0, le=90), s: Session = Depends(db)):
    get_field(s, field_id)
    since = utcnow() - timedelta(days=days)
    rows = s.exec(select(Reading).where(Reading.field_id == field_id, Reading.time >= since)
                  .order_by(Reading.time)).all()
    # Keep the answer small for phones: at most ~500 points, evenly thinned
    step = max(1, len(rows) // 500)
    return {"field_id": field_id, "days": days, "readings": [reading_out(r) for r in rows[::step]]}


@app.get("/fields/{field_id}/climate")
def climate(field_id: int, s: Session = Depends(db)):
    f = get_field(s, field_id)
    loc, km, exact = nasa.location_for(f.lat, f.lon, f.region)
    ind = nasa.indicators(loc["id"])
    if ind is None:
        raise HTTPException(503, "climate indicators not computed yet")
    return {
        "field_id": field_id,
        "distance_km": km,
        # Outside the 3 demo regions the nearest one stands in: say so, and lower confidence
        "confidence": "high" if exact and km < 25 else "medium" if km < 60 else "low",
        **ind,
    }


@app.get("/fields/{field_id}/rotations")
def rotations(field_id: int,
              rain: float = Query(0, ge=-50, le=50, description="What-if: rain change in %"),
              temp: float = Query(0, ge=0, le=3, description="What-if: warming in °C"),
              s: Session = Depends(db)):
    f = get_field(s, field_id)
    loc, km, _ = nasa.location_for(f.lat, f.lon, f.region)
    ind = nasa.indicators(loc["id"])
    crops_f, lib_f = nasa.read_data_file("crops.json"), nasa.read_data_file("rotations.json")
    if ind is None or crops_f is None or lib_f is None:
        raise HTTPException(503, "crop table, rotation library or indicators missing")
    crops = {c["id"]: c for c in crops_f["crops"]}
    library = lib_f["rotations"]
    yields = nasa.read_data_file("yields.json") or {"locations": {}}
    prices = nasa.read_data_file("prices.json") or {"prices": []}

    valid = [c for c in (f.current_rotation or []) if c in crops]
    if valid:
        current = {"id": "current", "name": " → ".join(crops[c]["name"] for c in valid),
                   "plantings": [{"crop": c, "year": i + 1} for i, c in enumerate(valid)]}
    else:  # no rotation entered yet: use what is common in the region
        current = next(r for r in library if r.get("kind") == "common" and loc["id"] in r.get("regions", []))
    out = scoring.rank(library, crops, {**ind, "_distance_km": km}, yields, prices, current,
                       priorities=f.priorities, what_if={"rain": rain, "temp": temp})
    yield_years = sorted({value['years'] for value in yields.get('locations', {}).get(loc['id'], {}).get('crops', {}).values() if value})
    return {
        "field_id": field_id, "location": ind["location"], "distance_km": km,
        "what_if": {"rain_pct": rain, "temp_c": temp},
        "current_is_default": not valid,
        **out,
        "sources": [
            {"dataset": "NASA POWER daily", "dates": ind["sources"][0]["dates"]},
            {"dataset": "MakStat crop yields by municipality", "dates": ', '.join(yield_years) or 'not available'},
            {"dataset": "ZPIS prices (Ministry of Agriculture)", "dates": f"retrieved {prices.get('retrieved')}"},
        ],
    }


@app.get("/fields/{field_id}/forecast")
def soil_forecast(field_id: int, s: Session = Depends(db)):
    f = get_field(s, field_id)
    made = s.exec(select(Forecast.made_at).where(Forecast.field_id == field_id)
                  .order_by(Forecast.made_at.desc()).limit(1)).first()
    rep = forecast.report()
    if made is None or rep is None:
        raise HTTPException(503, "forecast not made yet")
    rows = s.exec(select(Forecast).where(Forecast.field_id == field_id, Forecast.made_at == made)
                  .order_by(Forecast.day)).all()
    loc, km, _ = nasa.location_for(f.lat, f.lon, f.region)
    lr = rep["locations"][loc["id"]]
    anchor = rows[0].day
    today = datetime.now(timezone.utc).date()
    by_day = {r.day: r for r in rows}
    days = [by_day[d] for d in (today + timedelta(days=i) for i in range(8)) if d in by_day]
    if not days:
        raise HTTPException(503, "forecast is out of date")

    # Field correction: SMAP/ERA5 see ~9 km, the sensor sees one spot. A fresh sensor reading shifts the whole
    # curve so today's value matches it; the shape (drying, wetting) still comes from the model.
    r = s.exec(select(Reading).where(Reading.field_id == field_id, Reading.soil_pct != None)  # noqa: E711
               .order_by(Reading.time.desc()).limit(1)).first()
    offset, reading = 0.0, None
    if r and utcnow() - (r.time if r.time.tzinfo else r.time.replace(tzinfo=timezone.utc)) < timedelta(hours=6):
        offset = max(-25.0, min(25.0, r.soil_pct - days[0].soil_moisture))
        reading = {"time": iso(r.time), "soil_pct": r.soil_pct}

    # Irrigation advice compares the uncorrected model with this place's own dry/wet days (same units)
    low7 = min(d.soil_moisture for d in days)
    advice = "dry" if low7 < lr["dry_threshold_pct"] else "wet" if days[-1].soil_moisture > lr["wet_threshold_pct"] else "ok"
    h_end = (days[-1].day - anchor).days
    mae, base = lr["test"]["mae_pct_points"][h_end - 1], lr["test"]["mae_no_change_baseline"][h_end - 1]
    return {
        "field_id": field_id, "made_at": made.isoformat(), "data_until": anchor.isoformat(),
        "unit": "volumetric % (top 7 cm)", "location": loc["id"], "distance_km": km,
        "days": [{"day": d.day.isoformat(), "soil_moisture": round(d.soil_moisture + offset, 1),
                  "low": round(max(0.0, d.low + offset), 1), "high": round(d.high + offset, 1)} for d in days],
        "field_correction": {"applied": reading is not None, "offset": round(offset, 1), "reading": reading},
        "advice": advice, "dry_threshold": lr["dry_threshold_pct"] + offset,
        "error": {"mae_pct_points": mae, "no_change_mae": base, "days_ahead": h_end,
                  "test_years": rep["test"]},
        "top_inputs": [i["input"] for i in lr["importance"][:3]],
        "confidence": "medium" if km < 60 else "low",
        "sources": [
            {"dataset": "NASA POWER daily", "dates": f"to {anchor.isoformat()}"},
            {"dataset": "ERA5-Land soil moisture 0-7 cm (Open-Meteo), backup for NASA SMAP",
             "dates": f"to {anchor.isoformat()}"},
            {"dataset": "Model trained on 2015-2022, tested on 2023-2024", "dates": f"trained {rep['trained']}"},
        ],
    }


def data_file_or_empty(name: str, key: str):
    data = nasa.read_data_file(name)
    if data is None:
        return {key: [], "status": "not filled yet", "file": f"data/{name}"}
    return data


@app.get("/crops")
def crops():
    return data_file_or_empty("crops.json", "crops")


@app.get("/prices")
def prices():
    return data_file_or_empty("prices.json", "prices")


@app.get("/buyers")
def buyers(crop: Optional[str] = None, region: Optional[str] = None):
    data = data_file_or_empty("buyers.json", "buyers")
    items = data.get("buyers", [])
    if crop:
        items = [b for b in items if crop in b.get("crops", [])]
    if region:
        items = [b for b in items if b.get("region") == region]
    return {**data, "buyers": items}
