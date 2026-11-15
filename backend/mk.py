"""Macedonian for everything the API writes in words: soil health, alerts, rotation names and advice.

The English text is built from templates in health.py, sensor.py and rotations.py; each template has a pattern
here. translate() walks an API response and rewrites its strings. Anything without a pattern stays English, so a
new sentence never breaks the page, it only shows in English until it is added here.
"""
import re

# crop and word names, longest first so "dry bean" wins over "bean"
WORDS = {
    "vetch + oat cover": "граор + овес", "winter wheat": "пченица", "winter barley": "јачмен",
    "maize (grain)": "пченка", "alfalfa (hay)": "луцерка", "dry bean": "грав", "winter vetch": "зимски граор",
    "pepper": "пиперка", "tomato": "домат", "wheat": "пченица", "barley": "јачмен", "maize": "пченка",
    "sunflower": "сончоглед", "tobacco": "тутун", "bean": "грав", "chickpea": "наут", "alfalfa": "луцерка",
    "vetch": "граор", "oat": "овес", "a typical crop": "типична култура", "the crop": "културата",
}
FAMILIES = {"Solanaceae": "компирови (Solanaceae)", "Poaceae": "житни (Poaceae)",
            "Fabaceae": "мешункасти (Fabaceae)", "Asteraceae": "главоцветни (Asteraceae)"}
MONTHS = {"January": "јануари", "February": "февруари", "March": "март", "April": "април", "May": "мај",
          "June": "јуни", "July": "јули", "August": "август", "September": "септември", "October": "октомври",
          "November": "ноември", "December": "декември"}
SHORT_MONTHS = {"Jan": "јан", "Feb": "фев", "Mar": "мар", "Apr": "апр", "May": "мај", "Jun": "јун", "Jul": "јул",
                "Aug": "авг", "Sep": "сеп", "Oct": "окт", "Nov": "ное", "Dec": "дек"}
SLOPE = {"flat": "рамно", "gentle": "благ наклон", "moderate": "умерен наклон", "steep": "стрмно"}
SOILS = {"sandy loam": "песоклива иловица", "clay loam": "глинеста иловица", "silty clay loam": "тињеста глинеста иловица",
         "silt loam": "тињеста иловица", "sandy clay loam": "песоклива глинеста иловица", "loamy sand": "иловичест песок",
         "silty clay": "тињеста глина", "sandy clay": "песоклива глина", "loam": "иловица", "clay": "глина",
         "sand": "песок", "silt": "тиња"}

_word_re = re.compile(r"\b(" + "|".join(re.escape(w) for w in sorted(WORDS, key=len, reverse=True)) + r")\b",
                      re.IGNORECASE)


def words(s: str) -> str:
    """Crop names inside a sentence, keeping a capital first letter where the English had one."""
    def rep(m):
        mk = WORDS[m.group(0).lower()]
        return mk[0].upper() + mk[1:] if m.group(0)[0].isupper() else mk
    return _word_re.sub(rep, s)


def soil_name(s: str) -> str:
    for en in sorted(SOILS, key=len, reverse=True):
        if s.lower().startswith(en):
            mk = SOILS[en]
            return mk[0].upper() + mk[1:] + s[len(en):]
    return s


def rotation_name(s: str) -> str:
    s = s.replace(", with winter vetch", ", со зимски граор").replace(", vetch every winter", ", граор секоја зима")
    s = re.sub(r", vetch before ", ", граор пред ", s)
    s = s.replace(" and ", " и ").replace("(2 years)", "(2 години)").replace(" (now)", " (сега)")
    return words(s)


def _f(x):  # a matched word or name inside a sentence
    return words(x)


