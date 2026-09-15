/* HMB-Market — domain data
   Original prototype data, not lifted from any real product. */

window.ARCHETYPES = [
  { id: "ck14", label: "Чешский рыцарь",     period: "к. XIV в.",     region: "Чехия / Богемия", slotCount: 12 },
  { id: "vk10", label: "Викинг",              period: "IX–XI вв.",    region: "Скандинавия",     slotCount: 9  },
  { id: "st12", label: "Степной конник",      period: "XII–XIII вв.", region: "Степь",           slotCount: 10 },
  { id: "cb15", label: "Арбалетчик",          period: "XV в.",        region: "Бургундия",       slotCount: 11 },
  { id: "tk13", label: "Тевтонец",            period: "сер. XIII в.", region: "Пруссия",         slotCount: 12 },
  { id: "kp14", label: "Копейщик-пехотинец",  period: "к. XIV в.",    region: "Италия",          slotCount: 9  },
];

/* paperdoll body-zones — flat coordinates on a 320×560 silhouette */
window.BODY_ZONES = {
  head:        { cx: 160, cy:  60, w:  62, h:  72, label: "Голова" },
  neck:        { cx: 160, cy: 112, w:  44, h:  26, label: "Шея" },
  shoulderL:   { cx: 116, cy: 144, w:  44, h:  34, label: "Плечо лев." },
  shoulderR:   { cx: 204, cy: 144, w:  44, h:  34, label: "Плечо прав." },
  chest:       { cx: 160, cy: 188, w: 108, h:  74, label: "Грудь" },
  upperArmL:   { cx:  98, cy: 192, w:  30, h:  60, label: "Плечо (рука) лев." },
  upperArmR:   { cx: 222, cy: 192, w:  30, h:  60, label: "Плечо (рука) прав." },
  elbowL:      { cx:  92, cy: 240, w:  26, h:  22, label: "Локоть лев." },
  elbowR:      { cx: 228, cy: 240, w:  26, h:  22, label: "Локоть прав." },
  forearmL:    { cx:  86, cy: 274, w:  26, h:  52, label: "Предплечье лев." },
  forearmR:    { cx: 234, cy: 274, w:  26, h:  52, label: "Предплечье прав." },
  handL:       { cx:  82, cy: 318, w:  28, h:  30, label: "Кисть лев." },
  handR:       { cx: 238, cy: 318, w:  28, h:  30, label: "Кисть прав." },
  waist:       { cx: 160, cy: 254, w:  96, h:  34, label: "Пояс" },
  groin:       { cx: 160, cy: 296, w:  86, h:  36, label: "Пах" },
  thighL:      { cx: 138, cy: 358, w:  40, h:  74, label: "Бедро лев." },
  thighR:      { cx: 182, cy: 358, w:  40, h:  74, label: "Бедро прав." },
  kneeL:       { cx: 138, cy: 412, w:  36, h:  24, label: "Колено лев." },
  kneeR:       { cx: 182, cy: 412, w:  36, h:  24, label: "Колено прав." },
  shinL:       { cx: 138, cy: 460, w:  34, h:  64, label: "Голень лев." },
  shinR:       { cx: 182, cy: 460, w:  34, h:  64, label: "Голень прав." },
  footL:       { cx: 138, cy: 510, w:  44, h:  28, label: "Стопа лев." },
  footR:       { cx: 182, cy: 510, w:  44, h:  28, label: "Стопа прав." },
};

/* Czech Knight late 14th c. — 12 required slots, 3 layers system.
   Layer order from skin out: 1 = padding/under, 2 = mail, 3 = plate, 4 = surcoat. */
