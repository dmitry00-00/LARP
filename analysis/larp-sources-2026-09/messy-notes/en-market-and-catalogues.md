# Англоязычный контур и структурированные источники — сырая заметка

Дата всех обращений: **15.09.2026**. Инструменты: только WebSearch и WebFetch.
Ничего не обходил: отказы (403 / DNS / login wall) помечены как есть.

Важная оговорка про метод: WebFetch отдаёт страницу как markdown, теги
`<script>` вырезаются. Поэтому «JSON-LD не виден» в этой заметке означает
«не виден через WebFetch», а НЕ «его нет». Проверять наличие schema.org
Product надо отдельным прогоном с сырым HTML — это в «Сомнительное».

Структура: 1 — второй рынок (б/у); 2 — каталоги новых товаров; 3 — правила
безопасности оружия; 4 — календари; 5 — отрицательные результаты;
6 — сомнительное; 7 — сводка по доступности.

---

## 1. Второй рынок (б/у)

### 1.1 Reddit

**r/LARP** — https://www.reddit.com/r/LARP/
- тип: сабреддит, общий (не торговый); страна — международный, англ.
- состояние: **недоступно через WebFetch, 15.09.2026** — и `www.reddit.com`,
  и `old.reddit.com`, и `/about.json` отвечают «Claude Code is unable to
  fetch from www.reddit.com». JSON-доступ (`.json`-суффикс) существует у
  Reddit как платформы, но проверить флейры/правила r/LARP напрямую не
  удалось.
