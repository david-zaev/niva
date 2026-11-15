# Niva: crop rotations for your field, from NASA data and your own soil sensor

NASA Space Apps challenge: help farmers explore crop-rotation options that improve soil health and strengthen
resilience to changing weather and water conditions. Compare at least three rotations, including the current one,
and for each say why it was suggested, the evidence, the benefits, the information gaps and the risks.

**Demo farm:** Murtino, Strumica valley, south-east North Macedonia (41.414 N, 22.727 E).

**Pitch line:** NASA shows 25 years of the weather at Murtino. Our ESP32 shows how this field's soil handles that
weather. Together they pick the rotation, protect the crops this season, and learn for the next one.

## The screen (top to bottom)

1. **Soil health card (ESP32 only).** A verdict, Healthy / Needs attention / Poor, with "Read more" opening
   every check behind it: water for the roots, air in the soil (hours saturated), soil temperature against the
   NASA normal for the date, soil protection (daily temperature swing: bare vs covered), how fast the soil dries,
   and, after a soil test (pour water next to the probe), how fast rain soaks in. Live alerts (water, frost, storm
   from falling pressure, heat, disease weather) sit under it. The sensor never changes the rotation plans.
2. **Map.** Satellite map of the farm. In the demo the Murtino farm and its fields are already drawn and the first
   field is selected. Tap another field to select it, or draw a new one (area is computed).
3. **Crop rotation plans for the selected field, from data about the place only:**
   - NASA POWER daily 2001 to now: temperature, humidity, pressure, wind, sun, rain, soil wetness and soil
     temperature. Crop water demand (ET0) by FAO-56 Penman-Monteith.
   - NASADEM / SRTM 30 m: elevation and slope over the field outline (erosion factor).
   - ISRIC SoilGrids 250 m: sand, clay, organic matter, pH → texture, water holding (Saxton & Rawls), runoff
     group. This is the global stand-in for the soil surveys the challenge lists (WSS/SSURGO cover only the US).
   - MODIS MOD13Q1 NDVI 250 m: bare periods, past crop pattern, stressed summers.
   - NASA SMAP 9 km: checks that the simulated soil water rises and falls with the satellite's.
   - Market: ZPIS prices and MakStat yields for Strumica.
   The simulator replays each rotation through every season since 2001 (FAO-56 daily soil water balance) and
   scores water, soil health, resilience and income. At least three rotations are shown next to the current one,
   each with why it is suggested, evidence (dataset named), benefits, information gaps and risks.
4. **Evidence and farm plan** under the cards: climate profile (rain vs crop demand by month, frost dates, heat
   days trend, driest summers), NDVI history, and the whole farm (water by month, plant families per season,
   neighbouring fields, income spread).

## What is built where

| Part | Files |
|---|---|
| NASA POWER fetch + cache per POWER grid cell | `backend/power.py` → `data/cache/power/*.csv` |
| MODIS NDVI over a field + bare/stress periods | `backend/ndvi.py` |
| SMAP check | `backend/smap.py` (existing grid in `data/smap/`) |
| Slope + erosion factor | `backend/terrain.py` (existing, NASADEM tiles in `data/dem/`) |
| Crop parameters (FAO-56 Kc, stages, roots, p, Ky, families, frost/heat limits) | `data/rotation/crops.json` |
| Rotation library for the Strumica valley | `data/rotation/rotations.json` |
| Soil from SoilGrids, texture and water holding | `backend/soil.py` |
| Climate profile | `backend/climate.py` |
| Simulator + scoring + cards | `backend/simulate.py`, `backend/rotations.py` |
| Soil health card, soil test, alerts | `backend/health.py`, `backend/sensor.py` |
| API | `backend/main.py` (new) |
| Demo farm seed (Murtino fields, cached data) | `backend/seed.py` |
| Web app | `web/src/` (map + field + farm screens) |
| Firmware | optional second soil probe (bare vs covered pot demo) |

The previous app is kept in `backend/legacy/` and `docs/archive/` for reference. It is not used.

## Demo (about 3 minutes)

1. Open the app: the Murtino demo farm is there with three fields (data already cached, works without wifi).
2. Draw a new field live. Area appears; it shares Murtino's NASA grid cell, so its rotations appear at once.
3. Field by the river: climate profile, NDVI bare periods, three or more rotations with cards.
4. Soil health card: open "Read more", pour water on the pot (soil test), watch the infiltration check appear.
5. Live alerts from the sensor.
6. Farm view: water by month, pest-family and income warnings.

## Honest limits (shown in the app as information gaps)

- One probe measures one spot. A pot test is not a field survey: on a farm the test is done in the field.
- SoilGrids is a 250 m model of soil, not a sample: a lab test confirms texture, organic matter and pH.
- The sensor measures the water side of soil health. Organic matter, nutrients, pH and soil life are not measured.
- NASA POWER is about 50 km, SMAP 9 km, MODIS NDVI 250 m: a small field is one or two MODIS pixels.
- Crop parameters are FAO-56 / FAO-33 table values, not calibrated for Macedonian varieties.
- Prices and yields are rough and must be checked with local buyers.
- Live alerts give hours of warning, not a forecast. They cannot tell hail from rain.

## Next steps after the hackathon

GPM IMERG daily rain (GES DISC subsetting), Sentinel-2 10 m NDVI, ECOSTRESS evapotranspiration, GRACE groundwater
trend, multiple sensors per farm, Macedonian translation.
