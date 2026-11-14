# Agronomic Domain Specification: Crop Rotation & Soil Management Engine
**Target Consumer:** Claude Code / AI Software Engineering Agent  
**Purpose:** Domain knowledge, mathematical models, variable definitions, validation rules, and authoritative data sources for building a soil and farm management application.

---

## 1. Core Domain Definitions & Spatio-Temporal Disambiguation

To model farm operations accurately in a database or simulation engine, the system must distinguish between **temporal sequencing** (across years) and **spatial/intra-annual arrangement** (within a single year).

| Practice | Temporal Scope | Spatial Scope | Agronomic Definition & System Modeling Rule |
| :--- | :--- | :--- | :--- |
| **Crop Rotation** | Multi-year ($t_1, t_2, \dots, t_n$) | Single Field / Management Zone | Planting a sequence of *different* botanical crop species on the exact same parcel of land across successive growing seasons (years). **Rule:** A field has 1 primary crop per year cycle in standard rotation; crop changes when `Year` increments. |
| **Spatial Staggering (Field Phasing)** | Single Year ($t_1$) across multiple fields | Whole Farm ($F_A, F_B, F_C$) | Dividing a farm into $N$ fields so that each stage of an $N$-year rotation is grown every year on a different field (e.g., Year 1: $F_A=\text{Corn}$, $F_B=\text{Soy}$, $F_C=\text{Wheat}$). Stabilizes annual farm income and labor. |
| **Monoculture / Monocropping** | Multi-year ($t_1, t_2, \dots, t_n$) | Single Field | Planting the *same* crop species on the same field year after year (e.g., continuous corn). Triggers yield drag, pest accumulation, and nutrient depletion penalties. |
| **Intercropping** | Single Season ($t_1$) | Sub-field (Rows/Strips/Mixed) | Growing two or more crops *simultaneously* in the same field during the same growing season (e.g., relay intercropping, strip intercropping). |
| **Double Cropping (Sequential)** | Single Year ($t_1$, Season A & B) | Single Field | Growing and harvesting two complete crops consecutively on the same field within a single 12-month period (e.g., harvesting Winter Wheat in June, immediately planting Soybeans on the same field for October harvest). |
| **Cover Cropping** | Off-season / Shoulder Season | Single Field | Non-cash crops planted between primary cash crops to protect soil, scavenge nutrients, fix nitrogen ($N_2$), or build organic matter. Terminated prior to or during the next cash crop planting. |
| **Fallow** | Single Season or Full Year | Single Field | Intentionally leaving a field unseeded (either via tillage or chemical weed suppression) for a season to conserve soil moisture (common in dryland/arid wheat systems). |

---

## 2. Core Agronomic Factors & State Variables

When building data models or scoring algorithms for crop rotation, track the following four factor categories and their underlying variables.

### 2.1 Soil Fertility & Plant Biology Variables
* **`botanical_family` (Enum/String):** Taxonomic family of the crop. Critical for disease/pest break rules.
  * *Poaceae* (Grasses/Cereals): Corn, Wheat, Barley, Oats, Sorghum, Millet, Rye.
  * *Fabaceae* (Legumes): Soybeans, Alfalfa, Clover, Peas, Lentils, Peanuts, Dry Beans.
  * *Brassicaceae* (Brassicas/Mustards): Canola/Rapeseed, Radish, Turnip, Cabbage, Mustard.
  * *Solanaceae* (Nightshades): Potatoes, Tomatoes, Peppers, Eggplant.
  * *Asteraceae* (Composites): Sunflowers, Safflower, Lettuce.
  * *Amaranthaceae* (Chenopods): Sugar Beets, Spinach, Quinoa.
* **`nitrogen_role` (Enum: `HEAVY_FEEDER`, `MODERATE_FEEDER`, `LIGHT_FEEDER`, `NITROGEN_FIXER`, `SCAVENGER`):**
  * Legumes host symbiotic *Rhizobium* bacteria that convert atmospheric nitrogen ($N_2$) into ammonia ($NH_3$), providing a **Nitrogen Credit** to the subsequent crop.
