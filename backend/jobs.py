"""Daily job (DESIGN.md "jobs.py"): every morning at 06:00 Skopje time, for each field:
fetch the last 50 days of NASA POWER and ERA5-Land top-soil moisture at the field's own point, save them to
climate_daily, run the soil forecast and save it to forecasts. Also runs once at start-up if today's forecast
is missing, so a fresh server is never empty.
"""
import logging
import threading
import csv
import json
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlmodel import Session, delete, select

import forecast
import nasa
import climate_data
from models import ClimateDaily, FieldRow, Forecast, engine

log = logging.getLogger("niva.jobs")
DAYS_BACK = 50  # the inputs reach 30 days back, plus the 3-6 days both sources run late
POWER = "https://power.larc.nasa.gov/api/temporal/daily/point"
PARAMS = {"T2M_MAX": "t_max", "T2M_MIN": "t_min", "PRECTOTCORR": "rain_mm", "RH2M": "humidity",
          "ALLSKY_SFC_SW_DWN": "solar", "WS2M": "wind", "TOA_SW_DWN": "ra"}
SOIL = "https://archive-api.open-meteo.com/v1/archive"


def hargreaves_et0(t_max, t_min, ra):
    """FAO-56 Hargreaves, mm/day: the same formula as data/scripts/download_power.py."""
    if None in (t_max, t_min, ra) or t_max < t_min:
        return None
    return round(0.0023 * 0.408 * ra * ((t_max + t_min) / 2 + 17.8) * (t_max - t_min) ** 0.5, 2)


def fetch_power(lat, lon, start: date, end: date) -> dict[date, dict]:
    r = httpx.get(POWER, timeout=120, params={
        "parameters": ",".join(PARAMS), "community": "AG", "latitude": lat, "longitude": lon,
        "start": start.strftime("%Y%m%d"), "end": end.strftime("%Y%m%d"), "format": "JSON"})
    r.raise_for_status()
    p = r.json()["properties"]["parameter"]
    out = {}
    for d in p["T2M_MAX"]:
        row = {col: (None if p[k].get(d) in (None, -999.0) else p[k][d]) for k, col in PARAMS.items()}
        if row["t_max"] is None and row["rain_mm"] is None:
            continue  # not published yet
        row["et0"] = hargreaves_et0(row["t_max"], row["t_min"], row.pop("ra"))
        out[date(int(d[:4]), int(d[4:6]), int(d[6:]))] = row
    return out


def fetch_soil(lat, lon, start: date, end: date) -> dict[date, float]:
    r = httpx.get(SOIL, timeout=60, params={
        "latitude": lat, "longitude": lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
        "hourly": "soil_moisture_0_to_7cm", "models": "era5_land", "timezone": "Europe/Skopje"})
    r.raise_for_status()
    h = r.json()["hourly"]
    days: dict[str, list] = {}
    for t, v in zip(h["time"], h["soil_moisture_0_to_7cm"]):
        if v is not None:
            days.setdefault(t[:10], []).append(v)
    return {date.fromisoformat(d): sum(v) / 24 for d, v in days.items() if len(v) == 24}  # full days only


def refresh_climate(loc: dict, today: date) -> None:
    """Refresh the regional history and climate charts, including late solar data."""
    folder = nasa.DATA_DIR / 'locations' / loc['id']
    path = folder / 'power.csv'
    with path.open(encoding='utf-8', newline='') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames
        saved = {row['date']: row for row in reader}
    start = date.fromisoformat(max(saved)) - timedelta(days=14)
    updates = fetch_power(loc['lat'], loc['lon'], start, today - timedelta(days=1))
    for day, values in updates.items():
        key = day.isoformat()
        row = saved.setdefault(key, {'date': key})
        row.update({k: v for k, v in values.items() if v is not None})
    temporary = path.with_suffix('.csv.tmp')
    with temporary.open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(saved[key] for key in sorted(saved))
    temporary.replace(path)
    meta_path = folder / 'power_meta.json'
    meta = json.loads(meta_path.read_text(encoding='utf-8'))
    meta.update(last_date=max(saved), days=len(saved),
                downloaded_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
                request_url=f'{POWER}?parameters={",".join(PARAMS)}&community=AG&latitude={loc["lat"]}'
                            f'&longitude={loc["lon"]}&start={start:%Y%m%d}&end={today - timedelta(days=1):%Y%m%d}&format=JSON')
    climate_data.write_json(meta_path, meta)
    climate_data.compute_location(loc)


