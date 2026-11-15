"""Niva database tables (SQLite via SQLModel): farms, fields drawn on the map, ESP32 devices and readings,
soil tests, and a cache for slow outside services (MODIS NDVI)."""
import hashlib
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel, create_engine

# niva2.db: the rotation version starts a fresh database (the old app's niva.db is left alone)
DB_PATH = Path(os.getenv("NIVA_DB", Path(__file__).resolve().parent.parent / "niva2.db"))
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def new_token(nbytes: int = 24) -> str:
    return secrets.token_urlsafe(nbytes)


class Farm(SQLModel, table=True):
    __tablename__ = "farms"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    village: Optional[str] = None
    created: datetime = Field(default_factory=utcnow)


class FieldRow(SQLModel, table=True):
    __tablename__ = "fields"
    id: Optional[int] = Field(default=None, primary_key=True)
    farm_id: int = Field(foreign_key="farms.id", index=True)
    name: str
    lat: float  # centre of the outline
    lon: float
    polygon: list = Field(default_factory=list, sa_column=Column(JSON))  # [[lat, lon], ...]
    area_ha: Optional[float] = None
    # what grows now, as seasons (October-September), e.g. [["pepper"], ["pepper"], ["tomato"]]
    current_rotation: list = Field(default_factory=list, sa_column=Column(JSON))
    chosen_rotation: Optional[str] = None  # rotation id the farmer picked (farm plan)
    irrigation: Optional[str] = "drip"     # drip | sprinkler | furrow | none
    priorities: dict = Field(default_factory=dict, sa_column=Column(JSON))  # water/soil/resilience/income weights
    sensor: Optional[dict] = Field(default=None, sa_column=Column(JSON))    # {"lat":..,"lon":..} where the ESP32 is
    soil_measured: Optional[dict] = Field(default=None, sa_column=Column(JSON))  # result of the latest soil test
    t_offset: Optional[float] = None  # field night temperature minus NASA POWER, °C (from the ESP32)
    notes: Optional[str] = None


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
    soil2_pct: Optional[float] = None  # optional second probe (covered pot in the demo)
    soil_temp_c: Optional[float] = None
    air_temp_c: Optional[float] = None
    humidity_pct: Optional[float] = None
    pressure_hpa: Optional[float] = None
    simulated: bool = False  # made by the "simulate a test" button, never by hardware


class SoilTest(SQLModel, table=True):
    __tablename__ = "soil_tests"
    id: Optional[int] = Field(default=None, primary_key=True)
    field_id: int = Field(foreign_key="fields.id", index=True)
    started_at: datetime = Field(default_factory=utcnow)
    ended_at: Optional[datetime] = None
    water_ml: Optional[float] = None
    simulated: bool = False
    result: Optional[dict] = Field(default=None, sa_column=Column(JSON))


class Cache(SQLModel, table=True):
    __tablename__ = "cache"
    key: str = Field(primary_key=True)
    data: dict = Field(default_factory=dict, sa_column=Column(JSON))
    fetched_at: datetime = Field(default_factory=utcnow)


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