window.ARCHETYPE_CK14 = {
  id: "ck14",
  title: "Чешский рыцарь",
  period: "к. XIV в.",
  region: "Чехия / Богемия",
  blurb: "Полный латный комплекс позднего XIV в., с акцентом на пражскую и нюрнбергскую плате. Конная служба, ленник короны.",
  required: 12,
  filled: 8,
  conflicts: 1,
  slots: [
    { id: "helm",       label: "Шлем",          short: "БАЦИНЕТ", zones: ["head"],              layers: [1,2,3], picked: "i-helm-01" },
    { id: "aventail",   label: "Авентейл",      short: "АВЕНТЕЙЛ",zones: ["neck","shoulderL","shoulderR"], layers: [2], picked: "i-helm-01" }, // bundled w/ bascinet
    { id: "gambeson",   label: "Гамбезон",      short: "ГАМБЕЗОН", zones: ["chest","waist","upperArmL","upperArmR","forearmL","forearmR"], layers: [1], picked: "i-gam-01" },
    { id: "haubergeon", label: "Хауберк",       short: "КОЛЬЧУГА", zones: ["chest","waist","groin","upperArmL","upperArmR"], layers: [2], picked: "i-mail-01" },
    { id: "cuirass",    label: "Кираса / КП",   short: "КИРАСА",   zones: ["chest"],             layers: [3], picked: "i-cui-01" },
    { id: "pauldron",   label: "Наплечники",    short: "ПЛЕЧИ",    zones: ["shoulderL","shoulderR"], layers: [3], picked: null },
    { id: "rerebrace",  label: "Наручи (верх)", short: "НАРУЧИ",   zones: ["upperArmL","upperArmR"], layers: [3], picked: "i-arm-01" },
    { id: "couter",     label: "Налокотники",   short: "ЛОКТИ",    zones: ["elbowL","elbowR"],   layers: [3], picked: "i-arm-01" },
    { id: "vambrace",   label: "Поручи",        short: "ПРЕДПЛ.",  zones: ["forearmL","forearmR"], layers: [3], picked: "i-arm-01" },
    { id: "gauntlet",   label: "Латные перчатки",short:"ПЕРЧАТКИ", zones: ["handL","handR"],     layers: [3], picked: null },
    { id: "cuisse",     label: "Набедренники",  short: "БЁДРА",    zones: ["thighL","thighR"],   layers: [3], picked: null },
    { id: "poleyn",     label: "Наколенники",   short: "КОЛЕНИ",   zones: ["kneeL","kneeR"],     layers: [3], picked: "i-leg-01", conflict: true }, // mismatched period
    { id: "greave",     label: "Поножи",        short: "ГОЛЕНИ",   zones: ["shinL","shinR"],     layers: [3], picked: null },
    { id: "sabaton",    label: "Сабатоны",      short: "СТОПЫ",    zones: ["footL","footR"],     layers: [3], picked: null },
  ],
};

