# TECHNICAL SPECIFICATION: North Macedonia Agricultural Markets, Prices & Buyers Data Sources
**Target Agent:** Claude Code  
**Purpose:** Reference guide for scraping, fetching, and parsing agricultural commodity prices, wholesale/retail markets, and registered corporate buyers in North Macedonia (MK).  
**Currency:** `MKD` (Македонски денар / Denar) — Fixed peg: `1 EUR ≈ 61.50 MKD`  
**Primary Language of Sources:** Macedonian (Cyrillic `mk-MK`, UTF-8 encoding required).

---

## 1. OFFICIAL GOVERNMENT PRICE & MARKET PORTALS

### 1.1 ZPIS (Земјоделски пазарен информативен систем / Agricultural Market Information System)
The primary source for weekly wholesale (*Големопродажни / Кванташки*) and retail green market (*Малопродажни / Зелени пазари*) prices across Macedonian cities.

* **Base URL:** `https://zpis.gov.mk`
* **Direct Category Price Endpoints (HTML Tables / Dynamic Views):**
  * Livestock & Meat (*Жив добиток и месо*): `https://zpis.gov.mk/price/1`
  * Fruit & Vegetables (*Овошје и зеленчук*): `https://zpis.gov.mk/price/2`
  * Animal Feed & Grains (*Добиточна храна и житарки*): `https://zpis.gov.mk/price/3`
  * Tobacco & Oilseeds (*Тутун и маслодајни култури*): `https://zpis.gov.mk/price/4`
  * Agricultural Inputs - Seeds, Fertilizers, Pesticides (*Земјоделски репроматеријали / Внесови*): `https://zpis.gov.mk/price/5`
* **Bulletins & Reports (PDF/XLS Weekly & Monthly Summaries):** `https://zpis.gov.mk/Bilteni_Izvestai`
* **Annual & Seasonal Documents:** `https://zpis.gov.mk/Documents/1`
* **Supply & Demand Board (*Понуда и побарувачка*):** `https://zpis.gov.mk/Ponuda_Pobaruvacka`
* **Monitored Market Locations in ZPIS Data:**
  * `Скопје` (Skopje), `Битола` (Bitola), `Струмица` (Strumica), `Штип` (Štip), `Тетово` (Tetovo), `Куманово` (Kumanovo), `Прилеп` (Prilep), `Охрид` (Ohrid), `Велес` (Veles), `Кавадарци` (Kavadarci), `Кочани` (Kočani), `Ресен` (Resen).

---

### 1.2 MakStat (Државен завод за статистика / State Statistical Office - PxWeb API)
Provides machine-readable official monthly/annual buyout prices (*Откупни цени*), producer price indices, and input prices via the standard **PxWeb REST API v1**.

* **Interactive Web Root (MK):** `https://makstat.stat.gov.mk/PXWeb/pxweb/mk/MakStat/`
* **Interactive Web Root (EN):** `https://makstat.stat.gov.mk/PXWeb/pxweb/en/MakStat/`
* **Agriculture Database Path:** `https://makstat.stat.gov.mk/PXWeb/pxweb/mk/MakStat/MakStat__Zemjodelstvo/`
* **Prices Database Path (Includes Agri Input/Output Indices):** `https://makstat.stat.gov.mk/PXWeb/pxweb/mk/MakStat/MakStat__Ceni/`
* **PxWeb REST API Base Endpoint (JSON-stat / CSV / XLSX):**
  * `https://makstat.stat.gov.mk/PXWeb/api/v1/mk/MakStat/` (Macedonian)
  * `https://makstat.stat.gov.mk/PXWeb/api/v1/en/MakStat/` (English)
* **How Claude Code Should Query MakStat API:**
  1. Perform a `GET` request to `https://makstat.stat.gov.mk/PXWeb/api/v1/en/MakStat` to list top-level database IDs.
  2. Traverse into `MakStat__Ceni` (Prices) or `MakStat__Zemjodelstvo` (Agriculture) via `GET`.
  3. Issue a `POST` request with a JSON query payload to the specific `.px` table URL to receive JSON-stat or CSV data for agricultural producer prices (*Цени во земјоделството*).

---

### 1.3 Registered Buyers & State Tenders (Ministry of Agriculture & Open Data)
In North Macedonia, companies buying from farmers must be listed in the official Register of Buyers (*Регистар на откупувачи на земјоделски производи*).