- объём (косвенно, через сторонний индексатор reddapi.dev,
  https://reddapi.dev/subreddits/larp/insights): «66,740 subscribers»,
  «458 analyzed records», создан «March 15, 2010». Описание сабреддита
  оттуда же: «LARP (Live Action Role Playing) related content. This
  includes LARPs across the globe, LARPing gear, how-to guides, questions
  and ideas related to LARPing, articles and links, and anything else LARP.»
- флейры купли-продажи: **не подтверждены**. Поиск `site:reddit.com r/LARP
  "for sale" OR "WTS"` вернул только eBay/Walmart — ноль тредов Reddit в
  выдаче. Отдельные сабреддиты r/larpmarket / r/LARPexchange / r/LARPgear
  поиском не найдены (ни одного результата с reddit.com).
- вывод: Reddit как источник б/у-объявлений — **не подтверждён**; как
  источник вообще — нужен прогон с другого инструмента (JSON API Reddit
  требует OAuth-приложение с 2023 г.).

### 1.2 Facebook-группы (все — за стеной входа)

Все URL ниже при WebFetch отдают только форму логина («Электронный адрес
или номер мобильного телефона» / «Познакомьтесь с тем, что вам нравится»).
Названия — из выдачи WebSearch; размер участников **нигде не виден**.

| Название (как в выдаче) | URL | Регион по названию |
|---|---|---|
| USA LARP Buy Sell & Trade | https://www.facebook.com/groups/196542430531981/ | США |
| International LARP Buy Swap Sell | https://www.facebook.com/groups/LARPbuyswapsell/ | междунар. |
| LARP SWAPS, SALES & PART EXCHANGES | https://www.facebook.com/groups/102396143274251/ | (по выдаче — UK) |
| Buy & Sell LARP UK | https://www.facebook.com/groups/160076880845079/ | UK |
| UK LARP KIT | https://www.facebook.com/groups/289666864462656/ | UK |
| Mittelalter/Larp Flohmarkt Deutschland (D,A,CH) | https://www.facebook.com/groups/715173501975419/ | DE/AT/CH |
| LARP Flohmarkt | https://www.facebook.com/groups/340847742625036/ | DE (по названию) |
| Larp Basar (страница, «Mühlen Eichsen») | https://www.facebook.com/larpbasar/ | DE — по выдаче это магазин-посредник, не б/у |
| LARP Place (страница) | https://www.facebook.com/LarpPlace/ | ? |

Также в выдаче: пост «Where to sell LARP gear and equipment?»
(https://www.facebook.com/groups/6096034195/posts/10166508032979196/) —
группа с id 6096034195, название не видно.

Доступность для парсера: **за логином, парсить нельзя**; Graph API для
чужих групп закрыт с 2018 г. Единственный законный путь — ручной опрос
владельцем или оператором со своим аккаунтом.

### 1.3 eBay

- Категория США: **eBay category 43217** «LARP/Reenactment Collectible
  Armor & Shields», browse-node `bn_73457539`;
  https://www.ebay.com/b/LARP-Reenactment-Collectible-Armor-Shields/43217/bn_73457539
  Дочерние узлы по выдаче: `bn_99582947` Gauntlet/Glove, `bn_7111953315`
  Medieval, `bn_73457748` Original, `bn_99582922` Collectible Armors,
  `bn_73457585` Reproduction, `bn_96930162` Spartan, `bn_73457731` Steel
  Reproduction, `bn_73457502` Full Body Armors, `bn_73457356` Steel
  Ambidextrous.
- Категория DE: «LARP- & Reenactment-Rüstzeug Rüstung», категория 49178,
  `bn_12951665`: https://www.ebay.de/b/LARP-Reenactment-Rustzeug-Rustung/49178/bn_12951665
- Категория UK: «LARP Armour» https://www.ebay.co.uk/b/bn_55196818
- Состояние: **все три страницы — HTTP 403 при WebFetch, 15.09.2026**
  (antibot). Число лотов не получено.
- Отдельного узла «LARP weapons» в выдаче нет — оружие идёт запросом
  (в выдаче: «LARP Weapon Viking Sword 95cm…», «Foam and Latex Bendable
  Roman Spatha Sword…», ebay.de «Dunkelelfen Kriegsaxt LARP Waffe aus
  sicherem Latex & Schaum…»). Продавец-магазин в выдаче: ebay.com/usr/wonleith.
- API: **eBay Browse API** (`item_summary/search`, параметры `q`,
  `category_ids` — «currently you can pass in only one category ID per
  request»). Нужен Application access token (client credentials). Лимит
  по выдаче сообщества: «Browse API has a limit of 5,000 calls per day»,
  на уровне приложения, повышение — через «Application Growth Check».
  Страница docs https://developer.ebay.com/api-docs/buy/static/api-browse.html
  — **403 при WebFetch**. Маркетплейс задаётся заголовком
  `X-EBAY-C-MARKETPLACE-ID` (EBAY_US / EBAY_DE / EBAY_GB) — это из общих
  знаний об API, в выдаче 15.09 не процитировано.
- Вывод: eBay — единственный крупный б/у-источник с официальным API и
  готовой категорией; парсить HTML нельзя (403), через API — можно.

### 1.4 Etsy

- Рыночные страницы: https://www.etsy.com/market/larp (+ larp_sword,
  larp_costume, larp_clothing, larp_accessories, larp_kit (UK), sca_larp,
  larp_lot). **403 при WebFetch, 15.09.2026.** Число листингов не получено.
- Etsy — это **новое ремесленное**, а не б/у (продавцы — мастерские).
  Для нас — источник каталога кустарных производителей, не второго рынка.
- API: **Etsy Open API v3**, `GET /v3/application/listings/active`
  (`findAllListingsActive`) — по выдаче «one of three endpoints that
  authenticate with just an API key (no OAuth user token)»; параметры
  `keywords, limit, offset, sortOn, sortOrder, minPrice, maxPrice,
  taxonomyId, shopLocation`.
  Ограничение (github.com/etsy/open-api/discussions/1188): «Offset provided
  is greater than the maximum offset allowed» — потолок **12 000** записей
  на запрос при total 32 166.
  Лимит по умолчанию (по выдаче): «10,000 requests per 24-hour period,
  with a limit of 10 queries per second»; страница
  developer.etsy.com/documentation/essentials/rate-limits/ открылась, но
  чисел не содержит («You can see your application's current rate limits
  in the Developer Portal»).
  Доступ: сначала Personal App, потом «request Commercial Access» — в
  discussions #1607/#1361 люди застревают в «Pending Commercial Approval».
  Листинг-туториал (developer.etsy.com/documentation/tutorials/listings/)
  говорит про OAuth-скоупы `listings_r`/`listings_w` — это для продавцов.
- Вывод: Etsy через API — реально, но с гейтом одобрения и потолком
  12 000/запрос; через HTML — 403.

### 1.5 Доски объявлений (общие, не ЛАРП-специфичные) — самый живой пласт

**kleinanzeigen.de (Германия)** — открывается без antibot.
- https://www.kleinanzeigen.de/s-larp/k0 — «1 - 25 von **3.002** Ergebnissen
  für „larp" in Deutschland». Категории: «Freizeit, Hobby & Nachbarschaft:
  1,566», «Mode & Beauty: 1,069», «Handarbeit, Basteln & Kunsthandwerk:
  306». Регионы: NRW 720, Bayern 456, Niedersachsen 316. Связанные
  запросы: mittelalter, reenactment, larp rüstung, wikinger mittelalter,
  larp schwert. Примеры: «Wollumhang» €60 VB, «Mittelalter Rüstungen (set
  of 3)» €720 VB, «LARP Armbrust» VB.
- https://www.kleinanzeigen.de/s-larp-waffen/k0 — «1 - 25 von **32**
  Ergebnissen für „larp waffen"». Примеры: «LARP Hammer Polsterwaffe für
  Rollenspiele» 19 € VB; «Schwert LARP Ritter Cosplay Schaumgummi
  Polsterwaffe neu» 35 €; «LARP Krähenschnabel Schaumstoffwaffe
  Zweihandhammer» 125 €; «LARP Rüstungs-Set inkl. 2 Helme und Waffen» 500 €.
- Другие срезы из выдачи: /s-spielzeug/larp-waffen/k0c23,
  /s-freizeit-nachbarschaft/larp-waffe/k0c185, /s-larp-polsterwaffen/k0,
  /s-larp-schwert/k0.
- доступность: HTML без JS (WebFetch прочёл список, цены, фильтры) — **лучший
  б/у-источник по объёму и доступности в этой выборке**; API нет.
- агрегатор поверх: gebraucht-kaufen.de/larp-waffen (не открывал).

**marktplaats.nl (Нидерланды)** — открывается без antibot.
- есть **своя категория** «Kostuums, Theaterbenodigdheden en LARP»:
  https://www.marktplaats.nl/l/hobby-en-vrije-tijd/kostuums-theaterbenodigdheden-en-larp/
  — «**2,424** advertenties»; подтипы: Pak of Jurk 432, Accessoires 265,
  Toneelattributen 181, Bovenkleding 139, Handschoenen/Hoed 128; состояние:
  Nieuw 904, Zo goed als nieuw 759, Gebruikt 465; 2 045 с самовывозом,
  1 945 с доставкой.
- https://www.marktplaats.nl/q/larp/ — «**2,701** offerings», «294
  additions this week», «average price €71», new 1 085 / like-new 788 /
  used 482.
- по выдаче: /q/larp+wapens/ — «74 offerings in July» (июль 2026), пример
  «LARP ice pick … 63 cm … original price €89.99».
- доступность: HTML читается; отдельного API нет (marktplaats — eBay
  Classifieds Group, того же семейства, что kleinanzeigen).
- Оговорка: категория смешана с косплеем и фурсьютами (в примерах «Miku»,
  «Genshin Impact», fursuits) — доля ЛАРП внутри 2 424 неизвестна.

**Gumtree (UK)** — https://www.gumtree.com/search?search_category=all&q=larp
— **5** объявлений: «Chain Mail Hood» £95 (Pontyclun), «Viking LARP Horn
Drinking Vessel» £40, «Knight LARP Costume» £30, «Medieval Steel
Breastplate» £30, «Toy Pirate Sabre» £30 «95cm long». Читается без JS.
Объём ничтожный.

**Vinted (UK)** — https://www.vinted.co.uk/catalog?search_text=larp —
«**500+ results**», £1.00–£130.00, «most items under £50»; Next.js, но
листинги есть в HTML. Профиль: одежда/аксессуары (корсеты, туники,
плащи, наручи, пояса), оружие редко. Вероятно, есть и vinted.de/.fr/.pl —
не проверял.

**for-sale.co.uk** (агрегатор UK) — /larp-weapons и /larp-armour («60 used
Larp Armours» в тайтле выдачи) — **403 при WebFetch**.

**veilingkijker.nl** — агрегатор NL по выдаче (larp_wapens), не открывал.

### 1.6 Европейские форумы / соцсети с барахолкой

- **Larpbook** (DE) — https://larpbook.org/groups/larp-flohmarkt/ — группа
  «Larp Flohmarkt»: «Hier könnt ihr alles rund um das Hobby Larp
  miteinander handeln.» Видно ~10–12 постов и «Load More»; число участников
  не показано; **контент за регистрацией** (Sign in / Sign up).
  meinlarpkalender.de/kalender/ теперь редиректит на larpbook.org — то есть
  Larpbook поглотил и календарь; /kalender/ на larpbook.org — 404.
- **larp-platform.nl** (NL) — /webshop/ продаёт только мерч («Toont alle 4
  resultaten»: сумки, постеры, значки, открытки); барахолки нет.
- **forums.profounddecisions.co.uk** — исключён по условию (известен).
- UK-форумы с разделом For Sale: **не найдены** — поиск дал только Etsy,
  eBay, магазины и тред Empire-форума «Where to find Larp Weapons and
  Armour, cheap and reliable». Британская б/у-торговля, по всей видимости,
  ушла в Facebook-группы (1.2).
- DE-форумы с Marktplatz: поиск вывел на kleinanzeigen.de и Facebook, а не
  на форумы; larp-forum-подобных площадок с открытым разделом «Biete/Suche»
  в выдаче нет.

### 1.7 Discord

- disboard.org/servers/tag/larp?sort=-member_count — **403**.
- top.gg/discord/servers/844585263290724352 («gg/LarpSocial», в выдаче: «The
  #1 biggest discord community for larpers on the internet») — **403**.
- discord.com/servers/the-chizlarp-larphouse-15-1215289931467853834 — в
  выдаче, не открывал.
- В сниппетах выдачи есть фраза «high-quality 1:1 LARP tools and replica
  props on the market, with dedicated marketplace channels» — к какому
  серверу относится, не установлено. **Ни одного публично описанного
  ЛАРП-сервера с каналом продажи подтвердить не удалось.**

---

## 2. Структурированные каталоги нового (номенклатура и алиасы)

### 2.1 Epic Armoury / Iron Fortress (Дания) — сильнейший источник

- https://epicarmoury.com/ — Shopify («Powered by Shopify», CDN
  `//epicarmoury.com/cdn/shop/files/`). Витрины: epicarmoury.com (EU, €),
  us.epicarmoury.com (US), epicarmoury.com.au (AU, отдельный магазин).
- **/collections/all — «1,866 products».**
- **/products.json?limit=N — работает, открытый JSON без ключа.** Первый
  товар: «Effect Blood», product_type «SFX Blood», vendor «Epic Armoury
  Europe», tags «Epic Armoury Products, new release, Reviewed by
  Anastasiia», варианты «Red & Red Gore / 100 ml: €15.00», «500 ml: €48.00».
  Поля: id, title, handle, body_html, published_at/created_at/updated_at,
  vendor, product_type, tags, variants (price, sku, available), images,
  options. Пагинация Shopify: `?limit=250&page=N`.
- **/sitemap.xml** — индекс: sitemap_products_1.xml (id 10107724530000…
  10109784490320), sitemap_products_2.xml (…10578217533776),
  sitemap_pages_1.xml, sitemap_collections_1.xml, sitemap_blogs_1.xml,
  sitemap_agentic_discovery.xml; «kept up to date in real time».
- Навигация: Weaponry (Swords, Short swords, Staffs & Spears, Axes, Viking
  swords, Curved Blades, Medium Swords, Two-Handed Swords), Armour (Arms…),
  Clothing (Robes & Capes, Vests, Skirts, Dresses), Epic world (Brands…).
- Суббренд **Ready For Battle (RFB)** — /collections/ready-for-battle:
  «56 products»; 16 swords, 2 axes, 1 mace, 4 daggers, 1 staff; 6 arm,
  5 leg, 5 torso, 1 shoulder, 1 buckler, 3 shields; материалы-фасеты «EVA
  Foam (27), Fiberglass Rod (24), Latex (25), Suede Leather (24)»; типы
  конструкции «Classic» и «Hybrid»; цены €12–€142.
- Карточка товара (пример /products/1922-rfb-defender): «Length: 75 cm
  (29.5 in)», «Weight: 407g; blade 235g», «Grip 10 cm», «Blade Length 57 cm»,
  «Blade Width 5 cm», «Core: Fiberglass rod», «Materials: EVA Foam,
  Fiberglass Rod, Latex, Polyurethane Foam», «Brand: Ready For Battle»,
  €70.00. — **готовая структура полей для слота «оружие»**: длина, масса,
  сердечник, материал, бренд.
- Дилеры — /pages/recommended-retailers (три уровня, дословно):
  Partners: «The Epic Armoury Partners are the vanguard of the Recommended
  Retailers. They represent our brand, cover our entire product range and
  are directly involved in our development and marketing strategies.» —
  Epic Armoury Australia (AU), LARP Gear – Japan (JP).
  Return Centres: «…offer to receive and refund products purchased directly
  from epicarmoury.com» — LARP Box (USA), Le Rune (IT), Les Artisans
  d'Azure (CA).
  Recommended Retailers: Battle Merchant (DE), Dein LARP Shop (DE),
  Gripheim (SE), Faraos Cigarer (DK), LARP Inn (UK), Calimacil (CA), Imago
  (CZ), Le Repaire du Dragon (FR), Mon GN (FR), Chevalier du Drac (FR),
  Paddywhack (NZ).
- **ironfortress.com** — B2B-оболочка: «Your orders now have to be placed
  through our new B2B platform on epicarmoury.com…»; группа: Epic Armoury,
  Yoremade, Medieval Merchant. Дилерский вход — за логином. Адрес по выдаче:
  Kornmarksvej 12-20, Brøndby; основана 2008.
- JSON-LD на страницах — через WebFetch не виден (см. оговорку в шапке).

### 2.2 Calimacil (Канада)

- https://calimacil.com/ — Shopify. **/products.json?limit=3 — работает.**
  Примеры: «Cascade Sword Rack for Grid Walls» (type Accessories, vendor
  «Calimacil Accessories», $20/$40), «Aerondight Great Sword – Witcher Wild
  Hunt» (type Weapon, vendor «Calimacil Workshop», $320.00), «Mandragora
  Witcher Mask» ($115.00). Поле `vendor` у них — суб-линейка, `product_type`
  — класс (Weapon / Accessories).
- /collections/all-product — общий счётчик товаров WebFetch не вытащил;
  категории: weapons, armor, costume apparel, accessories, custom.
- /pages/brands — партнёры: «Calimacil, Les Artisans D'Azure, Mytholon,
  Rawblade, Dracolite, Zardwin, Athena, Calimotion, Nemesis Workshops».
- /pages/epic-armoury — реселлер Epic Armoury: «founded in 2008 Denmark…».
- Основана 2004, Sherbrooke, Québec; продаётся и через Amazon.com (store
  page в выдаче). Отдельного списка дилеров нет; сама — дилер Epic Armoury.
- Материал: foam без латекса (по выдаче), «1-year warranty».

### 2.3 Mytholon (Германия)

- https://mytholon.com/en/ — **Shopware**. Навигация: Garments, Armour,
  Foam Weapons, Accessories, Miniatures, Brands, Medieval Outlet, Sets.
  Магазины: «Store Hamburg, Store Cologne, Store Leipzig, Store Rome».
  Цитата: «one of the world's largest selections of garment, armour and
  all kinds of accessories».
- /sitemap.xml — индекс с одним gz-файлом
  `/sitemap/salesChannel-…/…-sitemap-mytholon-com-1.xml.gz`, lastmod
  2026-09-14T22:10:23+00:00 — **sitemap есть, товарные URL внутри gz (не
  открывал)**.
- /en/foam-weapons/ — «hundreds of foam weapon products across multiple
  pages», €<20–€350+; собственные линейки «Battle Standard» (бюджет),
  «Wyvern Replica»; стоят и Calimacil. Стейдж-оружие: «rounded tip… blunt
  edge with at least 2mm width».
- Число товаров самого бренда — по дистрибьюторам: LARP Distribution (US)
  «Mytholon — 1,488 products»; 5zywiolow.com (PL, PrestaShop) «Total
  products in this category: 1123».
- API: у Shopware 6 есть Store API (`/store-api/product`, нужен
  `sw-access-key` из HTML) — не проверял.
- Дилеры (из выдачи): Dark Knight Armoury, Medieval Collectibles, Having a
  Larp (UK), 5 Elements (PL), LARP Distribution (US wholesale).

### 2.4 LARP Distribution (США, оптовик)

- https://www.larpdistribution.com/product-category/shop-by-brand/ —
  WooCommerce. Счётчики по брендам: **Mytholon 1,488 · House of Warfare
  435 · Burgschneider 216 · Zeughaus 194 · Lord of Battles 173 · Mystic
  Colonial 91 · MADcraft 31 · Dungeons & Dragons 31 · Warhammer 25 ·
  Hammerkunst 22.** Цитата: «Become a Dealer for Quality Medieval,
  Renaissance and LARP Products from Mytholon, House of Warfare, Lord of
  Battles, Mystic Colonial, and Burgschneider Brands.»
- WooCommerce → обычно открыт `/wp-json/wc/store/v1/products` (Store API
  без ключа) — не проверял.

### 2.5 Dein LARP Shop (Германия)

- https://dein-larp-shop.de/en-us/collections/all-products — Shopify;
  «**3,582** total products», «686 in stock», «2,896 out of stock»;
  секции Garments, Armour, LARP-Weapons, Accessoires, LARP-Life, D.I.Y.;
  фильтры: product type «100+ categories», color «140+»; «more than 50 LARP
  manufacturer».
- **/products.json?limit=3 — работает**, но vendor у всех «dein larp shop
  (Shopify)», product_type «Artikel» — **бренд и тип в фиде не заполнены**,
  номенклатура из него не извлекается, только названия/цены.
  (Выдача поиска обещала «over 10,000 LARP products» — на странице 3 582.)

### 2.6 Battle-Merchant (Германия) — известен, только дополнение

- /en/larp-weapons — Shopware; «over 10,000 items in the range» (весь
  магазин); подкатегории оружия: Swords · Axes, Hammers, Maces · Knives &
  Daggers · Pole weapons · Throwing weapons · Bows & Arrows · Shields ·
  Modern weapons · Other weapons · Do it yourself · Holders · Care
  products. Языки EN/DE/FR/SV/ES/IT.

### 2.7 Andracor (Германия)

- https://www.andracor.com/en — с конца 1990-х, кожевенная мастерская в
  Берлине; бренды: «Iron Fortress, Wyvern Crafts, Burgschneider, Calimacil,
  Rawblade, Leonardo Carbone». Категории: Garments, Armor (leather, plate,
  chainmail, plastic), LARP Weapons (foam swords, axes, shields, bows),
  Accessories, Make-up & SFX, жанры (Vikings, Pirates, Steampunk, Fantasy,
  Post-Apocalypse).
- Карточка (пример /en/p/sword-wyverncrafts-type-17-larp-weapon--616017):
  «Sword Wyverncrafts - Type 17, larp weapon», SKU 616017, Brand «Wyvern
  Crafts», «129,99 €», «Currently not available»; атрибуты: «Length ca. 87
  cm / ca. 102cm», «Blade length approx. 70 / 85 cm», «Material: Foam, fibre
  glass», «Guard width approx. 21 cm». Платформу WebFetch не определил;
  счётчик товаров не найден.

### 2.8 Wyvern Crafts (Германия, Кёльн)

- https://www.wyvern-larpshop.de/en — Shopware; «since 1992»; категории:
  Larpweapons, Leather goods, Accessories, DrachenFest Merchandise;
  «Replicas of real swords». Счётчик не показан. По выдаче — «may hit
  harder than suitable for most UK LARP groups» (важно для валидатора:
  жёсткий/тяжёлый класс).

### 2.9 Forgotten Dreams Design (Германия)

- Собственного открытого каталога в выдаче нет; продаётся через
  swords-and-more.com/en/Manufacturer/Forgotten-Dreams-Design/ (2 товара на
  первой странице: «Roman Shield (green) €199.00», «Elf dagger €37.50»),
  medievalcollectibles.com, latex-weaponry.com (Knighthawk Armoury, UK),
  bytheswordinc.com, thevikingstore.co.uk, buyingasword.com. Цитата
  производителя: «From a replica of a historic weapon to exclusiv design of
  fantastic and individual models». С 2001 г. (по выдаче).

### 2.10 Palnatoke (Дания)

- Собственного магазина в выдаче нет; продаётся через getasword.com
  (/24_palnatoke-swords), therionarms.com, battlemerchant.com,
  periodsintime.com, dein-larp-shop.de/en/palnatoke/. По выдаче: «producing
  movie and stage props for over 25 years», «since 2000 … swords and
  daggers for LARP», «fiberglass cores… leather wrapped grips… rubberized
  coatings».

### 2.11 LARP-Fashion (Германия)

- https://www.larp-fashion.de/ — Shopware; «über 5000 ausgesuchte Artikel»;
  категории: Mittelalter Kleidung, LARP, Schuhe, Schmuck, Accessoires;
  «eigene Lederwerkstatt»; зеркала larp-fashion.co.uk / .fr / .it / .se;
  валюты EUR, CHF, GBP, SEK, USD. Профиль — одежда, не оружие.

### 2.12 Larpshop — не идентифицирован

Запрос «larpshop» ничего с таким доменом не дал; в выдаче —
the-larp-store.com (US, есть /sitemap.aspx), larpgems.com (UK; бренды
Medlock Armoury, Lyon Leathers Ltd), larpinn.co.uk. Возможно, имелся в
виду larpshop.de / larp-shop.nl — не проверено.

### 2.13 Прочие розничные с открытым каталогом (для алиасов, не для наполнения)

- **LARP Inn** (UK, Telford) — https://www.larpinn.co.uk/ — PrestaShop;
  Armour (leather, plate, chain, polyurethane, gambesons), LARP Weapons
  (swords, axes, daggers, bows, shields), Costumes, Makeup & Prosthetics,
  Accessories; £1.99–£205.99; дилер Epic Armoury уровня 1.
- **Having a Larp** (UK) — https://havingalarp.com/ — BigCommerce; бренды:
  Mytholon, HaL Emporium, Medlock Armoury, Cowley's Fine Foods, Irregular
  Props, Piece of History, Snazaroo, Art Hammer, Dunkel Art, Lyon Leathers;
  5 категорий / 30+ подкатегорий.
- **Medieval Collectibles** (US) — WooCommerce; /product-category/…/
  shop-by-larp-manufacturer/ — список производителей WebFetch не показал;
  упомянуты Epic Armoury, Calimacil, Windlass Steelcrafts, Marto, Hanwei,
  Get Dressed For Battle.
- **5 Żywiołów / 5zywiolow.com** (PL) — PrestaShop; Mytholon «1123».
- **Celtic Web Merchant** — известен (исключён), но в выдаче NL-описание
  «largest LARP webshop in the Netherlands».
- **fantasyshop-fairyland.nl** — по выдаче, не открывал.

---

## 3. Правила безопасности оружия (аналог регламента для валидатора)

### 3.1 Empire LRP (Profound Decisions, UK) — лучший источник: открытая вики, числа в дюймах

- https://www.profounddecisions.co.uk/empire-wiki/Weapons_&_armour —
  длины (дословно):
  Daggers «Must be between 8" and 24" long»; One-handed «between 24" and
  42"»; Great weapons «over 42" and up to 60"»; Polearms «between 60" and
  84"»; Pike «over 84" and up to 108"»; One-handed spear «over 60" and up
  to 84"»; Wands «between 8" and 18"»; Rods «over 18" and up to 42"»;
  Staves «over 42" and up to 84"».
  Доспех: Light — «Padded cloth or thin leather (1.5-3mm)», 2 hits;
  Medium — «Leather, 3mm+ thick», 3 hits, защищает от CLEAVE; Heavy —
  «Metal or metal-appearing material», 4 hits, от CLEAVE и IMPALE; Mage
  armour — 2 hits.
- https://www.profounddecisions.co.uk/empire-wiki/Weapon_checking —
  разделы: Overview, Traders, All weapons, Bows and Crossbows, Arrows &
  Bolts, Shields, Armour, Thrust safe polearms, Props, Banned items.
  Числа: «The draw of a bow must be less than 30 lbs at 28" draw. Crossbows
  are also limited to 30lbs draw weight»; «Arrows must have a maximum draw
  position of 28" clearly marked…»; «The arrowhead must be at least 50mm
  across and have a circular cross-section», «be at least 25mm at the
  thickest point and must collapse fully under firm pressure», «there must
  be no latex within 5-10 mm of the face»; щиты: «at least 6mm of
  high-density foam on the face and no protruding bolts».
  Сердечник (по выдаче форума/вики): «must be made of an appropriate
  material such as fibreglass or carbon fibre - not of aluminium, wood or
  bamboo»; «The 8" minimum weapon length still applies to all weapons,
  cored and coreless»; coreless допустимы «provided they are not whippy».
- https://www.profounddecisions.co.uk/empire-wiki/Bow_safety — те же 30 lbs;
  «reduce the draw… closer than 10m»; «may not fire a crossbow at targets
  under 3m»; «under 18 … cannot use a crossbow».
- Доступность: MediaWiki, HTML читается, есть стандартный `api.php`
  (не проверял). Формат — идеальный для правил валидатора (категория →
  min/max длина).

### 3.2 Lorien Trust (UK)

- Rules Handbook v4.06 (PDF):
  https://lorientrust.com/wp-content/uploads/2024/11/Lorien-Trust-Rules-Handbook-v4.06-3.pdf
  — не открывал (PDF через WebFetch не читается, см. 3.10). По выдаче:
  «checked by a senior weapons checker… stamped (with invisible ink),
  wrapped with an elastic band or labelled». Числовых норм из выдачи нет.

### 3.3 Общая британская норма (LARP Inn blog)

- https://www.larpinn.co.uk/module/ybc_blog/blog?id_post=7 — «A weapon
  needs to a have a minimum of around 0.5"/12mm of foam on any striking
  surface and 0.25"/6mm on any non-striking surface»; плотность «around
  45kg/m³»; отсылает к Curious Pastimes, Herofest, Lorien Trust, Profound
  Decisions; «there is no universal standard for LARP safety».
- legacylrp.co.uk/weapons-guidelines/ — **DNS не резолвится, 15.09.2026**.

### 3.4 Drachenfest (Германия)

- https://www.drachenfest-larp.info/informationen/regeln/ — открывается;
  ссылка на «Regelwerk-7-2EN2023.pdf»; DE и EN версии; чисел на странице
  нет. В выдаче также «Regelwerk-8-DE-2026.pdf»
  (https://www.drachenfest-larp.info/media/pdf/46/c0/6a/Regelwerk-8-DE-2026.pdf)
  и старые v6.0 / Codex Belli 2.0.
- Безопасность (по выдаче, источник dfenglish.wikidot.com/sicherheitsrichtlinien):
  «GFK core… recommended minimum padding of 15mm on striking zones and 5mm
  on non-striking zones»; полэрмы «at least 6mm firm foam or 10mm soft
  foam on all surfaces, striking zones at least 15mm»; луки/арбалеты «max
  draw force of 30 pounds».
  Сама страница wikidot — **не открылась: бесконечный 301 на саму себя**
  (http→http), 15.09.2026.

### 3.5 ConQuest of Mythodea (Live Adventure, Германия)

- «LARPzeit Waffencheck» —
  https://www.live-adventure.de/ConQuest/dateien/regelwerk/LARPzeit_Waffencheck.pdf
  — PDF 511.6 KB скачался, но текст не извлёкся (см. 3.10). По выдаче:
  гайд «Dennis Stirnberg, Larson Kasper und Christian Heimes», признан
  Drachenfest/Vinland и др.
- Особенность ConQuest: с 2009 г. **нет общего weapon check** —
  «eigenverantwortlicher Waffencheck» (larpwiki.de/EigenverantwortlicherWaffencheck:
  «ConQuest of Mythodea – abandoned general weapon checks, citing high
  administrative costs»; также Turney der Südlande, Großes Manöver «checks
  only bow draw weight»).
- Regelwerk 2022: https://www.live-adventure.de/ConQuest/dateien/Regelwerk_Conquest22_DE.pdf;
  Basisregelwerk V1.1 там же.

### 3.6 Bicolline (Канада, франкоязычная)

- https://bicolline.org/en/participants-guide/combat-rules/ — страница-хаб,
  чисел нет; PDF (все 2026 г.): «Combat rules»
  /wp-content/uploads/2026/05/ReglesCombat1.1-AN.pdf; «Homologation
  Standards» /wp-content/uploads/2026/05/Standards-dhomologation-AN-v1.2-juin-2026.pdf;
  «Tournament Rules» …/TournoisRegles-en.pdf; «Le Choc des Amiraux»
  …/2026/07/ChocAmirauxE-1.pdf. Старые: Homologation_v2022_finale.pdf
  (апрель 2022), FAQ-1.pdf (22.04.2024).
- По выдаче: «All participants, weapons, shields, monsters, war machines,
  and in-game items or objects must be homologated (approved) before
  entering the battlefield»; «must not have rigid parts, must have secured
  skeleton ends, and must be covered with protection from tip to guard».
- Термин **«homologation»** — прямой аналог нашего «допуска».

### 3.7 Belegarth (США)

- https://www.belegarth.com/rules — WebFetch увидел только меню; правила
  вынесены в вики geddon.org (wiki.belegarth.com — **DNS не резолвится**).
- https://geddon.org/Weapons_Check — числа (дословно): «No surface on a
  striking edge...may pass more than 0.5 inch through a 2.5 inch hole»;
  pommel «may not readily pass more than 0.5" through a 2" diameter hole»;
  flail «six (6) inches» цепь, «No more than 1 ½ inches of chain may be
  exposed», голова «fifteen (15) inches» окружность, «forty (40) inches»
  макс; Class 1 «shorter than forty-eight (48) inches», при 24"+ минимум
  «twelve (12) ounces»; Class 2 «forty-eight (48) inches» и «twenty-four
  (24) ounces»; double-ended «7 feet (210 cm)», «18 inches» набивки на
  конец; щит «3 feet» ширина, «18 inches less than the height of the
  wielder», минимум «12 inches».
- https://www.geddon.org/Weapon_Construction_Basics — сердечники: «1/2" PVC
  for up to 38" cores», «3/4" PVC for 38"-54"», «1" PVC for 54"-72"»;
  fiberglass «3/8" … up to 28"», «1/2" … up to 44"», «5/8" or 3/4" … <55"».
  Версия Book of War не указана. Из выдачи: «may not flex more than 45
  degrees».
- MediaWiki → есть api.php (не проверял).

### 3.8 Dagorhir (США)

- https://dagorhir.com/wordpress/rules/ — **403**.
- https://www.dagorhir.wiki/w/index.php?title=Manual_of_Arms_(MOA) —
  открылась. «Voted at Ragnarok XXXIII (2018) for use at Ragnarok XXXIV
  (2019)», «Last Updated: September 24, 2020». Дословно: 4.1.5 «No part of
  a weapon's striking surface… may pass easily more than 0.5" through a
  2.5" diameter hole when tested in the direction of the strike»; 4.1.6
  «…non-striking component… more than 0.5" through a 2" diameter hole»;
  4.2.2 Blue «minimum total length of 12 inches and a maximum total length
  less than 48"»; 4.3.2 Red «48 inches or longer… when swung with two
  hands»; 4.5.3.15.2 «The softer padded face of the arrow must be at least
  2.5" wide in all directions»; 4.5.3.15.1 «draw stop… between 27" and 28"»;
  4.7.4–4.7.5 щит «not taller than the distance between the wielder's chin
  and their ankles, nor wider than 3 feet… minimum diameter… 12 inches».
- Spear (из выдачи): «at least 1/3 of the haft padded».

### 3.9 Amtgard (США)

- wiki.amtgard.com (V9: Weapons, V9: Weapon Construction Terms) — **403**;
  amtwiki.amtgard.com — **DNS не резолвится**. Из выдачи: «Padding… at
  least half an inch of foam over the weapon core»; V9 — alpha playtest,
  актуален V8 Rulebook (PDF не найден; в выдаче только 7th edition PDF на
  сторонних хостах: alonatwotrees.com, amtgard-eh.com).

### 3.10 NERO / Alliance (США)

- http://nerolarp.com/page.php?12= — **404**. По выдаче: «NERO LARP Rule
  Book 9th Edition… free download»; спецификации из форума Alliance:
  «2" thrusting tip… 5/8" foam wall», «closed cell foam should extend 1"
  past the core… at both ends», «minimum of 5/8" thick foam… above the
  grip», сердечник «half or 3/4 inch» PVC.
- Underworld LARP (Канада) Weapon and Armour Guide v1.4 (PDF, май 2022):
  https://underworldlarp.com/wp-content/uploads/2022/05/Underworld_LARP_Weapon_and_Armour_Guide_v1.4.pdf
  — скачался 585.3 KB, текст не извлёкся.
- Mythic Adventures /weapons/safety, Polar LARP /rules/rulebook/ — в выдаче,
  не открывал.

**Общий факт про PDF:** WebFetch отдаёт PDF как бинарь и не извлекает
текст (три попытки: LARPzeit_Waffencheck, Underworld v1.4 — оба «не
читаются»); `pdftoppm` на машине нет. Все PDF-регламенты — в «Сомнительное»
до отдельного прогона.

### 3.11 Сводная таблица чисел (что уже можно положить в валидатор)

| Система | Лук, lbs | Дротик/стрела | Мин. длина | Классы длины | Набивка |
|---|---|---|---|---|---|
| Empire (UK) | <30 @ 28" | head ≥50 mm, ≥25 mm толщ. | 8" | 8–24 / 24–42 / 42–60 / 60–84 / 84–108 " | щит ≥6 mm |
| Drachenfest (DE), по выдаче | 30 | — | — | — | 15 mm удар / 5 mm прочее; полэрм 6 mm твёрд / 10 mm мягк |
| Belegarth (US) | — | — | — | Class 1 <48" (≥12 oz при ≥24"); Class 2 ≥48", ≥24 oz | тест 2.5"-отверстие / 0.5" |
| Dagorhir (US) | — | face ≥2.5", draw stop 27–28" | 12" (Blue) | Blue 12–<48"; Red ≥48" | тест 2.5" / 2" |
| Amtgard (US), по выдаче | — | — | — | — | ≥1/2" над сердечником |
| NERO/Alliance, по выдаче | — | — | — | — | 5/8" стенка, 2" колющий тип |
| UK «обычай» (LARP Inn) | — | — | — | — | 12 mm удар / 6 mm прочее, ~45 kg/m³ |

Две традиции измерения: европейская — миллиметры набивки + дюймы/см длины;
американская — «hole test» (проход через отверстие 2.5"/2") + унции.
Валидатору нужны оба типа правил.

---

## 4. Календари игр

| Источник | URL | Страна | Что даёт | Экспорт | Состояние |
|---|---|---|---|---|---|
| Thilo Wagners LARP-Kalender | https://www.larpkalender.de/ (= larp-kalender.de) | DE/AT/CH | «12078 Termine in der Datenbank», «Seit 20 Jahren» | RSS/iCal/API **не найдены**, только «Druckansicht» | жив |
| LARP Calendar Switzerland | https://www.larpkalender.ch/ics.php?lang=en | CH | события | **iCal**: `webcal://www.larpkalender.ch/ics_events.php`, файл `ics_events.php?type=file` («larpkalender_15-09-2026.ics») | жив |
| LARP.at Kalender | https://kalender.larp.at/ | AT | «9 events» в текущем виде, диапазон 15.09.2026–14.09.2028 | **RSS + iCalendar (ICS)** | жив |
| Larp Calendar (Nordic Larp) | https://larpcalendar.org/ | междунар. («events accepting international participants») | — | код открыт: github.com/nordiclarp/larpcalendar (NestJS + Prisma + PostgreSQL, Next.js, Nx; 23 commits; контакт johannes@axner.io) | сайт — **HTTP 526 (TLS), 15.09.2026** |
| LARP SEASON | https://larpseason.com | UK (+ междунар.) | «over 700 UK LARPs and 150 international blockbuster events», запущен 2024 | нет | жив |
| larpevents.co.uk | http://www.larpevents.co.uk/ | UK | события, организаторы, площадки, **trader directory**, отзывы | нет («We are mostly up and running again!») | жив |
| Larp Radar | https://larp-radar.com/larps-calendar | междунар. | по выдаче: календарь, билеты, карта | ? | **403** |
| Alexandria | https://alexandria.dk/en/ | DK/междунар. | «18,095 scenarios · 1,155 board games · 10,139 persons · 2,813 conventions · 370 RPG systems» | нет упоминания API | жив |
| LARP Platform | https://www.larp-platform.nl/kalender/ | NL | календарь по жанрам | нет | жив |
| Nordic LARP Calendar | https://www.nordlarp.com/ | SE/NO/DK/FI | — | — | **не открылся: сертификат *.one.com, 15.09.2026** |
| Mein Larp Kalender | https://meinlarpkalender.de/kalender/ | DE | — | — | редирект на larpbook.org (битый URL «larpbook.orgkalender»), larpbook.org/kalender/ — 404 |
| Список календарей Nordic Larp Wiki | https://www.nordiclarp.org/wiki/List_of_Larp_Event_Calendars | — | ссылки: rollespil.dk/calender.php (DK), kalenteri.larp.fi и con2.fi/larp-kalenteri (FI), larpalot.com (FR), laiv.org/laiv/DetStore.nsf (NO), spelkult.se/spelkalender/ (SE), + Google Doc | — | жив |
| larp.guide | — | — | **поиском не найден** (ни одного результата с таким доменом) | — | не найден |

Прочее из выдачи (не открывал): larperscalendar.wordpress.com («eurocentric
overview»), vehi-mercatus.com/market-calendar/type/larp-event/2026/
(рынки/ярмарки), liveactionroleplay.com/larp-events, larpadventureprogram.com.

Вывод по календарям: машинный экспорт есть только у **CH (iCal)** и **AT
(RSS+ICS)**; крупнейший (DE, 12 078) — только HTML; международный
larpcalendar.org лежит, но у него открытый код и БД-модель.

---

## 5. Отрицательные результаты

1. **Reddit недоступен инструментом** (www / old / .json) — состояние
   флейров/правил r/LARP не установлено; торговых сабреддитов в выдаче нет.
2. **UK-форумы с For Sale** — не найдены; британская б/у-торговля, судя по
   выдаче, целиком в Facebook-группах (5 групп по названиям).
3. **DE-форумы с Marktplatz** — не найдены; немецкая б/у-торговля — в
   kleinanzeigen.de и Facebook/Larpbook.
4. **Discord** — ни один ЛАРП-сервер с публично описанным каналом продажи
   не подтверждён (disboard/top.gg — 403).
5. **eBay/Etsy HTML** — 403 на всех страницах; числа лотов не получены.
6. **larp.guide** — не существует в выдаче.
7. **Larpshop** — домен не идентифицирован.
8. **Palnatoke, Forgotten Dreams** — собственных открытых каталогов нет,
   только через реселлеров.
9. **PDF-регламенты** (LARPzeit Waffencheck, Underworld, Lorien Trust,
   Drachenfest Regelwerk 8, Bicolline Homologation v1.2 2026) — не
   прочитаны: WebFetch не извлекает текст PDF.
10. **Dagorhir.com, Amtgard wiki, Belegarth.com/rules** — 403/DNS/пусто;
    числа взяты с зеркальных вики (dagorhir.wiki, geddon.org).
11. **JSON-LD Product** — ни на одном магазине не подтверждён (ограничение
    инструмента, не факт об отсутствии).
12. **Нордический календарь** (nordlarp.com) — битый TLS; larpcalendar.org
    — 526.

## 6. Сомнительное

- «LARP Distribution: Mytholon 1,488» и «5zywiolow: Mytholon 1123» — это
  ассортимент дилеров, а не полный каталог Mytholon; сам Mytholon счётчика
  не показал.
- Dein LARP Shop: выдача поиска говорила «over 10,000», страница — 3 582
  (из них 2 896 «out of stock»). Круглое число — из маркетинга.
- Battle-Merchant «over 10,000 items» — весь магазин, не оружие.
- kleinanzeigen «3.002 по слову larp» — в это входят одежда и рукоделие
  (Mode & Beauty 1 069, Handarbeit 306); чистого оружия — 32.
- marktplaats «2 424 в категории» — категория объединена с косплеем и
  театром; доля ЛАРП неизвестна.
- Drachenfest числа (15 mm/5 mm/6 mm/10 mm/30 lbs) — только из сниппета
  выдачи по wikidot-странице, сама страница не открылась; версия правил
  неизвестна.
- Amtgard «1/2"» — из сниппета по 7th edition / V9-alpha, не по действующему V8.
- NERO «5/8" foam wall, 2" thrusting tip» — цитата с форума Alliance LARP
  про «minimum NERO Alliance specs», не из рулбука.
- Etsy API «10,000/day, 10 QPS» — из выдачи по сторонним пересказам;
  официальная страница rate-limits чисел не содержит.
- eBay «5,000 calls/day» — из сообщества eBay, не из docs (docs — 403).
- larpcalendar.org «23 commits» — WebFetch не увидел даты последнего коммита;
  проект может быть мёртв.
- reddapi.dev «66,740 subscribers» — сторонний индексатор; дата снимка не
  указана.
- Все «за стеной» Facebook-группы: регион и назначение — по названию.

## 7. Сводка доступности для парсера

| Уровень | Источники |
|---|---|
| **Открытый JSON без ключа** | epicarmoury.com `/products.json` (1 866), calimacil.com `/products.json`, dein-larp-shop.de `/products.json` (3 582, но без бренда/типа) |
| **Sitemap с товарами** | epicarmoury.com (2 файла products), mytholon.com (1 gz) |
| **HTML без JS, читается** | kleinanzeigen.de, marktplaats.nl, gumtree.com, vinted.co.uk (частично), mytholon.com, andracor.com, wyvern-larpshop.de, larp-fashion.de, larpinn.co.uk, havingalarp.com, larpdistribution.com, Empire wiki, geddon.org, dagorhir.wiki, larpkalender.de/.ch/.at, larpseason.com, larpevents.co.uk, alexandria.dk |
| **Официальный API с ключом/одобрением** | eBay Browse API (5 000/день, одна категория на запрос), Etsy Open API v3 (`listings/active`, offset ≤12 000, гейт Commercial Access) |
| **Машинный экспорт календарей** | larpkalender.ch (iCal), kalender.larp.at (RSS + ICS) |
| **Antibot / 403** | ebay.com/.de/.co.uk, etsy.com, for-sale.co.uk, larp-radar.com, disboard.org, top.gg, dagorhir.com, wiki.amtgard.com, developer.ebay.com |
| **За логином** | все Facebook-группы, larpbook.org (Flohmarkt), ironfortress.com (B2B), Discord |
| **Не открылся / DNS / TLS** | reddit.com, old.reddit.com, legacylrp.co.uk, wiki.belegarth.com, amtwiki.amtgard.com, nordlarp.com (cert), larpcalendar.org (526), dfenglish.wikidot.com (redirect loop), nerolarp.com/page.php?12= (404), meinlarpkalender.de (битый редирект) |
| **PDF, текст не извлечён** | LARPzeit_Waffencheck.pdf, Underworld v1.4, Lorien Trust v4.06, Drachenfest Regelwerk 8, Bicolline Standards v1.2 (2026), Regelwerk_Conquest22 |
