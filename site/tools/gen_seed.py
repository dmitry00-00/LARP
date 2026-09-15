#!/usr/bin/env python3
# gen_seed.py — генератор демо-корпуса для site/
#
# Зачем скрипт, а не рукописный файл: корпус нужен воспроизводимый и
# помеченный как синтетический. Дом. правило проекта — «число без даты —
# враньё»: здесь все числа сгенерированы, и это написано прямо в данных
# (meta.synthetic = true), чтобы ни один отчёт не сослался на них как на рынок.
#
# Запуск:  python3 site/tools/gen_seed.py
# Пишет:   site/data/feed.json   — контракт фида (его будет писать парсер)
#          site/seed.js          — тот же корпус как window.HMB_SEED (для file://)

import json, os, math, datetime

SEED = 20260905
class R:
    """LCG — детерминированный, чтобы корпус не менялся между прогонами."""
    def __init__(s, seed): s.x = seed
    def next(s): s.x = (s.x * 1103515245 + 12345) % (2**31); return s.x
    def rand(s): return s.next() / (2**31)
    def i(s, a, b): return a + int(s.rand() * (b - a + 1))
    def pick(s, xs): return xs[s.i(0, len(xs) - 1)]
    def chance(s, p): return s.rand() < p
    def weighted(s, pairs):
        tot = sum(w for _, w in pairs); r = s.rand() * tot
        for v, w in pairs:
            r -= w
            if r <= 0: return v
        return pairs[-1][0]

R_ = R(SEED)
TODAY = datetime.date(2026, 9, 5)

# ────────────────────────────── справочники ──────────────────────────────

SLOTS = [
  # id, ru, короткое, зоны, слой, обмеры, базовая цена ₽ (от, до)
  ("helm",       "Шлем",             "ШЛЕМ",   ["head"],                                   3, ["head"],  35000, 95000),
  ("aventail",   "Авентейл",         "АВЕНТ.", ["neck","shoulderL","shoulderR"],           2, [],         9000, 28000),
  ("gorget",     "Ожерелье",         "ГОРЖЕТ", ["neck"],                                   3, ["neck"],   8000, 22000),
  ("gambeson",   "Поддоспешник",     "ПОДДОС", ["chest","waist","upperArmL","upperArmR"],  1, ["chest"],  6000, 22000),
  ("haubergeon", "Кольчуга",         "КОЛЬЧ.", ["chest","waist","groin"],                  2, ["chest"], 25000, 85000),
  ("cuirass",    "Кираса / КП",      "КИРАСА", ["chest"],                                  3, ["chest"], 30000,110000),
  ("fauld",      "Тассеты",          "ТАССЕТ", ["waist","groin"],                          3, ["waist"],  9000, 26000),
  ("pauldron",   "Наплечники",       "ПЛЕЧИ",  ["shoulderL","shoulderR"],                  3, [],        14000, 34000),
  ("rerebrace",  "Наручи",           "НАРУЧИ", ["upperArmL","upperArmR"],                  3, ["arm"],   18000, 48000),
  ("couter",     "Налокотники",      "ЛОКТИ",  ["elbowL","elbowR"],                        3, [],         6000, 16000),
  ("vambrace",   "Поручи",           "ПРЕДПЛ", ["forearmL","forearmR"],                    3, ["arm"],    7000, 18000),
  ("gauntlet",   "Латные перчатки",  "ПЕРЧАТ", ["handL","handR"],                          3, [],        16000, 45000),
  ("cuisse",     "Набедренники",     "БЁДРА",  ["thighL","thighR"],                        3, ["thigh"], 15000, 40000),
  ("poleyn",     "Наколенники",      "КОЛЕНИ", ["kneeL","kneeR"],                          3, [],         7000, 20000),
  ("greave",     "Поножи",           "ГОЛЕНИ", ["shinL","shinR"],                          3, ["shin"],  12000, 32000),
  ("sabaton",    "Сабатоны",         "СТОПЫ",  ["footL","footR"],                          3, ["foot"],   9000, 24000),
  ("weapon",     "Оружие",           "ОРУЖ.",  [],                                         0, [],        18000, 70000),
  ("shield",     "Щит",              "ЩИТ",    [],                                         0, [],         6000, 20000),
]