/* Marketplace items — original placeholder data */
window.ITEMS = [
  {
    id: "i-helm-01",
    slot: "helm",
    title: "Бацинет с авентейлом «нюрнбергского» типа",
    subtype: "Bascinet w/ aventail",
    period: "ок. 1380–1400",
    region: "Прага",
    discipline: "HMB / реконструкция",
    master: "Мастерская Жихаря",
    condition: "new",
    price: 78400,
    currency: "₽",
    city: "Москва",
    image: "helm",
  },
  {
    id: "i-cui-01",
    slot: "cuirass",
    title: "Кираса с подвесом для тассетов",
    subtype: "Breastplate, hinged",
    period: "к. XIV в.",
    region: "Богемия",
    discipline: "HMB",
    master: "Forge Brünn",
    condition: "used",
    price: 64500,
    city: "Минск",
    image: "cuirass",
  },
  {
    id: "i-arm-01",
    slot: "rerebrace",
    title: "Руки комплект: наручи · локти · поручи",
    subtype: "Arm harness, full",
    period: "ок. 1370",
    region: "Нюрнберг",
    discipline: "HMB / HEMA",
    master: "Кузница «Чёрный Ворон»",
    condition: "new",
    price: 41000,
    city: "СПб",
    image: "arm",
    tags: ["комплект"],
  },
  {
    id: "i-leg-01",
    slot: "poleyn",
    title: "Наколенники со створками, ранний тип",
    subtype: "Poleyns, early",
    period: "ок. 1340 ⚠ ранний для архетипа",
    region: "Италия",
    discipline: "реконструкция",
    master: "—",
    condition: "used",
    price: 9800,
    city: "Казань",
    image: "leg",
    conflictNote: "период раньше архетипа на ~40 лет",
  },
  {
    id: "i-mail-01",
    slot: "haubergeon",
    title: "Хауберк клёпаный, плоское кольцо",
    subtype: "Haubergeon, riveted flat",
    period: "XIV в.",
    region: "—",
    discipline: "HMB",
    master: "MailWorks RU",
    condition: "used",
    price: 52000,
    city: "Тверь",
    image: "mail",
  },
  {
    id: "i-gam-01",
    slot: "gambeson",
    title: "Гамбезон стёганый, лён 12 слоёв",
    subtype: "Gambeson, linen",
    period: "к. XIV в.",
    region: "Чехия",
    discipline: "HMB / LARP",
    master: "Швейная Прага",
    condition: "new",
    price: 14800,
    city: "Прага",
    image: "gambeson",
  },
  {
    id: "i-gaunt-01",
    slot: "gauntlet",
    title: "Латные перчатки «песочные часы»",
    subtype: "Hourglass gauntlets",
    period: "ок. 1380",
    region: "Германия",
    discipline: "HMB",
    master: "Ferrum Werk",
    condition: "new",
    price: 36900,
    city: "Минск",
    image: "gauntlet",
  },
  {
    id: "i-paul-01",
    slot: "pauldron",
    title: "Наплечники сегментные",
    subtype: "Spaulders, segmented",
    period: "к. XIV в.",
    region: "Нюрнберг",
    discipline: "HMB",
    master: "Forge Brünn",
    condition: "new",
    price: 28400,
    city: "Минск",
    image: "spaulder",
  },
  {
    id: "i-cuisse-01",
    slot: "cuisse",
    title: "Набедренники с тассетами",
    subtype: "Cuisses",
    period: "к. XIV в.",
    region: "Чехия",
    discipline: "HMB",
    master: "Мастерская Жихаря",
    condition: "new",
    price: 33200,
    city: "Москва",
    image: "cuisse",
  },
  {
    id: "i-greave-01",
    slot: "greave",
    title: "Поножи створчатые",
    subtype: "Greaves, hinged",
    period: "ок. 1390",
    region: "Италия",
    discipline: "HMB",
    master: "Officina Visconti",
    condition: "used",
    price: 21500,
    city: "Милан",
    image: "greave",
  },
  {
    id: "i-sab-01",
    slot: "sabaton",
    title: "Сабатоны чешуйчатые",
    subtype: "Sabatons, lamellar",
    period: "к. XIV в.",
    region: "Богемия",
    discipline: "HMB",
    master: "—",
    condition: "used",
    price: 12000,
    city: "Брно",
    image: "sabaton",
  },
  {
    id: "i-sword-01",
    slot: "weapon",
    title: "Меч одноручный XIIIа",
    subtype: "Arming sword, Oakeshott XIIIa",
    period: "к. XIV в.",
    region: "—",
    discipline: "HMB / HEMA",
    master: "Albion-style",
    condition: "new",
    price: 47000,
    city: "СПб",
    image: "sword",
  },

  /* ─── additional listings per slot to fill the inventory grid ─── */
  { id: "i-helm-02",  slot: "helm",      title: "Бацинет «свиное рыло», без авентейла",
    subtype: "Hounskull bascinet", period: "ок. 1390", region: "Италия",
    discipline: "HMB", master: "Officina Visconti", condition: "used",
    price: 52000, city: "Минск", image: "helm" },
  { id: "i-helm-03",  slot: "helm",      title: "Бацинет купольный, ранний",
    subtype: "Bascinet, early dome", period: "ок. 1360", region: "Чехия",
    discipline: "реконструкция", master: "Кузница «Чёрный Ворон»",
    condition: "new", price: 64500, city: "Брно", image: "helm" },

  { id: "i-cui-02",   slot: "cuirass",   title: "КП на тканевой основе с заклёпками",
    subtype: "Coat of plates", period: "ок. 1370", region: "Германия",
    discipline: "HMB", master: "Ferrum Werk", condition: "used",
    price: 38000, city: "Калининград", image: "cuirass" },
  { id: "i-cui-03",   slot: "cuirass",   title: "Кираса с тассетами комплект",
    subtype: "Breastplate + fauld", period: "к. XIV в.", region: "Италия",
    discipline: "HMB", master: "Officina Visconti", condition: "new",
    price: 84000, city: "Милан", image: "cuirass" },

  { id: "i-arm-02",   slot: "rerebrace", title: "Наручи створчатые сегментные",
    subtype: "Splinted arm harness", period: "ок. 1370", region: "Чехия",
    discipline: "HMB", master: "Forge Brünn", condition: "used",
    price: 22000, city: "Брно", image: "arm" },

  { id: "i-leg-02",   slot: "poleyn",    title: "Наколенники с боковыми крыльями",
    subtype: "Poleyns, winged", period: "к. XIV в.", region: "Чехия",
    discipline: "HMB", master: "Forge Brünn", condition: "new",
    price: 18400, city: "Брно", image: "leg" },

  { id: "i-mail-02",  slot: "haubergeon",title: "Хауберк лужёный",
    subtype: "Haubergeon, tinned", period: "XIV в.", region: "—",
    discipline: "HMB", master: "MailWorks RU", condition: "new",
    price: 72000, city: "Тверь", image: "mail" },
  { id: "i-mail-03",  slot: "haubergeon",title: "Хауберк длиной до колена",
    subtype: "Long haubergeon", period: "ок. 1380", region: "—",
    discipline: "реконструкция", master: "—", condition: "used",
    price: 38000, city: "Псков", image: "mail" },

  { id: "i-gam-02",   slot: "gambeson",  title: "Гамбезон с короткими рукавами",
    subtype: "Short-sleeve gambeson", period: "к. XIV в.", region: "Германия",
    discipline: "HMB", master: "Швейная Прага", condition: "used",
    price: 8400, city: "Прага", image: "gambeson" },

  { id: "i-gaunt-02", slot: "gauntlet",  title: "Латные перчатки сегментные",
    subtype: "Mitten gauntlets", period: "ок. 1370", region: "Чехия",
    discipline: "HMB", master: "Forge Brünn", condition: "used",
    price: 22000, city: "Брно", image: "gauntlet" },

  { id: "i-paul-02",  slot: "pauldron",  title: "Наплечники с крылом",
    subtype: "Spaulders, winged", period: "к. XIV в.", region: "Италия",
    discipline: "HMB", master: "Officina Visconti", condition: "used",
    price: 19500, city: "Милан", image: "spaulder" },

  { id: "i-cuisse-02",slot: "cuisse",    title: "Набедренники с малыми тассетами",
    subtype: "Short cuisses", period: "ок. 1380", region: "Германия",
    discipline: "HMB", master: "Ferrum Werk", condition: "used",
    price: 22800, city: "Минск", image: "cuisse" },

  { id: "i-greave-02",slot: "greave",    title: "Поножи закрытые с шарниром",
    subtype: "Greaves, closed", period: "к. XIV в.", region: "Чехия",
    discipline: "HMB", master: "Forge Brünn", condition: "new",
    price: 28400, city: "Брно", image: "greave" },

  { id: "i-sab-02",   slot: "sabaton",   title: "Сабатоны пластинчатые узкий мысок",
    subtype: "Sabatons, pointed", period: "ок. 1380", region: "Италия",
    discipline: "HMB", master: "Officina Visconti", condition: "new",
    price: 16800, city: "Милан", image: "sabaton" },

  { id: "i-sword-02", slot: "weapon",    title: "Полутораручный меч XVa",
    subtype: "Longsword, Oakeshott XVa", period: "к. XIV в.", region: "Германия",
    discipline: "HMB / HEMA", master: "Albion-style", condition: "new",
    price: 58000, city: "СПб", image: "sword" },
  { id: "i-sword-03", slot: "weapon",    title: "Тесак боевой",
    subtype: "Falchion", period: "XIV в.", region: "Чехия",
    discipline: "HMB", master: "—", condition: "used",
    price: 24000, city: "Прага", image: "sword" },
];