* **Ministry of Agriculture (MZŠV) Official Registers Page:**
  * `https://www.mzsv.gov.mk/mk-MK/dokumenti-i-informacii-od-javen-karakter/registri`
  * Contains downloadable `.xlsx` / `.pdf` lists of licensed buyout companies categorized by:
    1. Fruit & Vegetables (*Овошје и зеленчук*)
    2. Wine Grapes & Wine (*Грозје и вино*)
    3. Grains & Oilseeds (*Жита и маслодајни семиња*)
    4. Raw Milk, Livestock & Honey (*Сурово млеко, жив добиток и мед*)
    5. Tobacco (*Тутун*)
* **National Open Data Portal (CKAN API Enabled):**
  * Dataset URL: `https://data.gov.mk/mk/dataset/pernctap-ha-otkynybahn-ha-3emjodejickn-npon3bodn`
  * CKAN API Base: `https://data.gov.mk/api/3/action/package_search?q=земјоделски`
* **Agency for Financial Support in Agriculture and Rural Development (IPARD & Subsidies / Платежна агенција):**
  * `https://ipardpa.gov.mk` (Tracks subsidy rates per kg/hectare delivered to registered buyers).
* **State Commodity Reserves (*Агенција за стоковни резерви*):**
  * Public procurement announcements for state wheat/barley buyouts are published on the Electronic System for Public Procurements (ESJN): `https://e-nabavki.gov.mk`

---

## 2. AGRO-MEDIA PORTALS (DAILY WHOLESALE & SEASONAL BUYOUT PRICES)
Official government portals lag by 7–30 days. For near-real-time wholesale (*Кванташки*) and processor buyout (*Откупни*) rates, scrape or search these news portals:

1. **Agrotim.mk**
   * **Base URL:** `https://agrotim.mk`
   * **WP REST API Endpoint (JSON):** `https://agrotim.mk/wp-json/wp/v2/posts?search=цени` (or `?search=откуп`, `?search=кванташки`)
   * **Data Value:** Publishes daily/weekly price tables from the Skopje and Strumica wholesale markets and processor buyout prices for wheat, peppers, tomatoes, cabbage, and grapes.
2. **Zelena Berza (Зелена Берза)**
   * **Base URL:** `https://zelenaberza.com.mk`
   * **WP REST API Endpoint (JSON):** `https://zelenaberza.com.mk/wp-json/wp/v2/posts?search=цени`
   * **Data Value:** Strong focus on Bitola/Pelagonija grains, dairy, tobacco buyout prices by class, and Tikveš grape buyout rates.
3. **Agri.mk**
   * **Base URL:** `https://agri.mk`
   * **Data Value:** Market analyses, livestock prices, and regional crop updates.

---

## 3. CYRILLIC KEYWORD DICTIONARY FOR SEARCHING & PARSING
When building scrapers, search queries, or regex parsers for Macedonian agricultural data, use the exact Cyrillic terms below:

### 3.1 Market & Price Types
| English Term | Macedonian Cyrillic | Transliteration / Root |
| :--- | :--- | :--- |
| **Buyout / Farm-gate Price** | `Откупна цена` / `Откупни цени` | Otkupna cena |
| **Wholesale Price** | `Големопродажна цена` | Golemoprodažna cena |
| **Wholesale Market** | `Кванташки пазар` | Kvantaški pazar |
| **Retail / Green Market Price** | `Малопродажна цена` / `Зелен пазар` | Maloprodažna cena / Zelen pazar |
| **Registered Buyer / Center** | `Откупувач` / `Откупен центар` | Otkupuvač / Otkupen centar |
| **Processing Factory** | `Преработувачки капацитет` | Prerabotuvački kapacitet |
| **Price per kilogram** | `ден/кг` or `МКД/кг` | den/kg |