ALIASES = {
  "helm":["шлем","бацинет","хундсгугель","армет","салад","шишак","hounskull","bascinet","sallet","helmet"],
  "aventail":["авентейл","бармица","aventail","camail"],
  "gorget":["горжет","ожерелье","бевор","gorget","bevor"],
  "gambeson":["поддоспешник","гамбезон","акетон","стёганка","gambeson","aketon"],
  "haubergeon":["кольчуга","хауберк","хаубержон","байдана","mail","haubergeon","hauberk"],
  "cuirass":["кираса","кп","корпус","бригандина","нагрудник","breastplate","cuirass","coat of plates"],
  "fauld":["тассеты","юбка","набрюшник","fauld","tassets"],
  "pauldron":["наплечники","плечи","оплечья","эполеты","spaulders","pauldrons"],
  "rerebrace":["наручи","верх руки","rerebrace","upper arm"],
  "couter":["налокотники","локти","couters","elbows"],
  "vambrace":["поручи","предплечья","vambraces"],
  "gauntlet":["перчатки","рукавицы","митенки","латные перчатки","gauntlets","mittens"],
  "cuisse":["набедренники","бёдра","cuisses"],
  "poleyn":["наколенники","колени","poleyns"],
  "greave":["поножи","голени","greaves"],
  "sabaton":["сабатоны","сапоги латные","стопы","sabatons"],
  "weapon":["меч","топор","алебарда","булава","тесак","фальшион","sword","axe"],
  "shield":["щит","павеза","баклер","shield","buckler"],
}

ARCHETYPES = [
  ("ck14","Чешский рыцарь","Богемия",1370,1400,"bi","hmb",
   "Полный латный комплекс позднего XIV в., пражская и нюрнбергская плате.",
   ["helm","aventail","gambeson","haubergeon","cuirass","pauldron","rerebrace","couter","vambrace","gauntlet","cuisse","poleyn","greave","sabaton"]),
  ("de15","Немецкий готический","Германия",1450,1490,"bi","hmb",
   "Готический доспех, рифлёные поверхности, максимальная подвижность.",
   ["helm","gorget","gambeson","cuirass","fauld","pauldron","rerebrace","couter","vambrace","gauntlet","cuisse","poleyn","greave","sabaton"]),
  ("it14","Итальянский латник","Италия",1370,1410,"imcf","hmb",
   "Миланская школа: крупные пластины, асимметричная защита рук.",
   ["helm","aventail","gambeson","haubergeon","cuirass","pauldron","rerebrace","couter","vambrace","gauntlet","cuisse","poleyn","greave","sabaton"]),
  ("pl15","Польский копейщик","Польша",1410,1450,"bi","hmb",
   "Грюнвальдский горизонт, смешение немецкой плате и местных традиций.",
   ["helm","gorget","gambeson","haubergeon","cuirass","fauld","pauldron","rerebrace","couter","vambrace","gauntlet","cuisse","poleyn","greave"]),
  ("tk13","Тевтонский рыцарь","Пруссия",1230,1270,"club","reenact",
   "Кольчужный комплекс с топхельмом, ранняя пластина на конечностях.",
   ["helm","haubergeon","gambeson","couter","poleyn","gauntlet","greave"]),
  ("st13","Степной конник","Степь",1240,1350,"club","reenact",
   "Ордынский комплекс: ламелляр, куяк, шлем с бармицей, конная служба.",
   ["helm","aventail","gambeson","haubergeon","cuirass","rerebrace","vambrace","cuisse","greave"]),
  ("ru12","Русский дружинник","Русь",1150,1250,"club","reenact",
   "Кольчуга, наручи, шелом с бармицей, миндалевидный щит.",
   ["helm","aventail","gambeson","haubergeon","vambrace","poleyn","shield"]),
  ("vk10","Викинг","Скандинавия",900,1050,"club","reenact",
   "Кольчуга или стёганка, шлем норманнского типа, круглый щит.",
   ["helm","gambeson","haubergeon","vambrace","shield","weapon"]),
]

REGIONS = ["Богемия","Германия","Нюрнберг","Италия","Милан","Польша","Пруссия",
           "Скандинавия","Степь","Русь","Англия","Франция","Венгрия"]

