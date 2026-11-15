# Niva

An ESP32 field system that measures soil and air on a field and posts the readings to a small server.

```
firmware/niva_sensor/   the ESP32 sketch (Arduino)
backend/                the API the ESP32 posts to (FastAPI + SQLite)
deploy/                 one-time server setup (systemd service + Caddy for HTTPS)
brand/                  logo and team photo
```

## What the field system measures

| Value          | JSON key       | Sensor              |
|----------------|----------------|---------------------|
| Soil moisture  | `soil_pct`     | capacitive probe    |
| Soil temperature | `soil_temp_c` | DS18B20            |
| Air temperature | `air_temp_c`  | DHT / BME280        |
| Air humidity   | `humidity_pct` | DHT / BME280        |
| Air pressure   | `pressure_hpa` | BME280 / BMP280     |

A sensor that is missing or fails sends `null`, never a wrong number.
Pins, timing and the server address are in `firmware/niva_sensor/config.h`; the sketch header lists the board
settings and libraries.

## Firmware

1. Copy `secrets.example.h` to `secrets.h` and put in the device key (see "Add a device" below).
2. Open `niva_sensor.ino` in the Arduino IDE, board "ESP32 Dev Module", partition scheme "Huge APP".
3. Upload. With no saved WiFi the board opens the `Niva-Setup` network: join it on a phone and pick the WiFi.

Without `secrets.h` the board still prints every reading as one JSON line over USB; it just does not post.

## Backend

```bash
python -m venv .venv
.venv/Scripts/pip install -r backend/requirements.txt    # Linux/macOS: .venv/bin/pip
cd backend
../.venv/Scripts/uvicorn main:app --reload
```

The database is `niva.db` next to `backend/` (override with `NIVA_DB`).

| Method | Path                         | Who calls it | What it does |
|--------|------------------------------|--------------|--------------|
| GET    | `/health`                    | anyone       | is the server up |
| POST   | `/readings`                  | the ESP32    | store one reading (`X-Device-Id`, `X-Device-Key` headers) |
| POST   | `/fields`                    | you          | create a field, returns its owner token once |
| GET    | `/fields/{id}`               | anyone       | name and place of a field |
| POST   | `/devices/pair`              | you          | link a device to a field (`X-Owner-Token` header) |
| GET    | `/fields/{id}/live`          | anyone       | newest reading and when each device was last heard from |
| GET    | `/fields/{id}/history?days=7`| anyone       | readings over time, thinned to about 500 points |

### Add a device

Run on the server, inside `backend/`:

```bash
python manage.py add-device NIVA-A1F3                      # prints the device key once: put it in secrets.h
python manage.py add-field "Field by the river" 41.44 22.64
python manage.py pair NIVA-A1F3 1                          # device -> field 1
python manage.py devices                                   # check last_seen
```

## Deploy

`deploy/setup.sh` sets up a fresh Ubuntu server: Python, a venv in `/opt/niva`, the `niva-api` systemd service
and Caddy for HTTPS. To update a running server, copy `backend/` to `/opt/niva/backend`, reinstall
`requirements.txt` and restart `niva-api`.
