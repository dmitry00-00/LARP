# sources.md — откуда это и живо ли оно ещё

Все обращения — **15.09.2026**, через WebSearch/WebFetch. Здесь — курированный
верх (то, на что опирается `SUMMARY.md`); полные списки с цитатами — в
`messy-notes/*.md`, разделы по источникам. Состояния: жив · за стеной ·
не открылся · мёртв · пуст.

| URL | что взяли | дата | состояние |
|---|---|---|---|
| `https://epicarmoury.com/products.json` | 1 866 товаров, поля Shopify; карточка RFB Defender: 75 см, 407 г, fiberglass, EVA+latex; дилеры 3 уровней | 15.09 | жив, JSON без ключа |
| `https://calimacil.com/products.json` | Shopify JSON, vendor/product_type, 9 брендов | 15.09 | жив |
| `https://www.dein-larp-shop.de/products.json` | 3 582 товара, без бренда/типа | 15.09 | жив |
| `https://kogda-igra.ru/api/` · `/api/changed/<ts>` · `/api/game/<id>` | документация; 1 000 записей за раз; 25 полей игры вкл. `vk_club`, `telegram_channel`, `players_count` | 15.09 | жив, проверен живьём |
| `https://www.olx.kz/api/v1/offers/?query=доспех` | 25 в data; «доспех» 69, «кольчуга» 23, «ларп» 2 (не ЛАРП) | 15.09 | жив, JSON без токена |
| `https://www.olx.ua/api/v1/offers/?query=larp` | 16 полных; HTML «ларп» 25 / «larp» 24 | 15.09 | жив, JSON без токена |
| `kufar.by` search-API | JSON с `total`; HTML — 403 | 15.09 | жив (API) |
| `https://www.kleinanzeigen.de/s-larp/k0` | «3.002 Ergebnissen für „larp"»; `/s-larp-waffen/k0` — 32 | 15.09 | жив, HTML без JS |
| `https://www.marktplaats.nl/l/hobby-en-vrije-tijd/kostuums-theaterbenodigdheden-en-larp/` | «2,424 advertenties»; `/q/larp/` 2 701, «294 additions this week», avg €71 | 15.09 | жив, HTML |
| `https://www.vinted.co.uk/catalog?search_text=larp` | «500+ results», £1–130 | 15.09 | жив (Next.js, листинги в HTML) |
| `https://www.gumtree.com/search?q=larp` | 5 объявлений | 15.09 | жив, ничтожно |
| `https://donjon.ru/category/bu/` | 12 позиций, коды продавцов, «Размер XL» | 15.09 | жив |
| `https://www.allrpg.info/exchange/` | «Склад»: 13 лотов, категории, города, без дат | 15.09 | жив, пуст |
| `https://github.com/alxgarshin/allrpg.info` | код портала open source с 30.09.2025, PHP 8.4 | 15.09 | жив |
| `https://wargearshop.ru` | меч ЛАРП 4 500–5 000 ₽, кинжал 2 500, щит 10 000, баклер 6 600 | 15.09 | жив, HTML (Storeland) |
| `mechiizpechi.orgs.biz` · `redfirm.orgs.biz` · `medieval-armor.orgs.biz` · `temirtumenkost.orgs.biz` | ПУ-меч 2 800–3 300 ₽, топор 5 000; щит на заказ 4 500 ₽ | 15.09 | живы, единый шаблон |
| `https://illium.ru` | меч+кинжал 3 800 ₽, ножны 2 800, наручи 1 000; «в порядке живой очереди» | 15.09 | жив (WooCommerce) |
| `https://arthammer.com.ua` | ПУ-доспех сеты 605–1 205 €, элементы 10–155 € | 15.09 | жив (OpenCart) |
| `https://medievallegends.ru` | прокат: латный комплект 10 000 ₽ + залог 20 000; меч 1 500–2 000 | 15.09 | жив |
| `https://zbroevy-falvarak.by` | единственная BY-мастерская с ЛАРП-разделом; цен нет | 15.09 | жив |
| `https://satu.kz` (щиты/катаны) | 58 150–83 776 ₸, сувенир | 15.09 | жив |
| `https://www.instagram.com/alarpg/` | Алматинский Клуб Ролевых Игр, 2 246 подписчиков | 15.09 | жив (публичный профиль) |
| `https://t.me/s/larp_bugle` | «Ролевой Горн», 1.45K, анонсы игр 300–1 000+ | 15.09 | жив, `t.me/s/` рендерит |
| `https://t.me/baraholka_ri` · `@gde_prikid` | резолвятся; чаты, численность не видна | 15.09 | существуют, активность не подтверждена |
| `https://tentaculus.ru/telegram.html` | каталог 88 чатов, «Дата обновления: 11.12.2019» | 15.09 | жив, данные 2019 |
| `https://t-j.ru/roleplay/` | Т—Ж 18.02.2021: три VK-барахолки (Rolesales, Единый рынок, Косплей-барахолка) | 15.09 | жив |
| `vk.com/public79045997` · `public120606878` · `cosplay_second` · `alarpg_club` · `vk.ru/@claws_and_lilies-dospehi-i-oruzhie` | названия и назначение по выдаче; статья — 9 мастерских | 15.09 | за стеной (vk.com инструменту недоступен; статья открылась через m.vk.ru) |
| `https://warhammerlarp.ru/wiki/правила-по-допуску-оружия-ближнего-бо/` | 30 Шор A, клинок ≤2 м, 800 г/м, ≤2 000 г, щит ≤6 кг/м² | 15.09 | жив |
| `https://takeularp.ru/adventura-boyovka` | «Адвентура» 2025.12.08-1: ≤110/200/250 см, лук ≤15 кг, наконечник ≥5 см ≤20 Шор A | 15.09 | жив |
| `http://larpwitcher.ru/Правила-по-техдопуску-оружия/` | — | 15.09 | мёртв (DNS) |
| Empire wiki (Profound Decisions) | 9 классов длины, <30 lbs @ 28", head ≥50 мм, щит ≥6 мм | 15.09 | жив (MediaWiki) |
| `dagorhir.wiki` · `geddon.org` | hole test 2.5"/2", Blue 12–<48", Red ≥48" | 15.09 | живы |
| `https://gmrpg.ru/calendar` | 9 493 события, фильтр «Казахстан», экспорта нет | 15.09 | жив |
| `larpkalender.de` (12 078 событий) · `.ch` (iCal) · `kalender.larp.at` (RSS+ICS) | календари EN | 15.09 | живы |
| `https://docs.joinrpg.ru/ru/latest/api/api-docs.html` | API «только людям с мастерскими правами»; расписание — `.ics` | 15.09 | жив |
| `mytholon.com` · `larpdistribution.com` · `andracor.com` · `wyvern-larpshop.de` · `larp-fashion.de` · `larpinn.co.uk` | номенклатура брендов (Mytholon 1 488, House of Warfare 435, Burgschneider 216) | 15.09 | живы, HTML |
| `rpg.ru/shop` · `qadviser.ru` · `forum.manor.ru` · `krm-krom.ucoz.ru` | каталоги мастеров | 15.09 | мёртвы (сертификат/TLS/2011) |
| `avito.ru` · `youla.ru` · `livemaster.ru` · `rolemarket.ru` · `wildberries.ru` · `ozon.ru` · `tgstat.ru` · `telemetr.io` · `reddit.com` · `ebay.*` · `etsy.com` | — | 15.09 | не открылись (antibot / SPA / 403) |
| `larpperm.ru` · `artelers.ru` · `rolevik.org` · `rpg.by` | — | 15.09 | мёртвы / 403 |