CITIES = [
  ("Алматы","KZ",0.10),("Астана","KZ",0.07),("Караганда","KZ",0.03),("Шымкент","KZ",0.02),
  ("Бишкек","KG",0.03),("Ташкент","UZ",0.02),
  ("Москва","RU",0.13),("СПб","RU",0.09),("Казань","RU",0.04),("Екатеринбург","RU",0.04),
  ("Новосибирск","RU",0.03),("Тверь","RU",0.03),("Псков","RU",0.02),("Калининград","RU",0.02),
  ("Минск","BY",0.07),("Брест","BY",0.02),
  ("Киев","UA",0.04),("Львов","UA",0.03),
  ("Прага","CZ",0.05),("Брно","CZ",0.03),("Варшава","PL",0.03),("Краков","PL",0.02),
  ("Милан","IT",0.02),("Нюрнберг","DE",0.02),
]

MAKERS = [
  ("m-01","Мастерская Жихаря","RU","Москва",70,True,["helm","cuirass","cuisse"],4.9,True),
  ("m-02","Forge Brünn","CZ","Брно",120,False,["cuirass","greave","gauntlet"],4.8,True),
  ("m-03","Кузница «Чёрный Ворон»","RU","СПб",90,True,["rerebrace","couter","vambrace"],4.6,True),
  ("m-04","Ferrum Werk","BY","Минск",45,True,["gauntlet","cuisse","poleyn"],4.7,True),
  ("m-05","Officina Visconti","IT","Милан",150,False,["sabaton","pauldron","helm"],4.9,True),
  ("m-06","MailWorks","RU","Тверь",30,True,["haubergeon","aventail"],4.5,True),
  ("m-07","Дала-Темир","KZ","Алматы",35,True,["helm","haubergeon","cuirass"],4.4,True),
  ("m-08","Швейная Прага","CZ","Прага",21,True,["gambeson"],4.8,True),
  ("m-09","Сталь и Лён","RU","Казань",60,True,["gambeson","haubergeon"],4.3,False),
  ("m-10","Nürnberger Platte","DE","Нюрнберг",180,False,["cuirass","pauldron","fauld"],5.0,True),
  ("m-11","Kraków Armoury","PL","Краков",100,True,["helm","gorget","cuirass"],4.6,True),
  ("m-12","Кузня «Тумен»","KZ","Астана",40,True,["helm","haubergeon","cuisse"],4.2,False),
  ("m-13","Lviv Steel","UA","Львов",75,True,["greave","sabaton","poleyn"],4.7,True),
  ("m-14","Белая Ковка","BY","Брест",50,True,["couter","vambrace","gauntlet"],4.4,False),
  ("m-15","Уральский Доспех","RU","Екатеринбург",55,True,["cuirass","cuisse","greave"],4.5,True),
  ("m-16","Steppe Forge","KG","Бишкек",45,True,["helm","aventail","haubergeon"],4.1,False),
  ("m-17","Officina Sarmatia","PL","Варшава",110,False,["pauldron","rerebrace"],4.6,True),
  ("m-18","Мастерская Ивана Гончара","UA","Киев",85,True,["weapon","shield"],4.8,True),
  ("m-19","Novgorod Mail","RU","Псков",38,True,["haubergeon","aventail"],4.3,False),
  ("m-20","Almaty Leather & Steel","KZ","Алматы",25,True,["gambeson","shield","fauld"],4.0,False),
]

SOURCES = [
  ("tg-isb",   "tg",    "@isb_baraholka",        "Telegram"),
  ("tg-rekon", "tg",    "@rekon_market",         "Telegram"),
  ("tg-kz",    "tg",    "@steppe_armour_kz",     "Telegram"),
  ("tg-buhurt","tg",    "@buhurt_flea",          "Telegram"),
  ("vk-market","vk",    "vk.com/rekon_market",   "VK"),
  ("vk-isb",   "vk",    "vk.com/isb_kupliprodam","VK"),
  ("forum-lh", "forum", "livinghistory.ru",      "Форум"),
  ("shop-dj",  "shop",  "donjon.ru",             "Магазин"),
  ("shop-me",  "shop",  "medievalextreme.com",   "Магазин"),
  ("shop-wg",  "shop",  "wargearshop.ru",        "Магазин"),
  ("manual",   "manual","добавлено вручную",     "Вручную"),
]