# (pattern, Macedonian) pairs; groups are passed through words() so crop names inside are translated too
SENTENCES = [
    # soil health card
    (r"Healthy", "Здрава"), (r"Needs attention", "Бара внимание"), (r"Poor", "Лоша"), (r"No sensor data", "Нема податоци од сензорот"),
    (r"Connect the ESP32 to see the health of this field's soil\.", "Поврзете го ESP32 за да го видите здравјето на почвата на оваа нива."),
    (r"Water for the roots", "Вода за корените"), (r"Soil temperature", "Температура на почвата"),
    (r"Soil protection", "Заштита на почвата"), (r"Keeps water", "Ја задржува водата"),
    (r"Wetter than the soil can hold: water is still draining or standing\.", "Повлажна отколку што почвата може да задржи: водата сè уште се цеди или стои."),
    (r"Roots can take up water easily\.", "Корените лесно земаат вода."),
    (r"Getting dry: close to the point where plants start to suffer\.", "Се суши: блиску до точката кога растенијата почнуваат да страдаат."),
    (r"Too dry: plants are under water stress\.", "Премногу суво: растенијата се под воден стрес."),
    (r"(\d+)% of available water", r"\1% од достапната вода"),
    (r"Sensor reads (\d+)% \(about ([\d.]+) m³/m³\)\. This soil holds plant water between ([\d.]+) \(wilting point\) and ([\d.]+) m³/m³ \(field capacity\); (.+) is stressed below (\d+)% of that range \(FAO-56\)\.",
     lambda m: f"Сензорот покажува {m[1]}% (околу {m[2]} m³/m³). Оваа почва држи вода за растенијата меѓу {m[3]} (точка на венење) и {m[4]} m³/m³ (пољски капацитет); {_f(m[5])} е под стрес под {m[6]}% од тој опсег (FAO-56)."),
    (r"Too hot: soil life and roots are stressed near the surface\.", "Премногу топло: животот во почвата и корените се под стрес близу површината."),
    (r"Near freezing: soil life is dormant\.", "Близу замрзнување: животот во почвата мирува."),
    (r"Far from normal for this time of year\.", "Далеку од нормалното за ова време од годината."),
    (r"Normal for the season: soil life is active\.", "Нормално за сезоната: животот во почвата е активен."),
    (r"Cool, as usual for the season: soil life is slow\.", "Ладно, како обично за сезоната: животот во почвата е бавен."),
    (r"Measured by the DS18B20 probe in the soil; the NASA POWER 0-10 cm soil temperature for this date averages ([-\d.]+) °C \(2001-now\)\.",
     r"Измерено со сондата DS18B20 во почвата; NASA POWER температурата на почвата на 0-10 cm за овој датум во просек е \1 °C (2001-денес)."),
    (r"Measured by the DS18B20 probe in the soil\.", "Измерено со сондата DS18B20 во почвата."),
    (r"(\d+) °C daily swing", r"\1 °C дневна разлика"),
    (r"Well buffered: covered or moist soil\.", "Добро заштитена: покриена или влажна почва."),
    (r"Large daily swings: the soil surface is bare and exposed\.", "Големи дневни разлики: површината на почвата е гола и изложена."),
    (r"Bare soil heats up by day and cools at night much more than soil under a crop, mulch or cover crop\. Big swings dry the soil and slow soil life\.",
     "Голата почва дење се загрева, а ноќе се лади многу повеќе од почвата под култура, малч или покривна култура. Големите разлики ја сушат почвата и го забавуваат животот во неа."),
    (r"(\d+) points drier per day", r"\1 поени посуво на ден"),
    (r"Keeps water well between rains\.", "Добро ја задржува водата меѓу дождовите."),
    (r"Loses water fast: low organic matter or a bare surface\.", "Брзо губи вода: малку органска материја или гола површина."),
    (r"The fall in soil moisture over the last day shows how fast water leaves the root zone\. Soils rich in organic matter, and covered soils, lose it more slowly\.",
     "Падот на влажноста во последниот ден покажува колку брзо водата ја напушта зоната на корените. Почвите богати со органска материја и покриените почви ја губат побавно."),
    # alerts
    (r"Water now", "Наводнете сега"), (r"Water soon", "Наводнете наскоро"), (r"Waterlogged soil", "Презаситена почва"),
    (r"Frost now", "Мраз сега"), (r"Frost risk tonight", "Ризик од мраз вечерва"), (r"Heat stress", "Топлински стрес"),
    (r"Disease weather", "Време за болести"),
    (r"The soil holds (\d+)% of its available water; (.+) is stressed below (\d+)%\.",
     lambda m: f"Почвата има {m[1]}% од достапната вода; {_f(m[2])} е под стрес под {m[3]}%."),
    (r"Available water (\d+)%: plan to irrigate in the next days\.", r"Достапна вода \1%: планирајте наводнување во наредните денови."),
    (r"Soil has stayed above field capacity for hours: roots lack air\. Avoid irrigating and driving on the field\.",
     "Почвата со часови е над пољскиот капацитет: на корените им недостига воздух. Не наводнувајте и не возете по нивата."),
    (r"Air at ([-\d.]+) °C in the field: cover seedlings or run frost irrigation\.", r"Воздухот е \1 °C на нивата: покријте ги расадите или наводнувајте против мраз."),
    (r"Air ([-\d.]+) °C( and falling)?(, dew point ([-\d.]+) °C)?: the field can reach 0 °C before dawn\. Protect young plants\.",
     lambda m: f"Воздух {m[1]} °C" + (" и паѓа" if m[2] else "") + (f", точка на роса {m[4]} °C" if m[3] else "")
     + ": нивата може да падне на 0 °C пред зори. Заштитете ги младите растенија."),
    (r"Air ([-\d.]+) °C: flowers of pepper and tomato drop above 35 °C\. Irrigate early morning, shade if possible\.",
     r"Воздух \1 °C: цветовите на пиперката и доматот паѓаат над 35 °C. Наводнувајте рано наутро, засенете ако може."),
    (r"About (\d+) of the last 12 hours were humid \(≥ 90%\) and mild \(10-25 °C\): late blight and downy mildew spread\. Check leaves\.",
     r"Околу \1 од последните 12 часа беа влажни (≥ 90%) и благи (10-25 °C): пламеницата и пероноспората се шират. Проверете ги листовите."),
    # rotation cards
    (r"Needs (\d+)% less irrigation water than your current rotation \((\d+) vs (\d+) mm a year\)\.",
     r"Бара \1% помалку вода за наводнување од сегашниот плодоред (\2 наспроти \3 mm годишно)."),
    (r"Living roots cover the soil (\d+)% of the year instead of (\d+)%\.", r"Живи корени ја покриваат почвата \1% од годината наместо \2%."),
    (r"Breaks the pest and disease cycle: the same plant family does not come back too soon\.",
     "Го прекинува циклусот на штетници и болести: истото растително семејство не се враќа прерано."),
    (r"Legumes add about (\d+) kg of nitrogen per hectare a year\.", r"Мешункастите додаваат околу \1 kg азот по хектар годишно."),
    (r"(\d+)% less soil exposed to heavy rain\.", r"\1% помалку почва изложена на силен дожд."),
    (r"Holds up better in dry years \((\d+)% of normal yield vs (\d+)%\)\.", r"Подобро издржува во сушни години (\1% од нормалниот принос наспроти \2%)."),
    (r"Higher gross income per hectare \((\d+)%\)\.", r"Повисок бруто приход по хектар (\1%)."),
    (r"A balanced alternative to compare\.", "Урамнотежена алтернатива за споредба."),
    (r"This is what the field grows now: the baseline every other option is compared with\.",
     "Ова е она што нивата го одгледува сега: основата со која се споредува секоја друга опција."),
    (r"Keeps (.+), which you already grow: you know the methods, the buyers and have the machinery\.",
     lambda m: f"Ја задржува културата {_f(m[1]).replace(' and ', ' и ')} што веќе ја одгледувате: ги знаете методите, купувачите и ја имате механизацијата."),
    (r"Replayed over all (\d+) seasons of real weather at this field, each crop in every season \(([\d-]+)\): typical year (\d+) mm irrigation, driest 1 in 10 years (\d+) mm\.",
     r"Пресметано низ сите \1 сезони со вистинското време на оваа нива, секоја култура во секоја сезона (\2): типична година \3 mm наводнување, најсушна 1 од 10 години \4 mm."),
    (r"In the driest summer \((\d+), crop demand exceeded rain by (\d+) mm\) the main crops reached (\d+)% of normal yield in the worst years\.",
     r"Во најсушното лето (\1, потребата на културите го надмина дождот за \2 mm) главните култури дадоа \3% од нормалниот принос во најлошите години."),
    (r"A frost-sensitive crop met a damaging frost in (\d+)% of seasons \(last spring frost usually ([\d]+) (\w+), 1 year in 10 after ([\d]+) (\w+)\)\.",
     lambda m: f"Култура чувствителна на мраз доживеа штетен мраз во {m[1]}% од сезоните (последниот пролетен мраз обично е на {m[2]} {SHORT_MONTHS.get(m[3], m[3])}, 1 година од 10 по {m[4]} {SHORT_MONTHS.get(m[5], m[5])})."),
    (r"Field slope ([\d.]+)° \((\w+)\): heavy rain on bare soil weighs ([\d.]+)x a gentle 2% slope\.",
     lambda m: f"Наклон на нивата {m[1]}° ({SLOPE.get(m[2], m[2])}): силен дожд на гола почва тежи {m[3]} пати колку на благ наклон од 2%."),
    (r"Satellite greenness shows this field bare in (.+?) in most years(; the winter cover crop in this rotation fills that gap)?\.",
     lambda m: "Сателитското зеленило покажува дека нивата е гола во " + ", ".join(SHORT_MONTHS.get(x.strip(), x) for x in m[1].split(","))
     + " во повеќето години" + ("; зимската покривна култура во овој плодоред ја пополнува таа празнина." if m[2] else ".")),
    (r"The simulated soil water follows NASA SMAP satellite soil moisture at this field \(correlation ([\d.]+) over (\d+) days, ([\d-]+)\)\.",
     r"Пресметаната вода во почвата ја следи сателитската влажност NASA SMAP на оваа нива (корелација \1 низ \2 дена, \3)."),
    (r"(.+) \((\d+)% sand, (\d+)% clay, ([\d.]+)% organic matter(, pH ([\d.]+))?\) from the global soil map at this field( \(nearest mapped pixel\))?\.",
     lambda m: f"{soil_name(m[1])} ({m[2]}% песок, {m[3]}% глина, {m[4]}% органска материја" + (f", pH {m[6]}" if m[5] else "")
     + ") од глобалната карта на почви за оваа нива" + (" (најблискиот пиксел)" if m[7] else "") + "."),
    (r"About (\d+) kg N/ha a year from legumes: less fertiliser\.", r"Околу \1 kg N/ha годишно од мешункасти: помалку ѓубриво."),
    (r"([\d.]+) t/ha of crop residue a year feeds soil organic matter\.", r"\1 t/ha растителни остатоци годишно ја хранат органската материја во почвата."),
    (r"Soil covered most of the year: less erosion, better infiltration, more soil life\.",
     "Почвата е покриена поголем дел од годината: помалку ерозија, подобро впивање, повеќе живот во почвата."),
    (r"No plant family repeats too soon: pests and soil diseases lose their host\.",
     "Ниедно растително семејство не се повторува прерано: штетниците и болестите во почвата го губат домаќинот."),
    (r"Low irrigation need: safer when wells or canals run short\.", "Мала потреба од наводнување: посигурно кога бунарите или каналите пресушуваат."),
    (r"Gross income about (\d+) € per hectare a year\.", r"Бруто приход околу \1 € по хектар годишно."),
    (r"Familiar crops and markets\.", "Познати култури и пазари."),
    (r"(.+) follows (.+) \((\w+)\) after (\d+) season\(s\): needs (\d+) for soil-borne pests and diseases to die down\.",
     lambda m: f"{_f(m[1])} доаѓа по {_f(m[2]).lower()} ({FAMILIES.get(m[3], m[3])}) по {m[4]} сезона: потребни се {m[5]} за штетниците и болестите во почвата да згаснат."),
    (r"Gross income about (\d+)% lower than now: check whether lower costs and soil gains make up for it\.",
     r"Бруто приходот е околу \1% понизок од сега: проверете дали пониските трошоци и подобрата почва го надоместуваат."),
    (r"New crops for this farm \((.+)\): check buyers, seed and machinery locally\.",
     lambda m: f"Нови култури за ова стопанство ({_f(m[1])}): проверете купувачи, семе и механизација локално."),
    (r"Late frost hits a sensitive crop in (\d+)% of seasons: transplant later or protect seedlings\.",
     r"Доцниот мраз погодува чувствителна култура во \1% од сезоните: расадувајте подоцна или заштитете ги расадите."),
    (r"About ([\d.]+) waterlogged days a year on this soil: check drainage\.", r"Околу \1 дена годишно презаситена почва: проверете ја дренажата."),
    (r"Alfalfa ties the field up for two years and needs a hay buyer or livestock\.",
     "Луцерката ја зафаќа нивата две години и бара купувач на сено или добиток."),
    (r"Check timing between harvest and the next sowing with local practice\.",
     "Проверете го времето меѓу бербата и следната сеидба според локалната пракса."),
    (r"Soil comes from a 250 m global soil map, not a sample from this field: a lab soil test would confirm texture, organic matter and pH\.",
     "Почвата е од глобална карта на почви од 250 m, а не од примерок од оваа нива: лабораториска анализа би ги потврдила составот, органската материја и pH."),
    (r"Soil map unavailable here: a typical valley loam is assumed\.", "Нема карта на почви тука: се претпоставува типична речна иловица."),
    (r"Prices for (.+) are estimates: no official market price was found\.",
     lambda m: f"Цените за {_f(m[1])} се проценки: не е најдена официјална пазарна цена."),
    (r"Crop water and yield responses are FAO table values, not calibrated for local varieties\.",
     "Потребите од вода и приносите се табеларни вредности од FAO, не се прилагодени за локалните сорти."),
    (r"The yield loss from repeating a plant family is assumed \((\d+)%\), not measured on this field\.",
     r"Загубата на принос од повторување на растително семејство е претпоставена (\1%), не е измерена на оваа нива."),
    (r"Satellite greenness is from a 250 m pixel, which also sees neighbouring fields\.",
     "Сателитското зеленило е од пиксел од 250 m, кој ги гледа и соседните ниви."),
    # rotation ideas
    (r"The rotation you grow now\.", "Плодоредот што го одгледувате сега."),
    (r"What you grow now, plus a vetch and oat cover crop over each winter\.", "Она што го одгледувате сега, со граор и овес како покривна култура секоја зима."),
    (r"Keeps your (.+), then two years of other families so its pests and soil diseases die down; the legume adds nitrogen\.",
     lambda m: f"Ја задржува вашата {_f(m[1])}, потоа две години други семејства за нејзините штетници и болести во почвата да згаснат; мешункастата култура додава азот."),
    (r"The usual vegetable sequence in the valley: high income, but three nightshades in a row and bare winters\.",
     "Вообичаениот редослед на зеленчук во долината: висок приход, но три компирови култури по ред и голи зими."),
    (r"Wheat with a chickpea break: a rain-fed legume that adds nitrogen and stops cereal diseases carrying over\.",
     "Пченица со пауза со наут: мешункаста култура без наводнување која додава азот и ги прекинува болестите на житата."),
    (r"Three field crops from three plant families, all workable without irrigation, with the soil covered over winter\.",
     "Три полски култури од три растителни семејства, сите без наводнување, со покриена почва преку зима."),
    (r"Keeps wheat and maize, adds a bean year and a winter cover so the soil is not bare before maize\.",
     "Ги задржува пченицата и пченката, додава година со грав и зимска покривка за почвата да не е гола пред пченката."),
    (r"A two-year alfalfa ley rebuilds soil structure and nitrogen, then feeds the cereals that follow\.",
     "Две години луцерка ги обновуваат структурата на почвата и азотот, а потоа ги хранат житата што следат."),
    (r"A field-crop rotation without vegetables: less labour, lower income\.", "Плодоред со полски култури без зеленчук: помалку работа, помал приход."),
    (r"A lower-water rotation: sunflower and wheat are grown without irrigation\.", "Плодоред со помалку вода: сончогледот и пченицата растат без наводнување."),
    (r"Breaks the nightshade cycle with a cereal and a legume; the vetch adds nitrogen before the pepper\.",
     "Го прекинува циклусот на компировите култури со жито и мешункаста култура; граорот додава азот пред пиперката."),
    (r"Common on the drier fields at the valley edge\.", "Вообичаено на посушите ниви на работ од долината."),
    (r"Deep alfalfa roots rebuild soil structure and nitrogen; the field is covered almost all year\.",
     "Длабоките корени на луцерката ги обновуваат структурата на почвата и азотот; нивата е покриена речиси цела година."),
    (r"Two vegetable years out of four; chickpea needs little water and fixes nitrogen\.",
     "Две години зеленчук од четири; наутот бара малку вода и врзува азот."),
    # reasons an option is not offered
    (r"only (\d+)% of normal yield in a dry year with no irrigation", r"само \1% од нормалниот принос во сушна година без наводнување"),
    (r"only (\d+)% of normal yield in a dry year with (\w+) irrigation",
     lambda m: f"само {m[1]}% од нормалниот принос во сушна година со наводнување ({ {'drip': 'капка по капка', 'sprinkler': 'прскалки', 'furrow': 'бразди'}.get(m[2], m[2]) })"),
    (r"brings pests and soil diseases back sooner than what you grow now", "ги враќа штетниците и болестите во почвата побрзо од сегашниот плодоред"),
]
_compiled = [(re.compile("^" + p + "$"), r) for p, r in SENTENCES]