/* Featured item for the item-card screen */
window.FEATURED_ITEM_ID = "i-helm-01";

/* Detail blob keyed by item id (only featured has full data) */
window.ITEM_DETAILS = {
  "i-helm-01": {
    photos: 6,
    measurements: [
      { k: "Обхват головы",  v: "57–60 см",        note: "регулируется подбоем" },
      { k: "Высота купола",  v: "215 мм",          note: "" },
      { k: "Толщина стали",  v: "2,0 мм / 2,5 мм", note: "верх / лицевая часть" },
      { k: "Масса",          v: "2,9 кг",          note: "с авентейлом" },
      { k: "Авентейл",       v: "клёпаный, ⌀8 мм", note: "плоское кольцо" },
    ],
    material: "Сталь конструкционная, термообработка. Авентейл — клёпаное кольцо.",
    construction: "Купол выкован из одного листа. Личина «свиное рыло» съёмная, на двух шарнирах с зашплинтованной осью.",
    provenance: [
      { date: "2024.03", text: "Изготовлен в мастерской Жихаря по заказу клуба «Богемская корона», Прага." },
      { date: "2024.09", text: "Турнир Battle of the Nations, отбор. Без боевых повреждений." },
      { date: "2025.02", text: "Продаётся в связи с переходом владельца на конную дисциплину." },
    ],
    referenceArtifact: {
      title: "Бацинет из Пражского Града, инв. № PH-1378-bA",
      blurb: "Атрибуция: пражская мастерская, ок. 1390. Бацинет «нюрнбергского» типа с креплением авентейла через вервель.",
    },
    market: {
      mine: 78400,
      median: 71000,
      p25: 58000,
      p75: 92000,
      newCount: 12,
      usedCount: 19,
      avgListingAge: "23 дня",
      myPercentile: 64,
    },
    fitsArchetypes: [
      { id: "ck14", label: "Чешский рыцарь, к. XIV в.", fit: 1.0 },
      { id: "tk13", label: "Тевтонец, сер. XIII в.",     fit: 0.4, note: "поздновато на ~120 лет" },
      { id: "kp14", label: "Копейщик-пехотинец, к. XIV в.", fit: 0.85 },
    ],
    seller: {
      name: "Мастерская Жихаря",
      handle: "@zhihar.forge",
      since: "на HMB-Market с 2022",
      rep: 4.9,
      reviewCount: 86,
      role: "Мастер · верифицирован",
    },
  },
};

/* Price analytics points for the featured-item market block */
window.PRICE_POINTS = [
  // x = price in k₽, y = used (0) or new (1), id
  { x: 38, c: "used" }, { x: 42, c: "used" }, { x: 46, c: "used" },
  { x: 48, c: "used" }, { x: 52, c: "used" }, { x: 55, c: "used" },
  { x: 58, c: "used" }, { x: 60, c: "used" }, { x: 62, c: "used" },
  { x: 64, c: "used" }, { x: 66, c: "used" }, { x: 68, c: "used" },
  { x: 70, c: "used" }, { x: 72, c: "used" }, { x: 74, c: "used" },
  { x: 76, c: "used" }, { x: 80, c: "used" }, { x: 84, c: "used" },
  { x: 88, c: "used" },
  { x: 64, c: "new"  }, { x: 68, c: "new"  }, { x: 72, c: "new"  },
  { x: 76, c: "new"  }, { x: 78, c: "new", mine: true }, { x: 80, c: "new" },
  { x: 84, c: "new"  }, { x: 88, c: "new"  }, { x: 92, c: "new" },
  { x: 96, c: "new"  }, { x:104, c: "new"  }, { x:118, c: "new" },
];