CURRENCIES = {"RUB":"₽","KZT":"₸","USD":"$","EUR":"€","UAH":"грн","BYN":"Br"}
# ⚠ курс — ЗАГЛУШКА. Реальный фид курсов не подключён; в интерфейсе это помечено.
RATES_STUB = {"RUB":1.0,"KZT":0.093,"USD":95.0,"EUR":103.0,"UAH":2.3,"BYN":29.0}
CUR_BY_COUNTRY = {"KZ":"KZT","KG":"KZT","UZ":"KZT","RU":"RUB","BY":"BYN","UA":"UAH",
                  "CZ":"EUR","PL":"EUR","IT":"EUR","DE":"EUR"}

TITLES = {
 "helm":["Бацинет с авентейлом","Бацинет «свиное рыло»","Бацинет купольный","Хундсгугель",
         "Салад немецкий","Армет ранний","Топхельм","Шелом с бармицей","Шишак степной","Капеллина"],
 "aventail":["Авентейл клёпаный","Бармица кольчужная","Авентейл на вервелях"],
 "gorget":["Горжет пластинчатый","Бевор откидной","Ожерелье сегментное"],
 "gambeson":["Гамбезон стёганый, лён","Поддоспешник короткий рукав","Акетон плотный",
             "Гамбезон 12 слоёв","Стёганка под кольчугу"],
 "haubergeon":["Хауберк клёпаный, плоское кольцо","Хауберк лужёный","Кольчуга до колена",
               "Байдана клёпаная","Хаубержон короткий","Кольчуга смешанного плетения"],
 "cuirass":["Кираса с подвесом для тассетов","КП на тканевой основе","Кираса с тассетами",
            "Бригандина клёпаная","Кираса рифлёная","Ламелляр степной","Куяк пластинчатый"],
 "fauld":["Тассеты сегментные","Юбка латная","Набрюшник с подвесом"],
 "pauldron":["Наплечники сегментные","Наплечники с крылом","Оплечья ламеллярные","Эполеты малые"],
 "rerebrace":["Наручи створчатые","Руки комплект: наручи · локти · поручи","Наручи сегментные"],
 "couter":["Налокотники со створками","Локти с крылом","Налокотники малые"],
 "vambrace":["Поручи створчатые","Предплечья пластинчатые","Поручи с шарниром"],
 "gauntlet":["Латные перчатки «песочные часы»","Митенки сегментные","Перчатки пальчатые",
             "Рукавицы латные","Перчатки с манжетом"],
 "cuisse":["Набедренники с тассетами","Набедренники короткие","Бёдра ламеллярные"],
 "poleyn":["Наколенники со створками","Наколенники с боковыми крыльями","Колени малые"],
 "greave":["Поножи створчатые","Поножи закрытые с шарниром","Поножи半 открытые"],
 "sabaton":["Сабатоны чешуйчатые","Сабатоны узкий мысок","Сабатоны пластинчатые"],
 "weapon":["Меч одноручный XIIIa","Полутораручный меч XVa","Тесак боевой","Топор бородовидный",
           "Алебарда","Булава шестопёр","Сабля ордынская"],
 "shield":["Щит миндалевидный","Павеза пехотная","Баклер стальной","Щит круглый норманнский"],
}

PERIOD_LABELS = [
  ("IX–XI вв.",900,1100),("X в.",900,1000),("к. X в.",970,1000),
  ("XI в.",1000,1100),("XII в.",1100,1200),("XII–XIII вв.",1100,1300),
  ("сер. XIII в.",1230,1270),("XIII в.",1200,1300),("XIII–XIV вв.",1200,1400),
  ("н. XIV в.",1300,1330),("XIV в.",1300,1400),("сер. XIV в.",1330,1370),
  ("к. XIV в.",1370,1400),("ок. 1370",1360,1380),("ок. 1380",1370,1390),
  ("ок. 1390",1380,1400),("ок. 1380–1400",1380,1400),
  ("н. XV в.",1400,1430),("XV в.",1400,1500),("сер. XV в.",1430,1470),
  ("к. XV в.",1470,1500),("ок. 1450",1440,1460),("ок. 1470",1460,1480),
]

