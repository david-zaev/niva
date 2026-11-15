"""Niva database tables (SQLite via SQLModel): fields, the ESP32 devices on them, and their readings."""
import hashlib
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlmodel import Field, SQLModel, create_engine

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
    """A place a field system stands on. The owner token is what lets someone pair a device to it."""
    __tablename__ = "fields"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    lat: float
    lon: float
    owner_token: str = Field(default_factory=new_token, index=True)


class Device(SQLModel, table=True):
    """One ESP32 field system. The server keeps only the hash of its key."""
    __tablename__ = "devices"
    id: str = Field(primary_key=True)  # NIVA-A1F3
    key_hash: str
    pair_code: str
    field_id: Optional[int] = Field(default=None, foreign_key="fields.id")
    last_seen: Optional[datetime] = None


class Reading(SQLModel, table=True):
    """One measurement from a device. A sensor that is missing or failed sends null."""
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


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