def run_field(s: Session, f: FieldRow, today: date) -> int:
    import pandas as pd
    start, end = today - timedelta(days=DAYS_BACK), today - timedelta(days=1)
    power, soil = fetch_power(f.lat, f.lon, start, end), fetch_soil(f.lat, f.lon, start, end)
    for d, row in power.items():
        s.merge(ClimateDaily(field_id=f.id, date=d, sm=soil.get(d), **row))
    s.commit()

    rows = s.exec(select(ClimateDaily).where(ClimateDaily.field_id == f.id, ClimateDaily.date >= start)
                  .order_by(ClimateDaily.date)).all()
    df = pd.DataFrame([r.model_dump() for r in rows]).drop(columns="field_id")
    df.index = pd.to_datetime(df.pop("date"))
    loc, _, _ = nasa.location_for(f.lat, f.lon, f.region)
    out = forecast.predict(loc["id"], forecast.build_frame(df))
    if out is None:
        log.warning("field %s: no model or not enough data", f.id)
        return 0
    s.exec(delete(Forecast).where(Forecast.field_id == f.id, Forecast.made_at == today))
    anchor = out["anchor"]
    s.add(Forecast(field_id=f.id, made_at=today, day=anchor, soil_moisture=out["sm"], low=out["sm"], high=out["sm"]))
    for d in out["days"]:
        s.add(Forecast(field_id=f.id, made_at=today, day=anchor + timedelta(days=d["h"]),
                       soil_moisture=d["sm"], low=d["low"], high=d["high"]))
    s.commit()
    return len(out["days"])


def run_all() -> None:
    today = date.today()
    for loc in nasa.locations():
        try:
            refresh_climate(loc, today)
        except Exception:
            log.exception('location %s: climate refresh failed; keeping saved data', loc['id'])
    with Session(engine) as s:
        for f in s.exec(select(FieldRow)).all():
            try:
                n = run_field(s, f, today)
                log.info("field %s: forecast %s days", f.id, n)
            except Exception:
                s.rollback()
                log.exception("field %s: daily job failed", f.id)


def run_one(field_id: int) -> None:
    """First forecast for a field just created in the app (runs after the answer is sent)."""
    with Session(engine) as s:
        f = s.get(FieldRow, field_id)
        if f:
            try:
                run_field(s, f, date.today())
            except Exception:
                log.exception("field %s: first forecast failed", field_id)


def start() -> object | None:
    """Start the scheduler (one uvicorn worker, so exactly one copy runs)."""
    from apscheduler.schedulers.background import BackgroundScheduler
    sched = BackgroundScheduler(timezone="Europe/Skopje")
    sched.add_job(run_all, "cron", hour=6, minute=0, id="daily", coalesce=True, misfire_grace_time=3600)
    sched.start()
    with Session(engine) as s:  # any field without today's forecast (new server, new field, missed 06:00)?
        done = set(s.exec(select(Forecast.field_id).where(Forecast.made_at == date.today())).all())
        fields = set(s.exec(select(FieldRow.id)).all())
        climate_stale = any(((nasa.indicators(loc['id']) or {}).get('updated_at') or '')[:10] != date.today().isoformat()
                            for loc in nasa.locations())
        if fields - done or climate_stale:
            threading.Thread(target=run_all, daemon=True).start()
    return sched