* **`root_architecture` (Enum: `FIBROUS_SHALLOW`, `FIBROUS_DEEP`, `TAPROOT_MODERATE`, `TAPROOT_DEEP`):**
  * `root_depth_cm` (Float): Effective rooting depth ($30\text{ cm}$ for onions/potatoes vs. $150\text{–}300\text{ cm}$ for alfalfa/sunflowers). Alternating depths prevents hardpan compaction and extracts leached nitrates ($NO_3^-$).
* **`residue_c_n_ratio` (Float):** Carbon-to-Nitrogen ratio of crop residue left after harvest.
  * $< 24:1$ (e.g., Soybeans $\approx 20:1$, Alfalfa $\approx 15:1$): Rapid microbial decomposition, net **mineralization** (releases N to soil).
  * $> 24:1$ (e.g., Corn stover $\approx 57:1$, Wheat straw $\approx 80:1$): Slow decomposition, net **immobilization** (soil microbes temporarily tie up available soil N to break down carbon), builds long-term Soil Organic Matter (SOM).
* **`residue_biomass_ton_ha` (Float):** Dry matter left on field. High residue protects against wind/water erosion; low residue warms soil faster in spring but increases erosion risk.
* **`mycorrhizal_host` (Boolean):** Most crops form symbiotic associations with Arbuscular Mycorrhizal Fungi (AMF), improving phosphorus ($P$) uptake. *Brassicaceae* (Canola, Radish) and *Amaranthaceae* (Sugar Beets) are **non-hosts**; planting them reduces AMF populations for the following year.

### 2.2 Pest, Disease & Weed Management Variables
* **`min_return_interval_years` (Integer):** Minimum safe number of years before the same crop (or botanical family) can be planted on the same field again without severe disease buildup.
  * *Corn / Soybeans:* $1\text{–}2\text{ years}$
  * *Winter Wheat:* $2\text{ years}$ (due to Take-all fungus, *Gaeumannomyces graminis*)
  * *Canola / Brassicas:* $3\text{–}4\text{ years}$ (due to Clubroot, *Plasmodiophora brassicae*, and Blackleg)
  * *Potatoes / Sugar Beets / Peas / Sunflowers:* $4\text{–}5\text{ years}$ (due to Sclerotinia white mold, Aphanomyces root rot, and cyst nematodes).
* **`shared_pathogen_groups` (Array of Strings):** Cross-family pathogens that bridge botanical families.
  * *Example:* **White Mold (*Sclerotinia sclerotiorum*)** infects Soybeans (*Fabaceae*), Canola (*Brassicaceae*), Sunflowers (*Asteraceae*), and Dry Beans (*Fabaceae*). Rotating Soybean $\rightarrow$ Canola $\rightarrow$ Sunflower fails to break the disease cycle despite changing families; a grass (*Poaceae*) must be inserted.
* **`growth_habit_cycle` (Enum: `SPRING_ANNUAL_WARM`, `SPRING_ANNUAL_COOL`, `WINTER_ANNUAL`, `PERENNIAL`):**
  * Alternating `SPRING_ANNUAL_WARM` (Corn/Soy) with `WINTER_ANNUAL` (Winter Wheat/Rye) disrupts weed life cycles because fall-seeded crops canopy early in spring, shading out summer annual weeds (like Palmer amaranth or waterhemp), and are harvested in summer before weeds set seed.
* **`herbicide_group_history` (Array of WSSA/HRAC Group IDs):** Tracks herbicide Modes of Action (e.g., Group 2 ALS inhibitors, Group 4 Synthetic Auxins, Group 9 EPSPS/Glyphosate, Group 14 PPO inhibitors, Group 15 VLCFA inhibitors, Group 27 HPPD inhibitors).