def sentence(s: str) -> str:
    for rx, rep in _compiled:
        m = rx.match(s)
        if m:
            return rep(m) if callable(rep) else m.expand(rep)
    return s


def summary(items: list[dict]) -> str:
    """Rebuild the soil health summary from the translated items (same rule as health.py)."""
    bad = [i for i in items if i["status"] != "good"]
    if not bad:
        return "Сите проверки се добри: " + ", ".join(i["title"].lower() for i in items) + "."
    return " ".join(f"{i['title']}: {i['text'].split(':')[0].rstrip('.').lower()}." for i in bad)


def live(d: dict) -> dict:
    h = d.get("health")
    if h:
        h["label"] = sentence(h["label"])
        for i in h.get("items", []):
            for k in ("title", "value", "text", "why"):
                i[k] = sentence(i[k])
        h["summary"] = summary(h["items"]) if h.get("items") else sentence(h.get("summary", ""))
    for a in d.get("alerts", []):
        a["title"], a["text"] = sentence(a["title"]), sentence(a["text"])
    return d


def rotations(d: dict) -> dict:
    for r in d.get("rotations", []):
        r["name"] = rotation_name(r["name"])
        r["idea"] = sentence(r.get("idea") or "")
        r["season_names"] = [words(s) for s in r.get("season_names", [])]
        c = r.get("card", {})
        for k in ("why", "benefits", "risks", "gaps"):
            c[k] = [sentence(x) for x in c.get(k, [])]
        for e in c.get("evidence", []):
            e["text"] = sentence(e["text"])
        for p in r.get("plant_next", []):
            for s in p["steps"]:
                s["name"] = words(s["name"])
                s["sow_month"] = MONTHS.get(s["sow_month"], s["sow_month"])
    for o in d.get("others", []) + d.get("not_offered", []):
        o["name"] = rotation_name(o["name"])
        if o.get("because"):
            o["because"] = sentence(o["because"])
    if d.get("soil", {}).get("name"):
        d["soil"]["name"] = soil_name(d["soil"]["name"])
    d["farm_type"] = {"vegetable": "зеленчук", "tobacco": "тутун", "field crop": "полски култури"}.get(d.get("farm_type"), d.get("farm_type"))
    return d
