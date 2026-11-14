"""Download this week's prices from ZPIS (zpis.gov.mk, Ministry of Agriculture market information system).

ZPIS shows each product's price at every buyout centre (Откупен центар) or market that reported it.
This script asks the same ASP.NET form the website uses and writes data/prices.json:
  - the national average (the last column, "Просечна цена на РМ")
  - the price at each named place, which the app uses for "where to sell"
Nothing is estimated: a crop with no ZPIS row stays in "missing".

Run: python data/scripts/download_zpis.py
"""
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

import requests

BASE = "https://zpis.gov.mk"
OUT = Path(__file__).resolve().parents[1] / "prices.json"
PLACES = Path(__file__).resolve().parents[1] / "zpis_places.json"
UA = {"User-Agent": "Mozilla/5.0 (Niva crop-rotation app; NASA Space Apps)"}

# crop -> (price page, ZPIS product, market types to try in order, text the report row must contain)
# Market types: 1 = buyout centre (price paid to farmers), 4 = wholesale market. Crops ZPIS does not list
# (alfalfa, chickpea, sorghum, vetch + oat, mustard) are left out on purpose and end up in "missing".
WANTED = {
    "wheat":     (3, "ПЧЕНИЦА", [1], "СИТЕ СОРТИ"),
    "barley":    (3, "ЈАЧМЕН", [1], "СИТЕ СОРТИ"),
    "maize":     (3, "ПЧЕНКА", [1], "СИТЕ СОРТИ"),
    "sunflower": (4, "СОНЧОГЛЕД", [1], ""),
    "rapeseed":  (4, "МАСЛОДАЈНА РЕПКА", [1], ""),
    "tobacco":   (4, "ТУТУН", [1], ""),
    "pepper":    (2, "ИНДУСТРИСКИ ПИПЕР", [1, 4], ""),
    "tomato":    (2, "ИНДУСТРИСКИ ДОМАТ", [1, 4], ""),
    "bean":      (2, "ГРАВ", [1, 4], ""),
}
ALL_CROPS = ["wheat", "barley", "maize", "sunflower", "tobacco", "alfalfa", "pepper", "tomato", "bean",
             "chickpea", "rapeseed", "sorghum", "vetch_oat", "mustard"]
KIND = {1: "buyout", 4: "wholesale"}


def hidden(page):
    return {m.group(1): html.unescape(m.group(2)) for m in re.finditer(r'<input type="hidden" name="([^"]+)" id="[^"]*" value="([^"]*)"', page)}


def selects(page):
    out = {}
    for name, body in re.findall(r'<select name="([^"]+)"[^>]*>(.*?)</select>', page, re.S):
        out[name] = [(v, html.unescape(t).strip()) for v, t in re.findall(r'<option[^>]*value="([^"]*)"[^>]*>([^<]*)</option>', body)]
    return out


def service(s, method, known, category, context=None):
    body = {"knownCategoryValues": known, "category": category}
    if context is not None:
        body["contextKey"] = context
    r = s.post(f"{BASE}/PriceService.asmx/{method}", json=body, timeout=60)
    r.raise_for_status()
    return [(x["value"], x["name"].strip()) for x in r.json()["d"]]


def table(page):
    """Return (column headers, rows) of the report table."""
    m = re.search(r"Сорта / Раса(.*?)</table>", page, re.S)
    if not m:
        return [], []
    chunk = "<tr><td>Сорта / Раса" + m.group(1)
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", chunk, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if cells:
            rows.append(cells)
    return (rows[0], rows[1:]) if rows else ([], [])


def num(x):
    x = x.replace(".", "").replace(",", ".").strip()
    try:
        return round(float(x), 2)
    except ValueError:
        return None