### 2.3 Climate, Water & Soil Physical Constraints
* **`gdd_requirement` (Integer):** Growing Degree Days required from planting to physiological maturity (Black Layer in corn).
* **`base_temp_c` (Float):** Baseline temperature ($T_{\text{base}}$) for GDD calculation ($10^\circ\text{C}$ / $50^\circ\text{F}$ for warm-season crops like Corn/Soy; $0^\circ\text{C}\text{–}4.4^\circ\text{C}$ / $32^\circ\text{F}\text{–}40^\circ\text{F}$ for cool-season crops like Wheat/Peas).
* **`crop_water_use_mm` (Float):** Seasonal Evapotranspiration ($ET_c$) demand. High water users (Alfalfa, Corn, Sunflowers) deplete subsoil moisture; low water users (Millet, Sorghum, Field Peas) conserve moisture for the next year.
* **`planting_window_start` / `planting_window_end` (Day of Year, $1\text{–}365$):** Dictates sequence feasibility.
* **`harvest_window_start` / `harvest_window_end` (Day of Year, $1\text{–}365$):** **Sequence Constraint:** Crop $t+1$'s `planting_window_end` must be $>$ Crop $t$'s `harvest_window_start` (plus field prep days) if transitioning from a summer crop to a fall-seeded winter crop in the same calendar year.
* **`soil_ph_min` / `soil_ph_max` (Float):** Optimal pH range (e.g., Alfalfa requires $6.5\text{–}7.5$ for *Rhizobium* nodulation; Potatoes tolerate $5.0\text{–}6.0$ to suppress common scab).

### 2.4 Operational & Economic Constraints
* **`herbicide_carryover_months` (Dict of Chemical $\rightarrow$ Months to Safe Plant):** Residual soil half-life constraint. If Farmer applies *Atrazine* (Group 5) or *Mesotrione* (Group 27) on Corn in Year $t$, sensitive crops like Sugar Beets, Canola, or Vegetables cannot be planted in Year $t+1$ due to phytotoxicity.
* **`equipment_compatibility_group` (Enum: `ROW_CROP_PLANTER`, `GRAIN_DRILL`, `SPECIALTY_TUBER`, `FORAGE_HARVESTER`):** Tracks capital expenditure barriers.
* **`labor_peak_months` (Array of Integers $1\text{–}12$):** Diversified rotations flatten labor spikes across April–November.

---

## 3. Reference Crop Parameter Matrix (Seed Data for App)

Claude Code can use this structured table directly as seed data or lookup logic for rotation validation.

| Crop Name | Botanical Family | Cycle Type | N Role | N Credit to Next Crop ($\text{kg N/ha}$) | Root Type & Depth ($\text{cm}$) | Residue $C:N$ Ratio | Min Return Interval (Yrs) | Water Use Tier |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Corn (Maize)** | *Poaceae* | Warm Spring Annual | Heavy Feeder | $0$ | Fibrous Deep ($120\text{–}150$) | $\sim 57:1$ (High Biomass) | $1\text{–}2$ | High |
| **Soybean** | *Fabaceae* | Warm Spring Annual | N Fixer | $35\text{–}50$ | Taproot Mod ($90\text{–}120$) | $\sim 20:1$ (Low Biomass) | $2$ | Moderate |
| **Winter Wheat** | *Poaceae* | Cool Winter Annual | Mod Feeder | $0$ | Fibrous Mod ($90\text{–}120$) | $\sim 80:1$ (High Biomass) | $2\text{–}3$ | Low–Mod |
| **Alfalfa** | *Fabaceae* | Perennial ($3\text{–}5\text{ yr}$) | High N Fixer | $90\text{–}170$ | Taproot Deep ($180\text{–}300$) | $\sim 15:1$ | $3\text{–}4$ | Very High |
| **Canola (Rapeseed)** | *Brassicaceae* | Cool Spring/Winter | Heavy Feeder | $0$ | Taproot Mod ($90\text{–}120$) | $\sim 45:1$ | $3\text{–}4$ | Moderate |
| **Field Pea / Lentil** | *Fabaceae* | Cool Spring Annual | N Fixer | $25\text{–}45$ | Taproot Shallow ($60\text{–}90$) | $\sim 22:1$ (Low Biomass) | $4$ | Low |
| **Sunflower** | *Asteraceae* | Warm Spring Annual | Mod Feeder | $0$ | Taproot Deep ($150\text{–}240$) | $\sim 40:1$ | $4$ | High (Deep) |
| **Potato** | *Solanaceae* | Cool Spring Annual | Heavy Feeder | $0$ | Fibrous Shallow ($40\text{–}60$) | $\sim 18:1$ (Very Low) | $3\text{–}5$ | Mod–High |
| **Sorghum (Milo)** | *Poaceae* | Warm Spring Annual | Mod Feeder | $0$ | Fibrous Deep ($120\text{–}150$) | $\sim 60:1$ (High Biomass) | $2$ | Low (Drought Tol.) |
| **Cereal Rye (Cover)**| *Poaceae* | Cool Winter Annual | N Scavenger | $0$ (Immobilizes if late) | Fibrous Deep ($120\text{–}180$) | $25:1$ (Veg) to $65:1$ (Mature) | $1$ | Low |
| **Crimson Clover (Cover)**| *Fabaceae* | Cool Winter Annual | N Fixer | $55\text{–}110$ | Taproot Shallow ($45\text{–}75$) | $\sim 16:1$ | $2$ | Moderate |

