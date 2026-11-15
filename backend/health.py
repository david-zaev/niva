"""Soil health card: what the ESP32 measures in the field right now, as a verdict (Healthy / Needs attention /
Poor) with the reasons behind it. Uses sensor data only; NASA appears just as the "normal for this date" yardstick."""
from datetime import timedelta

import numpy as np
import pandas as pd

import soil as soilmod


def _item(id_, title, status, value, text, why):
    return {"id": id_, "title": title, "status": status, "value": value, "text": text, "why": why}


def health(df: pd.DataFrame, long: pd.DataFrame, soil: dict, crop: dict | None, weather: pd.DataFrame,
           test: dict | None) -> dict:
    src = df if not df.empty else long
    if src.empty or "soil_pct" not in src or src["soil_pct"].dropna().empty:
        return {"status": "none", "label": "No sensor data",
                "summary": "Connect the ESP32 to see the health of this field's soil.", "items": []}
    items = []
    last_t = src.index[-1]
    fc, wp = soil["fc"], soil["wp"]
    sp = float(src["soil_pct"].dropna().iloc[-1])
    th = soilmod.theta(sp)
    avail = (th - wp) / (fc - wp)
    p = crop["p"] if crop else 0.5
    crop_name = crop["name"].lower() if crop else "a typical crop"

    # 1. water available to roots
    if avail > 1.1:
        st, txt = "watch", "Wetter than the soil can hold: water is still draining or standing."
    elif avail >= 1 - p + 0.1:
        st, txt = "good", "Roots can take up water easily."
    elif avail >= 1 - p:
        st, txt = "watch", "Getting dry: close to the point where plants start to suffer."
    else:
        st, txt = "poor", "Too dry: plants are under water stress."
    items.append(_item(
        "water", "Water for the roots", st, f"{max(0, round(100 * min(avail, 1.3)))}% of available water", txt,
        f"Sensor reads {sp:.0f}% (about {th:.2f} m³/m³). This soil holds plant water between {wp:.2f} (wilting "
        f"point) and {fc:.2f} m³/m³ (field capacity); {crop_name} is stressed below {round(100 * (1 - p))}% of that "
        f"range (FAO-56)."))

    # 2. air in the soil: hours saturated in the last day
    base = long if not long.empty else src
    l24 = base[base.index >= last_t - timedelta(hours=24)]
    s24 = l24["soil_pct"].dropna()
    span = (s24.index[-1] - s24.index[0]).total_seconds() / 3600 if len(s24) > 1 else 0
    if len(s24) > 3 and span >= 1:
        sat = np.array([(soilmod.theta(v) - wp) / (fc - wp) > 1.15 for v in s24])
        hrs = float(sat.mean()) * min(24.0, span)
        st = "good" if hrs < 3 else "watch" if hrs < 12 else "poor"
        items.append(_item(
            "air", "Air in the soil", st, f"{hrs:.0f} h saturated" + (" in 24 h" if span >= 20 else f" in {span:.0f} h"),
            "Drains well: roots and soil life get air." if st == "good"
            else "Saturated for hours: roots and soil life lack oxygen, nitrogen is lost.",
            "Soil above field capacity is waterlogged. More than about 12 hours a day damages roots and points to "
            "compaction or poor drainage."))

    # 3. soil temperature against the NASA normal for the date
    stc = src["soil_temp_c"].dropna() if "soil_temp_c" in src else pd.Series(dtype=float)
    if not stc.empty:
        t = float(stc.iloc[-1])
        doy = last_t.dayofyear
        win = weather[(abs(weather.index.dayofyear - doy) <= 7)]["soil_t"].dropna()
        normal = float(win.mean()) if len(win) else None
        if t > 35:
            st, txt = "poor", "Too hot: soil life and roots are stressed near the surface."
        elif t < 2:
            st, txt = "watch", "Near freezing: soil life is dormant."
        elif normal is not None and abs(t - normal) > 6:
            st, txt = "watch", "Far from normal for this time of year."
        else:
            st, txt = "good", ("Normal for the season: soil life is active." if t >= 8
                               else "Cool, as usual for the season: soil life is slow.")
        items.append(_item(
            "temp", "Soil temperature", st, f"{t:.1f} °C", txt,
            "Measured by the DS18B20 probe in the soil"
            + (f"; the NASA POWER 0-10 cm soil temperature for this date averages {normal:.1f} °C (2001-now)."
               if normal is not None else ".")))

    # 4. daily temperature swing: bare soil heats and cools hard, covered soil is buffered
    if len(stc) > 10:
        local = stc.tz_convert("Europe/Skopje")
        full = [s.max() - s.min() for _, s in local.groupby(local.index.date)
                if (s.index[-1] - s.index[0]).total_seconds() >= 18 * 3600]
        if full:
            swing = float(np.mean(full[-3:]))
            st = "good" if swing < 8 else "watch" if swing < 15 else "poor"
            items.append(_item(
                "cover", "Soil protection", st, f"{swing:.0f} °C daily swing",
                "Well buffered: covered or moist soil." if st == "good"
                else "Large daily swings: the soil surface is bare and exposed.",
                "Bare soil heats up by day and cools at night much more than soil under a crop, mulch or cover crop. "
                "Big swings dry the soil and slow soil life."))

    # 5. how well the soil keeps water: drying speed over the last 12-24 h
    if len(s24) > 10 and span >= 12:
        hrs = (s24.index - s24.index[0]).total_seconds() / 3600
        k = float(np.polyfit(hrs, s24.to_numpy(), 1)[0]) * 24
        if k <= 0:
            st = "good" if k > -6 else "watch" if k > -12 else "poor"
            items.append(_item(
                "holding", "Keeps water", st, f"{abs(k):.0f} points drier per day",
                "Keeps water well between rains." if st == "good"
                else "Loses water fast: low organic matter or a bare surface.",
                "The fall in soil moisture over the last day shows how fast water leaves the root zone. Soils rich "
                "in organic matter, and covered soils, lose it more slowly."))

    # 6. infiltration and drainage from the latest soil test
    if test and test.get("ok"):
        inf = test["soil"].get("infiltration")
        st = {"fast": "good", "moderate": "good", "slow": "poor"}.get(inf, "watch")
        items.append(_item(
            "infiltration", "Rain soaks in", st,
            f"{test['soak_in_s']} s to soak in" if test.get("soak_in_s") is not None else (inf or "-"),
            {"fast": "Water soaks in fast: little runoff.", "moderate": "Water soaks in well.",
             "slow": "Water soaks in slowly: rain runs off, the soil may be compacted."}.get(inf, "Not clear yet."),
            ("From a simulated soil test (no sensor): " if test.get("simulated") else "From the soil test: ")
            + f"moisture rose {test['rise_pct']} points after the water was poured"
            + (f" and drained {test['drain_pct_per_h']}% per hour" if test.get("drain_pct_per_h") is not None else "")
            + f"; the soil behaves like {test['soil']['name'].lower()}."))

    poor = sum(i["status"] == "poor" for i in items)
    watch = sum(i["status"] == "watch" for i in items)
    if poor >= 2:
        status, label = "poor", "Poor"
    elif poor or watch >= 2:
        status, label = "attention", "Needs attention"
    else:
        status, label = "healthy", "Healthy"
    good = [i["title"].lower() for i in items if i["status"] == "good"]
    bad = [i for i in items if i["status"] != "good"]
    summary = ("All checks look good: " + ", ".join(good) + ".") if not bad else \
        " ".join(f"{i['title']}: {i['text'].split(':')[0].rstrip('.').lower()}." for i in bad)
    return {"status": status, "label": label, "summary": summary, "items": items,
            "updated": last_t.isoformat(), "soil_basis": soil.get("label")}
