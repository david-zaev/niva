"""Niva database tables (SQLite via SQLModel). See DESIGN.md "Database tables"."""
import hashlib
import os
import secrets
from datetime import date as Date, datetime, timezone
from pathlib import Path
from typing import Optional

from sqlmodel import JSON, Column, Field, Session, SQLModel, create_engine, select

# The DB sits next to backend/, not inside it, so redeploying backend/ never wipes data.
# Server: /opt/niva/niva.db
DB_PATH = Path(os.getenv("NIVA_DB", Path(__file__).resolve().parent.parent / "niva.db"))
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_token(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)


class FieldRow(SQLModel, table=True):
    __tablename__ = "fields"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    lat: float
    lon: float
    region: Optional[str] = None  # strumica | ovche-pole | pelagonija
    current_rotation: list = Field(default_factory=list, sa_column=Column(JSON))
    priorities: dict = Field(default_factory=dict, sa_column=Column(JSON))
    owner_token: str = Field(default_factory=new_token, index=True)
    # optional field outline drawn on the map or picked from OSM farmland: [[lat, lon], ...]
    polygon: list = Field(default_factory=list, sa_column=Column(JSON))


class Device(SQLModel, table=True):
    __tablename__ = "devices"
    id: str = Field(primary_key=True)  # NIVA-A1F3
    key_hash: str
    pair_code: str
    field_id: Optional[int] = Field(default=None, foreign_key="fields.id")
    last_seen: Optional[datetime] = None


class Reading(SQLModel, table=True):
    __tablename__ = "readings"
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(foreign_key="devices.id", index=True)
    field_id: Optional[int] = Field(default=None, foreign_key="fields.id", index=True)
    time: datetime = Field(default_factory=utcnow, index=True)
    soil_pct: Optional[float] = None
    soil_temp_c: Optional[float] = None
    air_temp_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None


class ClimateDaily(SQLModel, table=True):
    __tablename__ = "climate_daily"
    field_id: int = Field(foreign_key="fields.id", primary_key=True)
    date: Date = Field(primary_key=True)
    t_max: Optional[float] = None
    t_min: Optional[float] = None
    rain_mm: Optional[float] = None
    humidity: Optional[float] = None
    solar: Optional[float] = None
    wind: Optional[float] = None
    et0: Optional[float] = None
    sm: Optional[float] = None  # top-soil moisture 0-7 cm, m3/m3 (ERA5-Land until SMAP is added)
    t_mean: Optional[float] = None    # NASA POWER T2M
    gwettop: Optional[float] = None   # NASA POWER GWETTOP, surface soil wetness 0-1
    gwetroot: Optional[float] = None  # NASA POWER GWETROOT, root-zone soil wetness 0-1


class Forecast(SQLModel, table=True):
    __tablename__ = "forecasts"
    field_id: int = Field(foreign_key="fields.id", primary_key=True)
    made_at: Date = Field(primary_key=True)
    day: Date = Field(primary_key=True)
    soil_moisture: float
    low: float
    high: float


class Planting(SQLModel, table=True):
    """A crop the farmer planted on a field (for growing-degree-day harvest alerts)."""
    __tablename__ = "plantings"
    id: Optional[int] = Field(default=None, primary_key=True)
    field_id: int = Field(foreign_key="fields.id", index=True)
    crop: str
    planted_on: Date
    harvested_on: Optional[Date] = None


class Harvest(SQLModel, table=True):
    """What the farmer harvested and sold: their own yield history."""
    __tablename__ = "harvests"
    id: Optional[int] = Field(default=None, primary_key=True)
    field_id: int = Field(foreign_key="fields.id", index=True)
    crop: str
    harvested_on: Date
    amount_kg: float
    sold_kg: Optional[float] = None
    price_mkd_kg: Optional[float] = None
    area_ha: Optional[float] = None
    quality: Optional[str] = None
    notes: Optional[str] = None


class PestReport(SQLModel, table=True):
    """A pest or disease the farmer saw on the field ("I see a pest")."""
    __tablename__ = "pest_reports"
    id: Optional[int] = Field(default=None, primary_key=True)
    field_id: int = Field(foreign_key="fields.id", index=True)
    pest: str
    seen_on: Date
    severity: Optional[str] = None  # few | many
    note: Optional[str] = None


class Cache(SQLModel, table=True):
    """Answers from outside services (SoilGrids, MODIS NDVI, weather forecast), kept so we ask rarely."""
    __tablename__ = "cache"
    key: str = Field(primary_key=True)
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utcnow)


# The demo field: the potted plant on stage stands for a field in Ovče Pole near Sveti Nikole.
DEMO_FIELD = dict(name="Ovče Pole (demo plant)", lat=41.865, lon=21.94, region="ovche-pole")


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    with engine.begin() as c:  # create_all never adds columns to a table that already exists
        cols = [r[1] for r in c.exec_driver_sql("PRAGMA table_info(climate_daily)")]
        for col in ("sm", "t_mean", "gwettop", "gwetroot"):
            if col not in cols:
                c.exec_driver_sql(f"ALTER TABLE climate_daily ADD COLUMN {col} FLOAT")
        if "polygon" not in [r[1] for r in c.exec_driver_sql("PRAGMA table_info(fields)")]:
            c.exec_driver_sql("ALTER TABLE fields ADD COLUMN polygon JSON")
    with Session(engine) as s:
        if s.exec(select(FieldRow)).first() is None:
            s.add(FieldRow(**DEMO_FIELD))
            s.commit()