---

## 4. Mathematical & Algorithmic Formulas for Application Logic

When implementing calculators, simulations, or recommendation engines in code, use the following standard agronomic equations.

### 4.1 Growing Degree Days (GDD) Accumulation
Used to validate whether a crop or cover crop can mature before frost or before the next crop's planting date:
$$\text{GDD}_{\text{daily}} = \max\left(0, \frac{\min(T_{\max}, T_{\text{upper}}) + \max(T_{\min}, T_{\text{base}})}{2} - T_{\text{base}}\right)$$
* Where $T_{\text{base}} = 10^\circ\text{C}$ and $T_{\text{upper}} = 30^\circ\text{C}$ for Corn/Soybeans; $T_{\text{base}} = 0^\circ\text{C}$ or $4.4^\circ\text{C}$ for Small Grains.

### 4.2 Net Nitrogen Fertilizer Requirement ($N_{\text{req}}$)
Used to calculate how much synthetic or organic fertilizer a farmer needs in Year $t$ based on Year $t-1$'s rotation crop:
$$N_{\text{req}} = (Y_{\text{goal}} \times U_N) - N_{\text{soil}} - N_{\text{legume\_credit}} - N_{\text{manure}} + N_{\text{immobilization\_penalty}}$$
* $Y_{\text{goal}}$: Target yield (e.g., $\text{bu/ac}$ or $\text{t/ha}$).
* $U_N$: Nitrogen uptake factor per unit of yield.
* $N_{\text{soil}}$: Baseline residual soil nitrate ($NO_3^--N$) from soil test.
* $N_{\text{legume\_credit}}$: Nitrogen credit from previous year's legume (see Section 3 table).
* $N_{\text{immobilization\_penalty}}$: Added $N$ needed ($15\text{–}35\text{ kg N/ha}$) if previous crop left high volumes of high-$C:N$ residue ($C:N > 50:1$, such as wheat straw or mature cereal rye).

### 4.3 Rotation Diversity & Transition Scoring Rule Engine
To build an automated **Rotation Health Score ($0\text{–}100$)** or transition validator between `Crop[t-1]` and `Crop[t]`, implement these rule weights:

1. **Hard Constraints (Blocking Errors / High Risk Alerts):**
   * **Herbicide Carryover Violation:** `if (MonthsElapsed(LastHerbicideApp, NextCropPlantDate) < Herbicide.RotationRestriction[NextCrop.id]) -> BLOCK ("Phytotoxicity Risk")`
   * **Calendar Overlap Violation:** `if (SameCalendarYearTransition && PrevCrop.harvest_doy > NextCrop.latest_plant_doy) -> BLOCK ("Planting Window Missed")`
   * **Return Interval Violation:** `if (YearsSinceLastPlanted(Field, NextCrop) < NextCrop.min_return_interval) -> WARN ("Severe Pathogen/Nematode Build-up Risk")`