window.formatPrice = (n, c="₽") => new Intl.NumberFormat("ru-RU").format(n) + "\u00A0" + c;

/* ══════════════════════════════════════════════════════════════════
   РЕЕСТР — двунаправленная модель рынка (добавлено 05.09.2026)
   Всё ниже — синтетические плейсхолдеры, как и ITEMS выше.
   Не цитировать как рыночные данные (CLAUDE.md § «Ловушки домена»).
   ══════════════════════════════════════════════════════════════════ */

/* ── разбор датировки в окно лет ────────────────────────────────── */
const ROMAN = { IX:9, X:10, XI:11, XII:12, XIII:13, XIV:14, XV:15, XVI:16, XVII:17 };

window.parsePeriod = (s) => {
  if (!s) return null;
  const txt = String(s);

  // явные годы: 1380–1400 / 1380-1400 / ок. 1370
  const years = (txt.match(/\b(1[0-9]{3})\b/g) || []).map(Number);
  if (years.length >= 2) return { from: Math.min(...years), to: Math.max(...years) };
  if (years.length === 1) {
    const approx = /ок\.|около|~/i.test(txt);
    return approx ? { from: years[0] - 10, to: years[0] + 10 }
                  : { from: years[0], to: years[0] };
  }

  // римские века: XII–XIII вв. / к. XIV в. / сер. XIII в.
  const rom = txt.toUpperCase().match(/\b(X{0,2}(?:IX|IV|V?I{0,3}))\b/g) || [];
  const cents = rom.map(r => ROMAN[r]).filter(Boolean);
  if (cents.length === 0) return null;
  const c1 = Math.min(...cents), c2 = Math.max(...cents);
  let from = (c1 - 1) * 100, to = c2 * 100;
  if (cents.length === 1) {
    // ⚠ \b — граница ASCII-слова и перед кириллицей НЕ срабатывает
    //   (родня ловушки «\b в Postgres regex — это BACKSPACE», CLAUDE.md).
    //   Поэтому «ок.» вырезаем явно, а «к.» / «н.» ищем по соседям, а не по \b.
    const t = txt.replace(/ок\./gi, " ");
    const late  = /(^|[\s.,(])к\./i.test(t) || /конец|поздн/i.test(txt);
    const early = /(^|[\s.,(])н\./i.test(t) || /нач|ранн/i.test(txt);
    const mid   = /сер\.|середин/i.test(txt);
    if (late)       from = (c1 - 1) * 100 + 70;
    else if (early) to   = (c1 - 1) * 100 + 30;
    else if (mid) { from = (c1 - 1) * 100 + 30; to = (c1 - 1) * 100 + 70; }
  }
  return { from, to };
};

/* окна не пересекаются → конфликт периода */
window.periodConflict = (lotPeriod, archFrom, archTo) => {
  const w = window.parsePeriod(lotPeriod);
  if (!w) return null;
  if (w.to < archFrom) return { kind: "early", years: archFrom - w.to };
  if (w.from > archTo) return { kind: "late",  years: w.from - archTo };
  return null;
};

/* окно архетипа «Чешский рыцарь, к. XIV в.» */
window.ARCHETYPE_CK14.yearFrom = 1370;
window.ARCHETYPE_CK14.yearTo   = 1400;
window.ARCHETYPE_CK14.ruleset  = "bi";

/* ── антропометрия покупателя (профиль) ─────────────────────────── */
window.MY_BODY = {
  head:   58,   // обхват головы, см
  chest: 108,   // обхват груди
  arm:    64,   // длина руки от плеча
  thigh:  60,   // обхват бедра
  shin:   42,   // длина голени
  foot:   44,   // размер стопы
};

/* ── обмеры лотов (то, чего почти всегда нет в объявлениях) ─────── */
window.ITEM_MEASURES = {
  "i-helm-01":   { head: [57, 60], steel: 2.0, kg: 2.9 },
  "i-helm-02":   { head: [59, 62], steel: 1.8, kg: 3.1 },
  "i-helm-03":   { head: [55, 57], steel: 2.0, kg: 2.6 },
  "i-cui-01":    { chest: [104, 112], steel: 1.5, kg: 5.4 },
  "i-cui-02":    { chest: [96, 104], steel: 1.2, kg: 6.0 },
  "i-cui-03":    { chest: [110, 118], steel: 1.5, kg: 6.2 },
  "i-arm-01":    { arm: [62, 66], steel: 1.5, kg: 3.4 },
  "i-arm-02":    { arm: [58, 62], steel: 1.2, kg: 2.9 },
  "i-leg-01":    { steel: 1.2, kg: 1.1 },
  "i-leg-02":    { steel: 1.5, kg: 1.3 },
  "i-mail-01":   { chest: [100, 120], kg: 9.8 },
  "i-mail-02":   { chest: [104, 124], kg: 11.2 },
  "i-gam-01":    { chest: [104, 112], kg: 2.4 },
  "i-gaunt-01":  { steel: 1.5, kg: 1.9 },
  "i-paul-01":   { steel: 1.5, kg: 2.2 },
  "i-cuisse-01": { thigh: [56, 62], steel: 1.5, kg: 2.6 },
  "i-greave-01": { shin: [40, 44], steel: 1.5, kg: 1.8 },
  "i-sab-01":    { foot: [42, 44], steel: 1.2, kg: 1.4 },
};

/* ── источники: откуда пришла запись ────────────────────────────── */
window.SOURCES = {
  tg:     { label: "Telegram", glyph: "TG", tone: "steel"  },
  vk:     { label: "VK",       glyph: "VK", tone: "steel"  },
  forum:  { label: "Форум",    glyph: "FR", tone: ""       },
  shop:   { label: "Магазин",  glyph: "SH", tone: "patina" },
  manual: { label: "Вручную",  glyph: "MN", tone: ""       },
};

/* привязка лотов к источникам и возрасту объявления (дней) */
window.ITEM_META = {
  "i-helm-01":{src:"tg",age:3},   "i-helm-02":{src:"tg",age:11},  "i-helm-03":{src:"shop",age:26},
  "i-cui-01": {src:"vk",age:7},   "i-cui-02": {src:"forum",age:34},"i-cui-03":{src:"shop",age:19},
  "i-arm-01": {src:"shop",age:2}, "i-arm-02": {src:"tg",age:16},
  "i-leg-01": {src:"vk",age:41},  "i-leg-02": {src:"tg",age:5},
  "i-mail-01":{src:"forum",age:22},"i-mail-02":{src:"shop",age:9}, "i-mail-03":{src:"vk",age:58},
  "i-gam-01": {src:"shop",age:1}, "i-gam-02": {src:"tg",age:13},
  "i-gaunt-01":{src:"shop",age:6},"i-gaunt-02":{src:"vk",age:29},
  "i-paul-01":{src:"shop",age:4}, "i-paul-02":{src:"tg",age:18},
  "i-cuisse-01":{src:"shop",age:8},"i-cuisse-02":{src:"vk",age:24},
  "i-greave-01":{src:"forum",age:37},"i-greave-02":{src:"shop",age:12},
  "i-sab-01": {src:"tg",age:20},  "i-sab-02": {src:"shop",age:15},
  "i-sword-01":{src:"shop",age:5},"i-sword-02":{src:"shop",age:10},"i-sword-03":{src:"vk",age:44},
};

/* ── СПРОС: запросы «ищу» — вторая сторона реестра ──────────────── */
window.WANTS = [
  { id:"w-01", slot:"helm",       title:"Бацинет под голову 58, без личины",
    period:"к. XIV в.", region:"Германия", condition:"used", budget:60000, currency:"₽",
    city:"Алматы", need:{head:58}, src:"tg", age:2, urgency:"турнир 12.10" },
  { id:"w-02", slot:"cuirass",    title:"Кираса или КП на грудь 108–112",
    period:"XIV в.", region:"любой", condition:"used", budget:55000, currency:"₽",
    city:"Астана", need:{chest:110}, src:"tg", age:6 },
  { id:"w-03", slot:"gauntlet",   title:"Перчатки «песочные часы», любой износ",
    period:"к. XIV в.", region:"Германия", condition:"any", budget:28000, currency:"₽",
    city:"Москва", need:{}, src:"vk", age:1, urgency:"срочно" },
  { id:"w-04", slot:"greave",     title:"Поножи под голень 42",
    period:"XIV–XV вв.", region:"любой", condition:"used", budget:16000, currency:"₽",
    city:"Алматы", need:{shin:42}, src:"tg", age:9 },
  { id:"w-05", slot:"haubergeon", title:"Хауберк клёпаный, грудь 108+",
    period:"XIV в.", region:"любой", condition:"used", budget:40000, currency:"₽",
    city:"Бишкек", need:{chest:108}, src:"forum", age:15 },
  { id:"w-06", slot:"pauldron",   title:"Наплечники сегментные, пара",
    period:"к. XIV в.", region:"Чехия", condition:"any", budget:22000, currency:"₽",
    city:"СПб", need:{}, src:"vk", age:4 },
  { id:"w-07", slot:"sabaton",    title:"Сабатоны 44, узкий мысок",
    period:"XIV в.", region:"Италия", condition:"used", budget:12000, currency:"₽",
    city:"Астана", need:{foot:44}, src:"tg", age:12 },
  { id:"w-08", slot:"gambeson",   title:"Поддоспешник под грудь 108, короткий рукав",
    period:"к. XIV в.", region:"любой", condition:"new", budget:14000, currency:"₽",
    city:"Алматы", need:{chest:108}, src:"tg", age:3, urgency:"турнир 12.10" },
  { id:"w-09", slot:"cuisse",     title:"Набедренники под бедро 60",
    period:"XIV в.", region:"любой", condition:"used", budget:20000, currency:"₽",
    city:"Караганда", need:{thigh:60}, src:"vk", age:21 },
  { id:"w-10", slot:"helm",       title:"Шлем степной, XIII–XIV, под Орду",
    period:"XIII–XIV вв.", region:"Степь", condition:"any", budget:70000, currency:"₽",
    city:"Астана", need:{head:59}, src:"tg", age:7 },
  { id:"w-11", slot:"rerebrace",  title:"Комплект руки целиком, рука 64",
    period:"к. XIV в.", region:"Нюрнберг", condition:"used", budget:35000, currency:"₽",
    city:"Минск", need:{arm:64}, src:"forum", age:18 },
  { id:"w-12", slot:"weapon",     title:"Одноручный меч под ИСБ, допуск BI",
    period:"XIV в.", region:"любой", condition:"any", budget:38000, currency:"₽",
    city:"Алматы", need:{}, src:"tg", age:5 },
  { id:"w-13", slot:"poleyn",     title:"Наколенники, строго к. XIV",
    period:"к. XIV в.", region:"Чехия", condition:"used", budget:14000, currency:"₽",
    city:"Прага", need:{}, src:"vk", age:26 },
  { id:"w-14", slot:"cuirass",    title:"КП на тканевой основе, грудь 96–104",
    period:"ок. 1370", region:"Германия", condition:"any", budget:34000, currency:"₽",
    city:"Екатеринбург", need:{chest:100}, src:"tg", age:11 },
];

/* ── МАСТЕРА ────────────────────────────────────────────────────── */
window.MAKERS = [
  { id:"m-01", title:"Мастерская Жихаря",     country:"RU", city:"Москва", lead:70,  queue:true,  spec:["helm","cuisse"],            rating:4.9 },
  { id:"m-02", title:"Forge Brünn",           country:"CZ", city:"Брно",   lead:120, queue:false, spec:["cuirass","greave","gauntlet"], rating:4.8 },
  { id:"m-03", title:"Кузница «Чёрный Ворон»",country:"RU", city:"СПб",    lead:90,  queue:true,  spec:["rerebrace","couter"],       rating:4.6 },
  { id:"m-04", title:"Ferrum Werk",           country:"BY", city:"Минск",  lead:45,  queue:true,  spec:["gauntlet","cuisse"],        rating:4.7 },
  { id:"m-05", title:"Officina Visconti",     country:"IT", city:"Милан",  lead:150, queue:false, spec:["sabaton","pauldron"],       rating:4.9 },
  { id:"m-06", title:"MailWorks",             country:"RU", city:"Тверь",  lead:30,  queue:true,  spec:["haubergeon"],               rating:4.5 },
  { id:"m-07", title:"Дала-Темир",            country:"KZ", city:"Алматы", lead:35,  queue:true,  spec:["helm","haubergeon"],        rating:4.4 },
  { id:"m-08", title:"Швейная Прага",         country:"CZ", city:"Прага",  lead:21,  queue:true,  spec:["gambeson"],                 rating:4.8 },
];

/* ── УСЛУГИ: ремонт · подгонка · ковка · расходники · оценка ────── */
window.SERVICE_KINDS = {
  repair:     { label:"Ремонт",     glyph:"РМ" },
  refit:      { label:"Подгонка",   glyph:"ПД" },
  custom:     { label:"На заказ",   glyph:"ЗК" },
  consumable: { label:"Расходники", glyph:"РХ" },
  appraisal:  { label:"Оценка",     glyph:"ОЦ" },
  logistics:  { label:"Доставка",   glyph:"ЛГ" },
};

window.SERVICES = [
  { id:"s-01", kind:"repair",     maker:"m-07", title:"Правка вмятин, переклёпка узлов",       scope:["cuirass","helm","pauldron"], price:8000,  currency:"₽", days:5,  city:"Алматы", remote:false, src:"tg", age:4 },
  { id:"s-02", kind:"refit",      maker:"m-04", title:"Подгонка чужой кирасы под фигуру",      scope:["cuirass"],                   price:12000, currency:"₽", days:10, city:"Минск",  remote:true,  src:"vk", age:8 },
  { id:"s-03", kind:"consumable", maker:"m-08", title:"Ремни, пряжки, вкладыши — комплект",    scope:["*"],                         price:3200,  currency:"₽", days:2,  city:"Прага",  remote:true,  src:"shop", age:1 },
  { id:"s-04", kind:"custom",     maker:"m-02", title:"Ковка кирасы по обмерам, к. XIV",       scope:["cuirass"],                   price:74000, currency:"₽", days:120,city:"Брно",   remote:true,  src:"shop", age:14 },
  { id:"s-05", kind:"appraisal",  maker:"m-03", title:"Оценка б/у: толщина, трещины, допуск",  scope:["*"],                         price:2500,  currency:"₽", days:1,  city:"СПб",    remote:true,  src:"forum", age:19 },
  { id:"s-06", kind:"consumable", maker:"m-06", title:"Кольцо клёпаное на ремонт кольчуги",    scope:["haubergeon"],                price:1800,  currency:"₽", days:3,  city:"Тверь",  remote:true,  src:"shop", age:6 },
  { id:"s-07", kind:"repair",     maker:"m-01", title:"Ремонт шлема после турнира",            scope:["helm"],                      price:6500,  currency:"₽", days:7,  city:"Москва", remote:false, src:"tg", age:2 },
  { id:"s-08", kind:"refit",      maker:"m-07", title:"Перешив поддоспешника под грудь",       scope:["gambeson"],                  price:5400,  currency:"₽", days:6,  city:"Алматы", remote:false, src:"tg", age:10 },
  { id:"s-09", kind:"logistics",  maker:"m-07", title:"Консолидация и доставка ЕАЭС, 30 кг",   scope:["*"],                         price:14000, currency:"₽", days:12, city:"Алматы", remote:true,  src:"manual", age:5 },
  { id:"s-10", kind:"custom",     maker:"m-05", title:"Сабатоны по слепку стопы",              scope:["sabaton"],                   price:31000, currency:"₽", days:150,city:"Милан",  remote:true,  src:"shop", age:23 },
];

/* ── вердикт по размеру: fits / refit / no / unknown ─────────────── */
window.fitVerdict = (measures, body) => {
  if (!measures) return "unknown";
  const keys = ["head","chest","arm","thigh","shin","foot"];
  let seen = 0, worst = "fits";
  for (const k of keys) {
    const rng = measures[k];
    if (!rng || !body[k]) continue;
    seen++;
    const [lo, hi] = rng;
    if (body[k] >= lo && body[k] <= hi) continue;
    const off = body[k] < lo ? lo - body[k] : body[k] - hi;
    if (off <= 4) { if (worst === "fits") worst = "refit"; }
    else return "no";
  }
  return seen === 0 ? "unknown" : worst;
};

/* добавлено 05.09.2026 после теста: без этих запросов блок «дефицит рынка»
   был пуст — спрос ни по одному слоту не превышал предложение, и фича
   выглядела мёртвой. Перчатки и сабатоны выбраны не случайно: это самые
   ломающиеся и самые трудные по посадке позиции. */
window.WANTS.push(
  { id:"w-15", slot:"gauntlet", title:"Латные перчатки, любые, под ремонт",
    period:"XIV в.", region:"любой", condition:"any", budget:15000, currency:"₽",
    city:"Алматы", need:{}, src:"tg", age:1, urgency:"сломал на турнире" },
  { id:"w-16", slot:"gauntlet", title:"Митенки или «часы», рука 64",
    period:"к. XIV в.", region:"любой", condition:"used", budget:24000, currency:"₽",
    city:"Астана", need:{arm:64}, src:"tg", age:8 },
  { id:"w-17", slot:"gauntlet", title:"Перчатки левая отдельно",
    period:"XIV–XV вв.", region:"любой", condition:"any", budget:9000, currency:"₽",
    city:"Новосибирск", need:{}, src:"vk", age:14 },
  { id:"w-18", slot:"sabaton",  title:"Сабатоны 43–44, любой тип",
    period:"XIV в.", region:"любой", condition:"any", budget:11000, currency:"₽",
    city:"Алматы", need:{foot:44}, src:"tg", age:6 },
  { id:"w-19", slot:"sabaton",  title:"Сабатоны чешуйчатые, Богемия",
    period:"к. XIV в.", region:"Чехия / Богемия", condition:"used", budget:13000, currency:"₽",
    city:"Прага", need:{}, src:"forum", age:31 },
  { id:"w-20", slot:"greave",   title:"Поножи створчатые, голень 42–44",
    period:"к. XIV в.", region:"любой", condition:"used", budget:18000, currency:"₽",
    city:"Бишкек", need:{shin:42}, src:"tg", age:10 },
  { id:"w-21", slot:"poleyn",   title:"Наколенники с крылом, пара",
    period:"к. XIV в.", region:"Чехия / Богемия", condition:"any", budget:16000, currency:"₽",
    city:"Астана", need:{}, src:"vk", age:17 }
);