### 3.2 Core Crops & Commodities
| English Crop Name | Macedonian Cyrillic (Singular / Plural) | Primary Production & Buyout Hub |
| :--- | :--- | :--- |
| **Wheat** | `Пченица` | Pelagonija (Bitola/Prilep), Ovče Pole, Kumanovo |
| **Barley** | `Јачмен` | Pelagonija, Štip, Veles |
| **Corn / Maize** | `Пченка` | Pelagonija, Polog (Tetovo/Gostivar), Skopje |
| **Rice (Paddy / White)** | `Ориз` (`Арпа` / `Бел ориз`) | Kočani, Vinica, Češinovo-Obleševo |
| **Sunflower** | `Сончоглед` | Pelagonija, Ovče Pole |
| **Tobacco** | `Тутун` | Prilep, Bitola, Kruševo, Radoviš, Strumica |
| **Tomatoes** | `Домати` (`Патлиџани`) | Strumica, Gevgelija, Bogdanci, Valandovo |
| **Peppers (Industrial / Ajvar)** | `Пиперки` (`Ајварка` / `Куртовска капија`) | Strumica, Prilep, Krivogaštani, Demir Hisar |
| **Cabbage (Early Spring)** | `Зелка` (`Рана пролетна зелка`) | Strumica, Novo Selo, Bosilovo |
| **Potatoes** | `Компир` | Berovo, Kriva Palanka, Tetovo (Polog) |
| **Apples** | `Јаболка` (`Ајдаред`, `Златен делишес`, `Муцу`) | Resen (Prespa region) |
| **Peaches** | `Праски` | Rosoman, Kavadarci, Gradsko |
| **Table & Wine Grapes** | `Трпезно грозје` / `Винско грозје` (`Вранец`, `Смедеревка`) | Kavadarci, Negotino, Demir Kapija, Valandovo |
| **Sour Cherries** | `Вишни` | Makedonski Brod, Karbinci, Bitola |
| **Raw Milk (Cow/Sheep/Goat)** | `Сурово млеко` (`Кравјо`, `Овчо`, `Козјо`) | Bitola, Tetovo, Kumanovo, Berovo |

---

## 4. KEY PHYSICAL MARKETS & BUYER ENTITIES (STATIC REFERENCE DATA)
If seeding a database of major physical market locations and corporate off-takers:

* **Wholesale Markets (*Кванташки пазари*):**
  * **Skopje Wholesale Market:** *Кванташки пазар Скопје* (blvd. Aleksandar Makedonski, Gazi Baba, Skopje — Coordinates: `42.0006, 21.4856`)
  * **Strumica Wholesale Market:** *Кванташки пазар Струмица* (Transit road / Industrijska, Strumica — Coordinates: `41.4411, 22.6508`)
* **Major Green Market Operator (Skopje):**
  * **Skopski Pazar AD:** `https://sp.mk` (Manages 16 green markets in Skopje including Zelen Pazar, Bit Pazar, Taftalidže, Bunjakovec, Ѓорче Петров, Ченто).
* **Major Registered Off-Takers by Sector:**
  * **Fruit & Veg Export/Buyout:** *Agrekord (Strumica)*, *Horizont (Strumica)*, *Agro-Komerc*, *Apple Land (Resen)*, *Prespa Frukt (Resen)*.
  * **Canneries (Peppers/Tomatoes/Gherkins):** *Vitaminka (Prilep)*, *Diem-GP (Gevgelija)*, *Vokel (Vinica)*, *Krivogaštani Promet*, *Bonum (Skopje)*.
  * **Wineries (Grapes):** *Tikveš (Kavadarci)*, *Stobi (Gradsko)*, *Dalvina (Strumica)*, *Imako Vino (Štip)*, *Bovin (Negotino)*.
  * **Tobacco (Strict Contract Buyout):** *Tutunski Kombinat Prilep*, *Sokotab (Bitola)*, *Alliance One Macedonia (Kavadarci)*.
  * **Dairies (Milk):** *Bimilk / Bitolska Mlekara (Bitola)*, *Zdravje Radovo (Strumica/Kumanovo)*, *Subra*, *Mlekara Gjorgiev (Radoviš)*.

---

## 5. RECOMMENDED IMPLEMENTATION STRATEGY FOR CLAUDE CODE
1. **Live Price Fetching (Fastest Path):** Query the WordPress REST APIs of `agrotim.mk` and `zelenaberza.com.mk` (`GET /wp-json/wp/v2/posts?search=цени&per_page=10`) to extract the latest published wholesale and buyout price articles, then parse the HTML tables/text for `ден/кг` values.
2. **Structured Historical & City-Level Prices:** Build a scraper using `Playwright` or `Cheerio`/`BeautifulSoup` targeting `https://zpis.gov.mk/price/1` through `/price/5` and `https://zpis.gov.mk/Bilteni_Izvestai`. Ensure SSL verification handles older government root certificates (`verify=False` or custom CA bundle if needed on some `.gov.mk` subdomains).
3. **Macro & Monthly Trends:** Use the `MakStat` PxWeb API (`https://makstat.stat.gov.mk/PXWeb/api/v1/mk/MakStat/`) for clean JSON time-series data without HTML scraping.
4. **Buyer Directory Seeding:** Download the `.xlsx` files from the Ministry of Agriculture registry (`mzsv.gov.mk/mk-MK/dokumenti-i-informacii-od-javen-karakter/registri`) or query the `data.gov.mk` CKAN API to populate verified buyer companies and locations.