2. **Soft Scoring Modifiers (Agronomic Synergy):**
   * **Family Alternation Bonus:** `PrevCrop.botanical_family != NextCrop.botanical_family` $\rightarrow +20\text{ pts}$ (breaks host-specific pest cycles).
   * **Shared Pathogen Penalty:** `Intersection(PrevCrop.shared_pathogens, NextCrop.shared_pathogens).length > 0` $\rightarrow -25\text{ pts}$ (e.g., Soybean $\rightarrow$ Canola shares *Sclerotinia*).
   * **Nitrogen Synergy Bonus:** `PrevCrop.nitrogen_role == 'NITROGEN_FIXER' && NextCrop.nitrogen_role == 'HEAVY_FEEDER'` $\rightarrow +20\text{ pts}$ (maximizes N credit utilization; note that planting a legume after a legume wastes the N credit and suppresses nodulation).
   * **Root Depth Alternation Bonus:** `PrevCrop.root_architecture != NextCrop.root_architecture` $\rightarrow +15\text{ pts}$.
   * **Seasonal Cycle Alternation Bonus:** `PrevCrop.growth_habit_cycle != NextCrop.growth_habit_cycle` $\rightarrow +15\text{ pts}$ (disrupts weed seedbank timing).
   * **Mycorrhizal Starvation Penalty:** `PrevCrop.mycorrhizal_host == false && NextCrop.mycorrhizal_dependency == 'HIGH'` $\rightarrow -10\text{ pts}$ (e.g., Corn or Flax planted immediately after Canola or Sugar Beets can suffer early Phosphorus deficiency, known as "fallow syndrome").

---

## 5. Proposed Data Schema (JSON / TypeScript Interfaces)

Claude Code can adapt these interfaces directly for backend models (PostgreSQL/Prisma/Supabase/SQLite) or frontend state.

```typescript
export type BotanicalFamily =
  | 'Poaceae'       // Grasses / Cereals
  | 'Fabaceae'      // Legumes
  | 'Brassicaceae'  // Mustards / Brassicas
  | 'Solanaceae'    // Nightshades
  | 'Asteraceae'    // Sunflowers / Composites
  | 'Amaranthaceae' // Beets / Chenopods
  | 'Linaceae'      // Flax
  | 'Polygonaceae'  // Buckwheat
  | 'Malvaceae';    // Cotton

export type NitrogenRole =
  | 'HEAVY_FEEDER'
  | 'MODERATE_FEEDER'
  | 'LIGHT_FEEDER'
  | 'NITROGEN_FIXER'
  | 'NITROGEN_SCAVENGER';

export type GrowthCycle =
  | 'SPRING_ANNUAL_WARM'
  | 'SPRING_ANNUAL_COOL'
  | 'WINTER_ANNUAL'
  | 'BIENNIAL'
  | 'PERENNIAL';

export interface CropDefinition {
  id: string;
  commonName: string;
  scientificName: string;
  botanicalFamily: BotanicalFamily;
  growthCycle: GrowthCycle;
  isCoverCrop: boolean;
  
  // Soil & Nutrient Parameters
  nitrogenRole: NitrogenRole;
  nitrogenCreditKgHa: number;          // N provided to subsequent crop
  nitrogenUptakePerTonYieldKg: number; // N required per ton of target yield
  residueCNRatio: number;              // <24 mineralizes, >24 immobilizes
  residueBiomassIndex: 1 | 2 | 3 | 4 | 5; // 1 = Very Low (Potato), 5 = Very High (Corn)
  rootDepthCm: { min: number; max: number };
  rootType: 'FIBROUS' | 'TAPROOT';
  mycorrhizalHost: boolean;
  optimalSoilPh: { min: number; max: number };

  // Climate & Water Parameters
  baseTempC: number;
  gddToMaturity: number;
  waterUseTier: 'LOW' | 'MODERATE' | 'HIGH' | 'VERY_HIGH';

  // Pest & Rotation Constraints
  minReturnIntervalYears: number;      // Min years before planting same crop again
  sharedPathogenIds: string[];         // e.g., ['sclerotinia_white_mold', 'rhizoctonia_solani']
  allelochemicalEffect: boolean;       // e.g., Cereal Rye suppresses small-seeded weeds/crops
}

export interface FieldRotationHistoryEntry {
  fieldId: string;
  cropYear: number;                    // e.g., 2026
  sequenceOrderInYear: 1 | 2;          // 1 = Primary crop, 2 = Double crop or Cover crop
  cropId: string;
  plantingDate: string;                // ISO Date
  harvestOrTerminationDate: string;    // ISO Date
  yieldTonsHa?: number;
  herbicidesApplied: Array<{
    activeIngredient: string;
    hracGroup: number;
    applicationDate: string;
    plantBackRestrictionsMonths: Record<string, number>; // cropId -> months
  }>;
}
```

