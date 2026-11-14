"""Official crop area and production per region from MakStat (PxWeb API, no login), every year published.

    python data/scripts/download_production.py

Writes data/production.json: for the 7 market regions in Main_Prompt (Strumica, Pelagonija, Ovče Pole, Polog,
Tikveš, Kočani, Skopje), the sum over the region's main municipalities of sown area (ha) and production (t),
per crop and year. Used by the Market page "Produced in your region" trend.
Bought-out (sold) volumes per region are not published by MakStat or ZPIS, so they are not in this file.
"""
import json
import time
import urllib.request
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent
TABLE = ("https://makstat.stat.gov.mk/PXWeb/api/v1/en/MakStat/Zemjodelstvo/RastitelnoProizvodstvo/"
         "475_RastPr_Op_GlPosevNtes13_ml.px")
# market region -> MakStat municipality names (the region's main farming municipalities)
REGIONS = {
    "strumica": ["Strumitsa", "Novo Selo", "Bosilovo", "Vasilevo"],
    "pelagonija": ["Bitola", "Prilep", "Mogila", "Novatsi"],
    "ovche-pole": ["Sveti Nikole", "Lozovo"],
    "polog": ["Tetovo", "Gostivar", "Teartse", "Bogovinje"],
    "tikvesh": ["Kavadartsi", "Negotino", "Rosoman"],
    "kochani": ["Kochani", "Cheshinovo-Obleshevo", "Zrnovtsi"],
    "skopje": ["Petrovets", "Ilinden", "Studenichani", "Arachinovo"],
}
NAMES = {"strumica": ("Strumica valley", "Струмичко Поле"), "pelagonija": ("Pelagonija", "Пелагонија"),
         "ovche-pole": ("Ovče Pole", "Овче Поле"), "polog": ("Polog", "Полог"), "tikvesh": ("Tikveš", "Тиквеш"),
         "kochani": ("Kočani", "Кочанско Поле"), "skopje": ("Skopje area", "Скопско")}
CROPS = {
    "wheat": "Wheat", "barley": "Barley", "maize": "Maize", "sunflower": "Sunflower",
    "tobacco": "Tobacco", "bean": "Beans-single maincrop", "tomato": "Tomatoes",
    "pepper": "Peppers", "alfalfa": "Alfalfa", "vetch_oat": "Vetches-hay",
}


def get(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8-sig"))
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
            time.sleep(15 * (attempt + 1))  # MakStat rate-limits bursts
    raise RuntimeError("MakStat kept answering 429")


def main():
    meta = get(TABLE)
    var = {v["code"]: v for v in meta["variables"]}
    codes = list(var)
    mun_v, year_v, crop_v, meas_v = (var[c] for c in codes)
    print("measures:", meas_v["valueTexts"])
    known = set(mun_v["valueTexts"])
    missing = [m for ms in REGIONS.values() for m in ms if m not in known]
    if missing:
        print("not in table, skipped:", missing)
    muns = [m for ms in REGIONS.values() for m in ms if m in known]
    pick = lambda v, texts: [v["values"][v["valueTexts"].index(t)] for t in texts]
    measures = ["Sown area, ha", "Total production in tonnes"]
    query = {"query": [
        {"code": mun_v["code"], "selection": {"filter": "item", "values": pick(mun_v, muns)}},
        {"code": year_v["code"], "selection": {"filter": "item", "values": year_v["values"]}},
        {"code": crop_v["code"], "selection": {"filter": "item", "values": pick(crop_v, CROPS.values())}},
        {"code": meas_v["code"], "selection": {"filter": "item", "values": pick(meas_v, measures)}},
    ], "response": {"format": "json"}}
    res = get(TABLE, query)
    text = {c: dict(zip(var[c]["values"], var[c]["valueTexts"])) for c in codes}
    by_name = {v: k for k, v in CROPS.items()}
    region_of = {m: r for r, ms in REGIONS.items() for m in ms}
    acc: dict = {}
    for row in res["data"]:
        mun, yr, crop, meas = (text[c][k] for c, k in zip(codes, row["key"]))
        v = row["values"][0]
        if v in ("..", "-", "", None):
            continue
        key = "production_t" if "production" in meas.lower() else "area_ha"
        cell = acc.setdefault(region_of[mun], {}).setdefault(by_name[crop], {}).setdefault(yr, {})
        cell[key] = round(cell.get(key, 0) + float(v), 1)

    years = sorted({y for r in acc.values() for c in r.values() for y in c})
    out = {"source": "MakStat (State Statistical Office of North Macedonia), table 475_RastPr_Op_GlPosevNtes13",
           "url": TABLE, "measures": measures, "retrieved": date.today().isoformat(), "years": years,
           "sold_note": "Bought-out (sold) volumes per region are not published (MakStat, ZPIS). Left empty on purpose.",
           "regions": {r: {"name": NAMES[r][0], "name_mk": NAMES[r][1],
                           "municipalities": [m for m in REGIONS[r] if m in known],
                           "crops": {c: [{"year": y, **acc.get(r, {}).get(c, {}).get(y, {})}
                                         for y in years if acc.get(r, {}).get(c, {}).get(y)]
                                     for c in CROPS}}
                       for r in REGIONS}}
    (DATA / "production.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for r, d in out["regions"].items():
        print(r, {c: len(v) for c, v in d["crops"].items()})


if __name__ == "__main__":
    main()