def body_for(slot_id, measures_keys, r):
    m = {}
    if "head"  in measures_keys: lo = r.i(54,60); m["head"]=[lo,lo+r.i(2,3)]
    if "neck"  in measures_keys: lo = r.i(36,42); m["neck"]=[lo,lo+r.i(2,4)]
    if "chest" in measures_keys: lo = r.i(92,116); m["chest"]=[lo,lo+r.i(6,12)]
    if "waist" in measures_keys: lo = r.i(78,104); m["waist"]=[lo,lo+r.i(6,10)]
    if "arm"   in measures_keys: lo = r.i(56,68); m["arm"]=[lo,lo+r.i(3,5)]
    if "thigh" in measures_keys: lo = r.i(50,66); m["thigh"]=[lo,lo+r.i(4,7)]
    if "shin"  in measures_keys: lo = r.i(36,46); m["shin"]=[lo,lo+r.i(3,5)]
    if "foot"  in measures_keys: lo = r.i(39,46); m["foot"]=[lo,lo+r.i(1,2)]
    return m

def pick_city(r):
    tot = sum(w for _,_,w in CITIES); x = r.rand()*tot
    for c,co,w in CITIES:
        x -= w
        if x <= 0: return c,co
    return CITIES[0][0], CITIES[0][1]

def iso(days_ago):
    return (TODAY - datetime.timedelta(days=days_ago)).isoformat()

# ────────────────────────────── генерация ──────────────────────────────

lots, wants, services = [], [], []
slot_by_id = {s[0]: s for s in SLOTS}

N_OFFERS = 236
for n in range(N_OFFERS):
    r = R_
    sid, ru, short, zones, layer, mkeys, p_lo, p_hi = r.weighted([
      (s, {"helm":1.4,"cuirass":1.3,"gauntlet":1.1,"haubergeon":1.0,"gambeson":1.0,
           "greave":0.9,"sabaton":0.8,"cuisse":0.9,"poleyn":0.9,"pauldron":0.9,
           "rerebrace":0.9,"couter":0.7,"vambrace":0.7,"weapon":1.0,"shield":0.6,
           "aventail":0.5,"gorget":0.5,"fauld":0.5}[s[0]]) for s in SLOTS])
    label, yf, yt = r.pick(PERIOD_LABELS)
    cond = r.weighted([("new",0.34),("used",0.55),("damaged",0.11)])
    base = p_lo + r.rand()*(p_hi-p_lo)
    mult = 1.0 if cond=="new" else (0.45+r.rand()*0.35 if cond=="used" else 0.22+r.rand()*0.23)
    rub = base*mult
    city, country = pick_city(r)
    cur = CUR_BY_COUNTRY.get(country,"RUB")
    if r.chance(0.25): cur = "RUB"
    price = rub / RATES_STUB[cur]
    price = round(price / (100 if cur in ("RUB","KZT","UAH") else 5)) * (100 if cur in ("RUB","KZT","UAH") else 5)
    has_measures = r.chance(0.62 if cond!="new" else 0.78)
    measures = body_for(sid, mkeys, r) if has_measures else {}
    steel = None
    if layer == 3 and r.chance(0.7): steel = r.pick([1.0,1.2,1.5,1.8,2.0,2.5])
    src_id, src_kind, src_ref, src_label = r.pick(SOURCES)
    age = r.weighted([(r.i(0,7),0.34),(r.i(8,21),0.30),(r.i(22,45),0.22),(r.i(46,120),0.14)])
    mk = r.pick(MAKERS) if r.chance(0.72) else None
    lots.append({
      "id": f"o-{n+1:04d}", "dir": "offer", "slot": sid,
      "title": r.pick(TITLES[sid]),
      "period": label, "yearFrom": yf, "yearTo": yt,
      "region": r.pick(REGIONS), "condition": cond,
      "price": int(price), "currency": cur,
      "city": city, "country": country,
      "measures": measures, "steelMm": steel,
      "weightG": int(400 + r.rand()*11000) if layer in (2,3) else None,
      "photos": r.weighted([(0,0.18),(r.i(1,3),0.42),(r.i(4,9),0.40)]),
      "maker": mk[0] if mk else None,
      "source": src_id, "sourceRef": src_ref,
      "postedAt": iso(age), "age": age,
      "provenance": r.chance(0.22),
      "status": "stale" if age > 60 else "active",
    })