---

## 6. Public APIs, Datasets & Agronomic Reference Links

Claude Code can fetch data, integrate APIs, or scrape standard tables from these authoritative agricultural and soil science resources:

### 6.1 Soil & Spatial APIs (Programmatic Access)
1. **USDA NRCS Soil Data Access (SDA) / SSURGO API:**
   * **URL:** `https://sdmdataaccess.sc.egov.usda.gov/`
   * **REST Endpoint:** `https://SDMDataAccess.sc.egov.usda.gov/Tabular/post.rest`
   * **Use Case:** Query soil texture, slope, drainage class, organic matter ($\%$), pH, Available Water Capacity (AWC), and National Commodity Crop Productivity Index (NCCPI) by GPS polygon or lat/lon in the US.
2. **ISRIC SoilGrids REST API (Global Soil Data):**
   * **URL:** `https://rest.isric.org/soilgrids/v2.0/docs`
   * **Use Case:** Global $250\text{m}$ resolution gridded soil properties (organic carbon, bulk density, pH, clay/silt/sand content, cation exchange capacity) across 6 soil depth horizons ($0\text{–}200\text{ cm}$) for farms outside the US.
3. **Open-Meteo Agricultural Weather API:**
   * **URL:** `https://open-meteo.com/en/docs`
   * **Use Case:** Free, no-key-required API providing historical and forecast Evapotranspiration ($ET_0$), soil temperature at multiple depths ($0, 6, 18, 54\text{ cm}$), and volumetric soil moisture ($m^3/m^3$) for calculating GDD and planting windows.
4. **FAO WaPOR & Crop Calendar API / Ecocrop Database:**
   * **URL:** `https://gaez.fao.org/` and `https://cropcalendar.apps.fao.org/`
   * **Use Case:** Global crop phenology, planting/harvesting windows by agro-ecological zone, and crop water requirements ($K_c$ coefficients).

### 6.2 Crop Rotation & Cover Crop Decision Tool Data Sources
5. **Midwest Cover Crops Council (MCCC) / Northeast / Southern / Western Cover Crop Selector Data:**
   * **URL:** `https://www.midwestcovercrops.org/selector-tool-2/`
   * **Use Case:** Contains county-level frost seeding windows, nitrogen fixation ratings, erosion control ratings, and cash-crop transition rules.
6. **USDA-ARS RUSLE2 / WEPS (Revised Universal Soil Loss Equation):**
   * **URL:** `https://fargo.nserl.purdue.edu/rusle2_dataweb/RUSLE2_Index.htm`
   * **Use Case:** Standard Crop Management ($C$-factor) databases containing daily canopy cover, root biomass, and residue decomposition coefficients for hundreds of crops.
7. **SARE (Sustainable Agriculture Research and Education) — *Crop Rotation on Organic Farms: A Planning Manual* (Mohler & Johnson):**
   * **URL:** `https://www.sare.org/resources/crop-rotation-on-organic-farms/`
   * **Use Case:** The gold-standard agronomic reference containing empirical crop sequence matrices, cross-disease charts, weed density tables, and nitrogen budget spreadsheets.
8. **HRAC (Herbicide Resistance Action Committee) Global Mode of Action Classification:**
   * **URL:** `https://hracglobal.com/tools/hrac-mode-of-action-classification-2024-map`
   * **Use Case:** Standardized herbicide group numbering system to track rotation of herbicide modes of action and prevent resistance.