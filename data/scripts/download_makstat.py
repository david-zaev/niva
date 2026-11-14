"""Official crop yields per municipality from MakStat (State Statistical Office, PxWeb API, no login).

    python data/scripts/download_makstat.py

Writes data/yields.json: yield in kg/ha for each demo location's municipality, last 3 years with data.
Table: "Area and production of crops, by municipalities, by years" (475_RastPr_Op_GlPosevNtes13_ml.px).
"""
import json
import urllib.request
from datetime import date
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent
TABLE = ("https://makstat.stat.gov.mk/PXWeb/api/v1/en/MakStat/Zemjodelstvo/RastitelnoProizvodstvo/"
         "475_RastPr_Op_GlPosevNtes13_ml.px")
# demo location -> MakStat municipality name
MUNICIPALITY = {"strumica": "Strumitsa", "ovche-pole": "Sveti Nikole", "pelagonija": "Bitola"}
# Niva crop id -> MakStat crop name
CROPS = {
    "wheat": "Wheat", "barley": "Barley", "maize": "Maize", "sunflower": "Sunflower",
    "tobacco": "Tobacco", "bean": "Beans-single maincrop", "tomato": "Tomatoes",
    "pepper": "Peppers", "alfalfa": "Alfalfa", "vetch_oat": "Vetches-hay",
}


def get(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8-sig"))


def main():
    meta = get(TABLE)
    var = {v["code"]: v for v in meta["variables"]}
    codes = list(var)  # municipality, year, crop, measure (names are Macedonian)
    mun_v, year_v, crop_v, meas_v = (var[c] for c in codes)
    pick = lambda v, texts: [v["values"][v["valueTexts"].index(t)] for t in texts]
    years = year_v["values"]
    query = {"query": [
        {"code": mun_v["code"], "selection": {"filter": "item", "values": pick(mun_v, MUNICIPALITY.values())}},
        {"code": year_v["code"], "selection": {"filter": "item", "values": years}},
        {"code": crop_v["code"], "selection": {"filter": "item", "values": pick(crop_v, CROPS.values())}},
        {"code": meas_v["code"], "selection": {"filter": "item", "values": pick(meas_v, ["Yield kg/ha"])}},
    ], "response": {"format": "json"}}
    res = get(TABLE, query)

    text = {c: dict(zip(var[c]["values"], var[c]["valueTexts"])) for c in codes}
    raw = {}
    for row in res["data"]:
        mun, yr, crop, _ = row["key"]
        v = row["values"][0]
        if v in ("..", "-", "", None) or float(v) == 0:
            continue
        raw.setdefault(text[mun_v["code"]][mun], {}).setdefault(text[crop_v["code"]][crop], {})[text[year_v["code"]][yr]] = float(v)

    out = {"source": "MakStat (State Statistical Office of North Macedonia), table 475_RastPr_Op_GlPosevNtes13",
           "url": TABLE, "unit": "kg/ha", "retrieved": date.today().isoformat(), "locations": {}}
    for loc, mun in MUNICIPALITY.items():
        out["locations"][loc] = {"municipality": mun, "crops": {}}
        for cid, name in CROPS.items():
            series = raw.get(mun, {}).get(name, {})
            last3 = sorted(series)[-3:]
            out["locations"][loc]["crops"][cid] = None if not last3 else {
                "yield_kg_ha": round(sum(series[y] for y in last3) / len(last3)),
                "years": f"{last3[0]}-{last3[-1]}",
            }
    (DATA / "yields.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    for loc, d in out["locations"].items():
        print(loc, {k: (v and v["yield_kg_ha"]) for k, v in d["crops"].items()})


if __name__ == "__main__":
    main()