N_WANTS = 78
URG = ["турнир 12.10","турнир 26.10","срочно","сломал на турнире","к сборам","до конца месяца"]
for n in range(N_WANTS):
    r = R_
    sid, ru, short, zones, layer, mkeys, p_lo, p_hi = r.weighted([
      (s, {"gauntlet":1.7,"sabaton":1.5,"greave":1.3,"helm":1.2,"cuirass":1.1,
           "poleyn":1.1,"gambeson":1.0,"haubergeon":0.9,"cuisse":0.9,"pauldron":0.9,
           "rerebrace":0.8,"couter":0.7,"vambrace":0.7,"weapon":0.7,"shield":0.4,
           "aventail":0.4,"gorget":0.4,"fauld":0.4}[s[0]]) for s in SLOTS])
    label, yf, yt = r.pick(PERIOD_LABELS)
    city, country = pick_city(r)
    cur = CUR_BY_COUNTRY.get(country,"RUB")
    budget_rub = (p_lo + r.rand()*(p_hi-p_lo)) * (0.5 + r.rand()*0.45)
    budget = budget_rub / RATES_STUB[cur]
    budget = round(budget / (100 if cur in ("RUB","KZT","UAH") else 5)) * (100 if cur in ("RUB","KZT","UAH") else 5)
    need = {}
    if mkeys and r.chance(0.72):
        b = body_for(sid, mkeys, r)
        for k, v in b.items(): need[k] = v[0] + 1
    src_id, src_kind, src_ref, src_label = r.pick(SOURCES[:7])
    age = r.weighted([(r.i(0,6),0.42),(r.i(7,20),0.33),(r.i(21,60),0.25)])
    wants.append({
      "id": f"w-{n+1:04d}", "dir": "want", "slot": sid,
      "title": f"Ищу: {r.pick(TITLES[sid]).lower()}",
      "period": label, "yearFrom": yf, "yearTo": yt,
      "region": r.pick(REGIONS + ["любой","любой","любой"]),
      "condition": r.weighted([("any",0.5),("used",0.34),("new",0.16)]),
      "price": int(budget), "currency": cur,
      "city": city, "country": country,
      "need": need, "urgency": r.pick(URG) if r.chance(0.24) else None,
      "source": src_id, "sourceRef": src_ref,
      "postedAt": iso(age), "age": age,
      "status": "closed" if age > 45 else "active",
    })