def fetch(s, page_no, product_name, market_type):
    url = f"{BASE}/price/{page_no}"
    page = s.get(url, timeout=60).text
    form = hidden(page)
    cats = service(s, "GetKategorii", "", "KategorijaID", str(page_no))
    for cat_id, cat_name in cats:
        prods = service(s, "GetProdukti", f"KategorijaID:{cat_id};", "ProduktId")
        hit = next(((pid, pn) for pid, pn in prods if pn.upper().lstrip("'") == product_name), None)
        if not hit:
            continue
        markets = service(s, "GetMestoSobiranje", f"KategorijaID:{cat_id};", "Pazar")
        mk = next(((v, n) for v, n in markets if v == str(market_type)), markets[0] if markets else None)
        if not mk:
            return None
        form.update({
            "ctl00$MainContent$ddlKategorii": cat_id,
            "ctl00$MainContent$CascadingDropDown1_ClientState": f"{cat_id}:::{cat_name}:::",
            "ctl00$MainContent$ddlProdukti": hit[0],
            "ctl00$MainContent$CascadingDropDown2_ClientState": f"{hit[0]}:::{hit[1]}:::",
            "ctl00$MainContent$tbDatumPodnesuvanjeOd": "",
            "ctl00$MainContent$tbDatumPodnesuvanjeDo": "",
            "ctl00$MainContent$ddlMestoSobiranje": mk[0],
            "ctl00$MainContent$CascadingDropDown4_ClientState": f"{mk[0]}:::{mk[1]}:::",
            "ctl00$MainContent$Button1": "Барај",
        })
        res = s.post(url, data=form, timeout=90).text
        head, rows = table(res)
        return {"url": url, "market_name": mk[1], "head": head, "rows": rows}
    return None


def geocode(names):
    """Town / municipality centre for each ZPIS place, from OpenStreetMap Nominatim, cached in zpis_places.json."""
    import time
    cache = json.loads(PLACES.read_text(encoding="utf-8")) if PLACES.exists() else {
        "note": "Centre of each town / municipality that reports ZPIS prices. Source: OpenStreetMap Nominatim.", "places": {}}
    for name in sorted(names):
        if name in cache["places"]:
            continue
        r = requests.get("https://nominatim.openstreetmap.org/search", timeout=60,
                         params={"q": f"{name}, North Macedonia", "format": "json", "limit": 1, "accept-language": "mk"},
                         headers={"User-Agent": "Niva crop-rotation app (NASA Space Apps 2026)"})
        hit = (r.json() or [None])[0]
        cache["places"][name] = {"lat": round(float(hit["lat"]), 4), "lon": round(float(hit["lon"]), 4), "osm": hit["display_name"]} if hit else None
        print(f"geocoded {name}: {cache['places'][name] and cache['places'][name]['osm']}")
        time.sleep(1.1)  # Nominatim policy: at most 1 request a second
    PLACES.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def main():
    s = requests.Session()
    s.headers.update(UA)
    prices, missing = [], []
    for crop, (page_no, product, market_types, must) in WANTED.items():
        got, kind = None, None
        for mt in market_types:
            try:
                got = fetch(s, page_no, product, mt)
            except Exception as e:  # network or layout change: keep the crop empty, say why
                print(f"{crop}: error {e}", file=sys.stderr)
                got = None
            if got and got["rows"]:
                kind = KIND[mt]
                break
        if not got or not got["rows"]:
            print(f"{crop}: no ZPIS price this week")
            continue
        row = next((r for r in got["rows"] if must and must in r[0].upper()), None) or got["rows"][0]
        head = got["head"]
        places = []
        for name, val in zip(head[1:-1], row[1:-1]):
            v = num(val)
            if v is not None:
                places.append({"place": re.sub(r"^[^-]*-", "", name).strip(), "price": v})
        avg = num(row[-1]) if len(row) == len(head) else None
        if avg is None and places:
            avg = round(sum(x["price"] for x in places) / len(places), 2)
        places.sort(key=lambda x: -x["price"])
        prices.append({"crop": crop, "product": row[0], "price": avg, "market": kind,
                       "scope": f"national average, {len(places)} {'buyout centres' if kind == 'buyout' else 'markets'}",
                       "places": places, "url": got["url"]})
        print(f"{crop}: {row[0]} avg {avg} at {len(places)} places ({kind})")
    if not prices:
        sys.exit("ZPIS returned nothing: prices.json left unchanged")
    missing = [c for c in ALL_CROPS if c not in {x["crop"] for x in prices}]
    out = {
        "note": "Downloaded from ZPIS (zpis.gov.mk, Ministry of Agriculture market information system), default view = latest week "
                "published. 'retrieved' is the download date because the report does not print the week. Buyout centre "
                "(Откупен центар) = price paid to farmers. Wholesale market = higher than the farm-gate price. Crops in "
                "'missing' had no ZPIS row: left empty on purpose.",
        "currency": "MKD/kg", "retrieved": dt.date.today().isoformat(), "prices": prices, "missing": missing,
    }
    geocode({x["place"] for p in prices for x in p["places"]})
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
