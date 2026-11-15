"""Niva backend: the small API the ESP32 field system talks to.

The device posts a reading every few seconds (POST /readings, signed with its id and key).
Everything else is for looking at those readings and for linking a device to a field.
"""
import os
import secrets
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field as PField
from sqlmodel import Session, select

from models import Device, FieldRow, Reading, engine, hash_key, init_db, utcnow


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Niva API", version="1.0.0", lifespan=lifespan)

# Browsers that may read the API: comma-separated list in .env. The ESP32 is not a browser and needs none.
origins = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])


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
    battery_v: Optional[float] = None  # accepted, not stored
    age_s: int = PField(0, ge=0, le=86400)  # seconds since measured (readings queued while offline)


class FieldIn(BaseModel):
    name: str = PField(min_length=1, max_length=80)
    lat: float = PField(ge=-90, le=90)
    lon: float = PField(ge=-180, le=180)


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


# ---------- endpoints ----------

@app.get("/health")
def health():
    return {"status": "ok", "service": "niva-api", "time": utcnow().isoformat()}


@app.post("/readings", status_code=201)
def post_reading(
    body: ReadingIn,
    x_device_id: str = Header(...),
    x_device_key: str = Header(...),
    s: Session = Depends(db),
):
    """The ESP32 calls this. 401 = unknown device or wrong key, 422 = a value out of range."""
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
def create_field(body: FieldIn, s: Session = Depends(db)):
    """Returns the owner token once: keep it, it is needed to pair a device to this field."""
    f = FieldRow(**body.model_dump())
    s.add(f)
    s.commit()
    s.refresh(f)
    return {**field_out(f), "owner_token": f.owner_token}


@app.get("/fields/{field_id}")
def read_field(field_id: int, s: Session = Depends(db)):
    return field_out(get_field(s, field_id))


@app.post("/devices/pair")
def pair_device(body: PairIn, x_owner_token: Optional[str] = Header(None), s: Session = Depends(db)):
    f = get_field(s, body.field_id)
    if not x_owner_token or not secrets.compare_digest(x_owner_token, f.owner_token):
        raise HTTPException(403, "owner token required")
    dev = s.get(Device, body.device_id.strip().upper())
    if not dev or not secrets.compare_digest(dev.pair_code, body.pair_code.strip().upper()):
        raise HTTPException(404, "unknown device or wrong pair code")
    dev.field_id = f.id
    s.add(dev)
    s.commit()
    return {"device_id": dev.id, "field_id": f.id}


@app.get("/fields/{field_id}/live")
def live(field_id: int, s: Session = Depends(db)):
    """The newest reading on a field and when each of its devices was last heard from."""
    get_field(s, field_id)
    r = s.exec(select(Reading).where(Reading.field_id == field_id)
               .order_by(Reading.time.desc()).limit(1)).first()
    devices = s.exec(select(Device).where(Device.field_id == field_id)).all()
    return {
        "field_id": field_id,
        "reading": reading_out(r) if r else None,
        "devices": [{"id": d.id, "last_seen": iso(d.last_seen)} for d in devices],
        "server_time": utcnow().isoformat(),
    }


@app.get("/fields/{field_id}/history")
def history(field_id: int, days: float = Query(7, gt=0, le=90), s: Session = Depends(db)):
    get_field(s, field_id)
    since = utcnow() - timedelta(days=days)
    rows = s.exec(select(Reading).where(Reading.field_id == field_id, Reading.time >= since)
                  .order_by(Reading.time)).all()
    step = max(1, len(rows) // 500)  # at most ~500 points, evenly thinned
    return {"field_id": field_id, "days": days, "readings": [reading_out(r) for r in rows[::step]]}