SVC = [
 ("repair","Правка вмятин и переклёпка узлов",["cuirass","helm","pauldron","greave"],4000,14000,3,10),
 ("repair","Ремонт шлема после турнира",["helm"],4000,12000,3,10),
 ("repair","Замена ремней и пряжек по комплекту",["*"],2000,6000,1,4),
 ("refit","Подгонка чужой кирасы под фигуру",["cuirass"],8000,20000,7,21),
 ("refit","Перешив поддоспешника под обмеры",["gambeson"],3000,9000,4,12),
 ("refit","Перекрой наручей под длину руки",["rerebrace","vambrace"],5000,13000,5,14),
 ("refit","Расклёпка и подгонка кольчуги",["haubergeon"],4000,11000,4,12),
 ("custom","Ковка кирасы по обмерам",["cuirass"],55000,120000,90,180),
 ("custom","Шлем на заказ по иконографии",["helm"],45000,110000,60,150),
 ("custom","Сабатоны по слепку стопы",["sabaton"],18000,38000,90,160),
 ("custom","Комплект руки целиком",["rerebrace","couter","vambrace"],30000,70000,60,120),
 ("consumable","Ремни, пряжки, вкладыши — комплект",["*"],2000,6000,1,5),
 ("consumable","Кольцо клёпаное на ремонт кольчуги",["haubergeon"],900,3000,1,5),
 ("consumable","Подшлемник и амортизация",["helm"],2500,7000,2,7),
 ("consumable","Заклёпки и шайбы, 200 шт",["*"],1200,3500,1,4),
 ("appraisal","Оценка б/у: толщина, трещины, допуск",["*"],1500,5000,1,3),
 ("appraisal","Проверка комплекта на допуск к боям",["*"],3000,9000,1,5),
 ("logistics","Консолидация и доставка ЕАЭС, до 30 кг",["*"],8000,22000,7,18),
 ("logistics","Доставка из ЕС в Казахстан",["*"],14000,40000,12,30),
 ("rent","Аренда комплекта на турнир",["*"],9000,25000,1,3),
]
for n in range(34):
    r = R_
    kind, title, scope, p_lo, p_hi, d_lo, d_hi = r.pick(SVC)
    mk = r.pick(MAKERS)
    cur = CUR_BY_COUNTRY.get(mk[2],"RUB")
    price = (p_lo + r.rand()*(p_hi-p_lo)) / RATES_STUB[cur]
    price = round(price / (100 if cur in ("RUB","KZT","UAH") else 5)) * (100 if cur in ("RUB","KZT","UAH") else 5)
    age = r.i(0, 60)
    services.append({
      "id": f"s-{n+1:04d}", "dir": "service", "kind": kind, "title": title,
      "scope": scope, "slot": None if scope[0]=="*" else scope[0],
      "price": int(price), "currency": cur,
      "days": r.i(d_lo, d_hi), "maker": mk[0],
      "city": mk[3], "country": mk[2], "remote": r.chance(0.6),
      "source": r.pick(["shop-dj","tg-isb","vk-market","forum-lh","manual"]),
      "postedAt": iso(age), "age": age, "status": "active",
    })

feed = {
  "meta": {
    "generated": TODAY.isoformat(),
    "generator": "site/tools/gen_seed.py",
    "seed": SEED,
    "synthetic": True,
    "note": "ДЕМО-КОРПУС. Сгенерирован скриптом, к рынку отношения не имеет. "
            "Реальный фид пишет парсер; контракт полей — этот же файл.",
    "ratesStub": True,
    "ratesNote": "Курсы — заглушка, фид курсов не подключён (docs/DOMAIN_MODEL.md §1).",
    "counts": {"offers": len(lots), "wants": len(wants), "services": len(services)},
  },
  "rates": RATES_STUB,
  "currencies": CURRENCIES,
  "slots": [{"id":s[0],"label":s[1],"short":s[2],"zones":s[3],"layer":s[4],
             "measures":s[5],"aliases":ALIASES.get(s[0],[])} for s in SLOTS],
  "archetypes": [{"id":a[0],"title":a[1],"region":a[2],"yearFrom":a[3],"yearTo":a[4],
                  "ruleset":a[5],"discipline":a[6],"blurb":a[7],"required":a[8]} for a in ARCHETYPES],
  "makers": [{"id":m[0],"title":m[1],"country":m[2],"city":m[3],"leadDays":m[4],
              "queueOpen":m[5],"spec":m[6],"rating":m[7],"verified":m[8]} for m in MAKERS],
  "sources": [{"id":s[0],"kind":s[1],"ref":s[2],"label":s[3]} for s in SOURCES],
  "lots": lots + wants + services,
}

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.makedirs(os.path.join(root, "data"), exist_ok=True)
with open(os.path.join(root, "data", "feed.json"), "w", encoding="utf-8") as f:
    json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))
with open(os.path.join(root, "seed.js"), "w", encoding="utf-8") as f:
    f.write("/* seed.js — сгенерирован site/tools/gen_seed.py, не править руками.\n"
            "   Нужен, чтобы страница работала из file:// (fetch туда не ходит).\n"
            "   Данные синтетические: feed.meta.synthetic = true. */\n")
    f.write("window.HMB_SEED=")
    json.dump(feed, f, ensure_ascii=False, separators=(",", ":"))
    f.write(";\n")

print(f"offers={len(lots)} wants={len(wants)} services={len(services)}")
print("feed.json:", os.path.getsize(os.path.join(root,"data","feed.json")), "байт")
print("seed.js  :", os.path.getsize(os.path.join(root,"seed.js")), "байт")
