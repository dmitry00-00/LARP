/* HMB-Market — страница-агрегатор.
   Ванильный JS, без сборки и зависимостей: страница открывается двойным
   кликом (file://) и работает так же, будучи отданной сервером.
   Данные: data/feed.json по http(s), иначе встроенный seed.js.

   1 хранилище · 2 состояние · 3 данные · 4 домен-логика · 5 фильтр/сорт
   6 рендер · 7 события · 8 URL-состояние · 9 клавиатура */
(function () {
"use strict";

/* ═══ 1. Хранилище (localStorage с падением в память) ═══ */
var mem = {};
var store = {
  get: function (k, d) {
    try { var v = localStorage.getItem("hmb." + k); return v == null ? d : JSON.parse(v); }
    catch (e) { return k in mem ? mem[k] : d; }
  },
  set: function (k, v) {
    mem[k] = v;
    try { localStorage.setItem("hmb." + k, JSON.stringify(v)); } catch (e) {}
  }
};

/* ═══ 2. Состояние ═══ */
var S = {
  feed: null, rows: [], slotById: {}, archById: {}, makerById: {}, srcById: {},
  view: "all", q: "",
  f: { slot: "", cent: "", region: "", cond: "", src: "", country: "", maker: "" },
  priceMax: null,
  fitOnly: false, noConflict: false, hideStale: true,
  sort: { key: "age", asc: true },
  arch: store.get("arch", "ck14"),
  cur: store.get("cur", "KZT"),
  body: store.get("body", { head: 58, neck: 41, chest: 108, waist: 92, arm: 64, thigh: 60, shin: 42, foot: 44 }),
  subs: store.get("subs", []),
  seen: store.get("seen", {}),
  fav: store.get("fav", {}),
  open: null, modal: null
};

/* зоны тела для paperdoll — координаты те же, что в прототипе (320×560) */
var Z = {
  head:{cx:160,cy:60,w:62,h:72}, neck:{cx:160,cy:112,w:44,h:26},
  shoulderL:{cx:116,cy:144,w:44,h:34}, shoulderR:{cx:204,cy:144,w:44,h:34},
  chest:{cx:160,cy:188,w:108,h:74},
  upperArmL:{cx:98,cy:192,w:30,h:60}, upperArmR:{cx:222,cy:192,w:30,h:60},
  elbowL:{cx:92,cy:240,w:26,h:22}, elbowR:{cx:228,cy:240,w:26,h:22},
  forearmL:{cx:86,cy:274,w:26,h:52}, forearmR:{cx:234,cy:274,w:26,h:52},
  handL:{cx:82,cy:318,w:28,h:30}, handR:{cx:238,cy:318,w:28,h:30},
  waist:{cx:160,cy:254,w:96,h:34}, groin:{cx:160,cy:296,w:86,h:36},
  thighL:{cx:138,cy:358,w:40,h:74}, thighR:{cx:182,cy:358,w:40,h:74},
  kneeL:{cx:138,cy:412,w:36,h:24}, kneeR:{cx:182,cy:412,w:36,h:24},
  shinL:{cx:138,cy:460,w:34,h:64}, shinR:{cx:182,cy:460,w:34,h:64},
  footL:{cx:138,cy:510,w:44,h:28}, footR:{cx:182,cy:510,w:44,h:28}
};
var MEASURE_RU = { head:"обхват головы", neck:"обхват шеи", chest:"обхват груди",
  waist:"обхват талии", arm:"длина руки", thigh:"обхват бедра",
  shin:"длина голени", foot:"размер стопы" };
var COND_RU = { "new":"новое", used:"б/у", damaged:"под ремонт", any:"любое" };
var SVC_RU = { repair:"ремонт", refit:"подгонка", custom:"на заказ",
  consumable:"расходники", appraisal:"оценка", logistics:"доставка", rent:"аренда" };
var SVC_GL = { repair:"РМ", refit:"ПД", custom:"ЗК", consumable:"РХ",
  appraisal:"ОЦ", logistics:"ЛГ", rent:"АР" };

/* ═══ 3. Загрузка данных ═══ */
function boot() {
  var seed = window.HMB_SEED || null;
  if (location.protocol === "file:") { init(seed); return; }
  fetch("data/feed.json", { cache: "no-store" })
    .then(function (r) { if (!r.ok) throw 0; return r.json(); })
    .then(function (j) { init(j); })
    .catch(function () { init(seed); });
}

function init(feed) {
  if (!feed) {
    document.getElementById("app").innerHTML =
      '<div class="empty">Нет данных: ни <code>data/feed.json</code>, ни <code>seed.js</code>.</div>';
    return;
  }
  S.feed = feed;
  feed.slots.forEach(function (s) { S.slotById[s.id] = s; });
  feed.archetypes.forEach(function (a) { S.archById[a.id] = a; });
  feed.makers.forEach(function (m) { S.makerById[m.id] = m; });
  feed.sources.forEach(function (s) { S.srcById[s.id] = s; });
  if (!S.archById[S.arch]) S.arch = feed.archetypes[0].id;
  S.rows = feed.lots.map(normalize);
  readHash();
  renderShell();
  renderAll();
}

/* ═══ 4. Домен-логика ═══ */
function normalize(r) {
  var o = {}, k;
  for (k in r) o[k] = r[k];
  o.priceRub = o.price * (S.feed.rates[o.currency] || 1);
  var sl = o.slot ? S.slotById[o.slot] : null;
  o.slotLabel = sl ? sl.label : (o.dir === "service" ? "любой слот" : "—");
  o.slotShort = sl ? sl.short : "—";
  var mk = o.maker ? S.makerById[o.maker] : null;
  o.hay = [o.title, o.city, o.region, o.period, mk ? mk.title : "",
           sl ? sl.aliases.join(" ") : ""].join(" ").toLowerCase();
  return o;
}

/* размерный вердикт: fits | refit | no | unknown; допуск подгонки — 4 см */
function fitOf(row) {
  if (row.dir !== "offer") return null;
  var m = row.measures;
  if (!m || !Object.keys(m).length) return "unknown";
  var seen = 0, worst = "fits", k;
  for (k in m) {
    var body = S.body[k]; if (body == null) continue;
    seen++;
    var lo = m[k][0], hi = m[k][1];
    if (body >= lo && body <= hi) continue;
    var off = body < lo ? lo - body : body - hi;
    if (off <= 4) { if (worst === "fits") worst = "refit"; }
    else return "no";
  }
  return seen ? worst : "unknown";
}

/* конфликт периода с активным архетипом */
function conflictOf(row) {
  if (row.dir === "service" || row.yearFrom == null) return null;
  var a = S.archById[S.arch];
  if (row.yearTo < a.yearFrom) return { kind: "early", years: a.yearFrom - row.yearTo };
  if (row.yearFrom > a.yearTo) return { kind: "late", years: row.yearFrom - a.yearTo };
  return null;
}

function fmtCur(rub, cur) {
  cur = cur || S.cur;
  var v = rub / (S.feed.rates[cur] || 1);
  return new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 0 }).format(Math.round(v)) +
    " " + (S.feed.currencies[cur] || cur);
}
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
  });
}

/* ═══ 5. Фильтр и сортировка ═══ */
function pass(r) {
  if (S.view !== "all" && r.dir !== S.view) return false;
  if (S.hideStale && r.status !== "active") return false;
  if (S.q && r.hay.indexOf(S.q.toLowerCase()) === -1) return false;
  if (S.f.slot && r.slot !== S.f.slot) return false;
  if (S.f.region && r.region !== S.f.region) return false;
  if (S.f.cond && r.condition !== S.f.cond) return false;
  if (S.f.country && r.country !== S.f.country) return false;
  if (S.f.src && r.source !== S.f.src) return false;
  if (S.f.maker && r.maker !== S.f.maker) return false;
  if (S.f.cent) {
    var c1 = (+S.f.cent - 1) * 100, c2 = +S.f.cent * 100;
    if (r.yearFrom == null || r.yearTo <= c1 || r.yearFrom >= c2) return false;
  }
  if (S.priceMax != null && r.priceRub > S.priceMax) return false;
  if (S.fitOnly) { var f = fitOf(r); if (f !== "fits" && f !== "refit") return false; }
  if (S.noConflict && conflictOf(r)) return false;
  return true;
}
function visible() { return S.rows.filter(pass); }

function sortRows(rows) {
  var k = S.sort.key, sg = S.sort.asc ? 1 : -1;
  return rows.slice().sort(function (a, b) {
    var av, bv;
    if (k === "period") { av = a.yearFrom == null ? 9999 : a.yearFrom; bv = b.yearFrom == null ? 9999 : b.yearFrom; }
    else if (k === "price") { av = a.priceRub; bv = b.priceRub; }
    else if (k === "slot") { av = a.slotShort; bv = b.slotShort; }
    else { av = a[k]; bv = b[k]; }
    if (av == null) av = "";
    if (bv == null) bv = "";
    return av < bv ? -sg : av > bv ? sg : 0;
  });
}

function counts() {
  var c = { all: 0, offer: 0, want: 0, service: 0 };
  S.rows.forEach(function (r) {
    if (S.hideStale && r.status !== "active") return;
    c.all++; c[r.dir]++;
  });
  return c;
}

/* ═══ 6. Рендер ═══ */
function renderShell() {
  document.getElementById("app").innerHTML =
    '<div class="topbar">' +
      '<div class="brand"><span class="mark">' +
        '<svg width="20" height="20" viewBox="0 0 22 22" fill="none">' +
        '<path d="M3 3 L11 11 L19 3" stroke="currentColor" stroke-width="1.5"/>' +
        '<path d="M3 19 L11 11 L19 19" stroke="currentColor" stroke-width="1.5"/>' +
        '<circle cx="11" cy="11" r="2" fill="currentColor"/></svg></span>' +
        '<span class="name">HMB-Market<em>реестр</em></span></div>' +
      '<div class="tabs" id="tabs"></div><div class="spacer"></div>' +
      '<span class="pill" id="feedpill"></span>' +
      '<button class="btn ghost" data-act="cur" id="curbtn"></button>' +
      '<button class="btn" data-act="profile">профиль</button>' +
    '</div>' +
    '<div class="main">' +
      '<aside class="rail" id="railL"></aside>' +
      '<div class="center">' +
        '<div class="controls" id="controls"></div>' +
        '<div class="grid" id="grid"></div>' +
        '<div class="statusbar" id="status"></div>' +
      '</div>' +
      '<aside class="rail right" id="railR"></aside>' +
    '</div><div id="layer"></div>';
}

function renderAll() {
  renderTabs(); renderControls(); renderLeft(); renderTable(); renderRight(); renderStatus(); writeHash();
}

function renderTabs() {
  var c = counts();
  var t = [["all", "Реестр"], ["offer", "▲ Предложение"], ["want", "▼ Спрос"], ["service", "◆ Услуги"]];
  document.getElementById("tabs").innerHTML = t.map(function (x) {
    return '<button data-view="' + x[0] + '" class="' + (S.view === x[0] ? "on" : "") + '">' +
      esc(x[1]) + '<span class="n">' + c[x[0]] + "</span></button>";
  }).join("");
  document.getElementById("curbtn").textContent = S.feed.currencies[S.cur] + " " + S.cur;
  var m = S.feed.meta;
  document.getElementById("feedpill").innerHTML =
    '<span class="dot"></span>' + m.counts.offers + " ▲ · " + m.counts.wants + " ▼ · " + m.counts.services + " ◆";
}

function renderControls() {
  document.getElementById("controls").innerHTML =
    '<div class="search"><input id="q" placeholder="поиск: бацинет, 58, Алматы, Forge Brünn…" value="' + esc(S.q) + '"><kbd>/</kbd></div>' +
    '<label class="chk ' + (S.fitOnly ? "on" : "") + '" data-tgl="fitOnly"><i></i>подойдёт мне</label>' +
    '<label class="chk ' + (S.noConflict ? "on" : "") + '" data-tgl="noConflict"><i></i>без конфликта эпохи</label>' +
    '<label class="chk ' + (S.hideStale ? "on" : "") + '" data-tgl="hideStale"><i></i>скрыть протухшие</label>' +
    '<div style="flex:1"></div>' +
    '<button class="btn sm" data-act="savesub">+ подписка на фильтр</button>' +
    '<button class="btn sm ghost" data-act="reset">сброс</button>';
}

function facetCounts(field) {
  var m = {};
  S.rows.forEach(function (r) {
    if (S.hideStale && r.status !== "active") return;
    if (S.view !== "all" && r.dir !== S.view) return;
    var v = r[field]; if (!v) return;
    m[v] = (m[v] || 0) + 1;
  });
  return m;
}

function facetBlock(title, field, key, labeler) {
  var m = facetCounts(field);
  var keys = Object.keys(m).sort(function (a, b) { return m[b] - m[a]; }).slice(0, 12);
  if (!keys.length) return "";
  return '<div class="sec"><span class="eyebrow">' + esc(title) + '</span><div class="facet">' +
    keys.map(function (k) {
      return '<button data-f="' + key + '" data-v="' + esc(k) + '" class="' + (S.f[key] === k ? "on" : "") + '">' +
        "<span>" + esc(labeler ? labeler(k) : k) + '</span><span class="c">' + m[k] + "</span></button>";
    }).join("") + "</div></div>";
}

function renderLeft() {
  var subs = S.subs.map(function (s, i) {
    var n = matchSub(s);
    return '<div class="sub" data-sub="' + i + '">' +
      (n.fresh ? '<span class="badge">' + n.fresh + "</span>" : "") +
      '<div class="nm">' + esc(s.name) + "</div>" +
      '<div class="meta">' + n.total + " совпад." + (n.fresh ? " · " + n.fresh + " новых" : "") + "</div>" +
      '<button class="x" data-delsub="' + i + '" title="удалить">✕</button></div>';
  }).join("");

  var prices = S.rows.filter(function (r) { return r.dir !== "service" && r.priceRub; })
                     .map(function (r) { return r.priceRub; });
  var maxP = prices.length ? Math.max.apply(null, prices) : 100000;
  var bins = []; for (var i = 0; i < 22; i++) bins.push(0);
  prices.forEach(function (p) { bins[Math.min(21, Math.floor(p / maxP * 21))]++; });
  var mx = Math.max.apply(null, bins) || 1;
  var cut = S.priceMax == null ? maxP : S.priceMax;

  document.getElementById("railL").innerHTML =
    '<div class="sec"><span class="eyebrow">подписки · алерты</span>' +
      (subs || '<div class="notice">Настройте фильтр и нажмите «+ подписка»: реестр посчитает совпадения и подсветит новые.</div>') +
    "</div>" +
    '<div class="sec"><span class="eyebrow">цена, до</span>' +
      '<div class="hist">' + bins.map(function (b, i2) {
        var on = (i2 / 21) * maxP <= cut;
        return '<i class="' + (on ? "on" : "") + '" style="height:' + Math.max(2, b / mx * 100) + '%"></i>';
      }).join("") + "</div>" +
      '<input type="range" id="price" min="0" max="' + Math.round(maxP) + '" step="1000" value="' + Math.round(cut) + '">' +
      '<div class="kv"><span>потолок</span><span>' + fmtCur(cut) + "</span></div>" +
    "</div>" +
    facetBlock("слот", "slot", "slot", function (k) { return S.slotById[k] ? S.slotById[k].label : k; }) +
    facetBlock("регион стиля", "region", "region") +
    facetBlock("страна", "country", "country") +
    facetBlock("источник", "source", "src", function (k) { return S.srcById[k] ? S.srcById[k].ref : k; });
}

function renderTable() {
  var rows = sortRows(visible());
  var isSvc = S.view === "service";
  var cols = [["", "", ""], ["slot", "СЛОТ", ""], ["title", "НАИМЕНОВАНИЕ", ""],
    isSvc ? ["days", "СРОК", "r"] : ["period", "ПЕРИОД", ""],
    ["region", isSvc ? "СТРАНА" : "РЕГИОН", ""]];
  if (!isSvc) cols.push(["", "РАЗМЕР", ""], ["condition", "СОСТ", "c"]);
  cols.push(["price", isSvc ? "ОТ" : "ЦЕНА", "r"], ["city", "ГОРОД", ""],
            ["source", "ИСТ", "c"], ["age", "ВОЗР", "r"]);

  var head = cols.map(function (c) {
    var s = (S.sort.key === c[0] && c[0]) ? '<span class="s">' + (S.sort.asc ? " ↑" : " ↓") + "</span>" : "";
    return '<th class="' + c[2] + '"' + (c[0] ? ' data-sort="' + c[0] + '"' : "") + ">" + esc(c[1]) + s + "</th>";
  }).join("");

  var body = rows.map(function (r) {
    var cf = conflictOf(r), fit = fitOf(r);
    var mk = r.maker ? S.makerById[r.maker] : null;
    var src = S.srcById[r.source];
    var td = [];
    td.push('<td class="c dirmark dir-' + r.dir + '">' +
      (r.dir === "offer" ? "▲" : r.dir === "want" ? "▼" : "◆") + "</td>");
    td.push('<td class="mono t-nowrap" style="font-size:10px;letter-spacing:.09em;color:var(--fg-4)">' +
      (r.dir === "service" ? '<span style="color:var(--steel)">' + SVC_GL[r.kind] + "</span>" : esc(r.slotShort)) + "</td>");
    var sub = r.dir === "service"
      ? esc(mk ? mk.title : "") + " · " + esc(SVC_RU[r.kind])
      : r.dir === "want"
        ? (Object.keys(r.need || {}).length
            ? Object.keys(r.need).map(function (k) { return esc(MEASURE_RU[k] || k) + " " + r.need[k]; }).join(" · ")
            : "без обмеров")
        : (mk ? esc(mk.title) : "мастер не указан") + (r.photos ? " · " + r.photos + " фото" : " · без фото");
    td.push("<td><div class=\"t-title\">" + esc(r.title) + '</div><div class="t-sub">' + sub +
      (r.urgency ? ' <span style="color:var(--rust)">⚑ ' + esc(r.urgency) + "</span>" : "") + "</div></td>");
    if (isSvc) td.push('<td class="r mono t-nowrap">' + r.days + " дн.</td>");
    else td.push('<td class="mono t-nowrap" style="color:' + (cf ? "var(--rust)" : "var(--fg-3)") + '">' +
      esc(r.period) + (cf ? ' <span title="' + (cf.kind === "early" ? "раньше" : "позже") +
      " архетипа на ~" + cf.years + ' лет">⚠</span>' : "") + "</td>");
    td.push('<td class="t-nowrap" style="color:var(--fg-3);font-size:11.5px">' +
      esc(r.dir === "service" ? (mk ? mk.country : "") : r.region) + "</td>");
    if (!isSvc) {
      td.push("<td>" + (
        fit === "fits" ? '<span class="tag patina">подойдёт</span>' :
        fit === "refit" ? '<span class="tag brass">подгонка</span>' :
        fit === "no" ? '<span class="tag rust">не тот</span>' :
        fit === "unknown" ? '<span class="tag" title="в объявлении нет обмеров">нет обмеров</span>' :
        '<span class="mono dim" style="font-size:10px">запрос</span>') + "</td>");
      td.push('<td class="c"><span class="dot ' + (r.condition || "any") + '" title="' +
        esc(COND_RU[r.condition] || "") + '"></span></td>');
    }
    td.push('<td class="r num t-nowrap" style="color:var(--fg-1)">' +
      (r.dir === "want" ? '<span class="dim" style="font-size:10px">до </span>' : "") + fmtCur(r.priceRub) + "</td>");
    td.push('<td class="t-nowrap" style="color:var(--fg-3);font-size:11.5px">' + esc(r.city) + "</td>");
    td.push('<td class="mono c" style="font-size:9px;color:var(--fg-4)" title="' + esc(src ? src.ref : "") + '">' +
      esc(src ? src.kind.toUpperCase().slice(0, 2) : "—") + "</td>");
    td.push('<td class="r mono t-nowrap" style="font-size:10.5px;color:' +
      (r.age > 30 ? "var(--fg-5)" : r.age > 14 ? "var(--fg-4)" : "var(--fg-2)") + '">' + r.age + "д</td>");
    return '<tr data-id="' + r.id + '" class="' + (S.open === r.id ? "sel " : "") +
      (r.status !== "active" ? "stale" : "") + '">' + td.join("") + "</tr>";
  }).join("");

  document.getElementById("grid").innerHTML = rows.length
    ? '<table class="reg"><thead><tr>' + head + "</tr></thead><tbody>" + body + "</tbody></table>"
    : '<div class="empty"><div class="eyebrow">ничего не найдено</div>' +
      '<button class="btn" style="margin-top:14px" data-act="reset">сбросить фильтры</button></div>';
}

function paperdoll(size, focusSlot) {
  var a = S.archById[S.arch], W = 320, H = 560;
  var need = {}, focus = {};
  a.required.forEach(function (sid) {
    var s = S.slotById[sid]; if (!s) return;
    s.zones.forEach(function (z) { need[z] = 1; });
  });
  if (focusSlot && S.slotById[focusSlot]) {
    S.slotById[focusSlot].zones.forEach(function (z) { focus[z] = 1; });
  }
  var parts = Object.keys(Z).map(function (z) {
    var o = Z[z], on = need[z], fc = focus[z];
    return '<rect class="z" x="' + (o.cx - o.w / 2) + '" y="' + (o.cy - o.h / 2) +
      '" width="' + o.w + '" height="' + o.h + '" rx="3" fill="' +
      (fc ? "oklch(0.46 0.080 78 / 0.9)" : on ? "oklch(0.33 0.030 82 / 0.55)" : "transparent") +
      '" stroke="' + (fc ? "var(--accent)" : on ? "oklch(0.52 0.045 80 / 0.8)" : "var(--line-1)") + '" stroke-width="1"/>';
  }).join("");
  return '<svg class="pd" width="' + size + '" height="' + Math.round(size * H / W) +
    '" viewBox="0 0 ' + W + " " + H + '">' +
    '<g fill="oklch(0.20 0.010 100)" stroke="var(--line-1)" stroke-width="1">' +
    '<ellipse cx="160" cy="62" rx="30" ry="36"/><rect x="140" y="96" width="40" height="26" rx="8"/>' +
    '<path d="M112 128 L208 128 L214 268 L106 268 Z"/>' +
    '<rect x="76" y="140" width="30" height="190" rx="14"/><rect x="214" y="140" width="30" height="190" rx="14"/>' +
    '<path d="M118 268 L202 268 L206 320 Q160 332 114 320 Z"/>' +
    '<rect x="120" y="316" width="38" height="200" rx="16"/><rect x="162" y="316" width="38" height="200" rx="16"/>' +
    "</g>" + parts + "</svg>";
}

function renderRight() {
  var a = S.archById[S.arch], vis = visible();
  var m = {};
  S.rows.forEach(function (r) {
    if (r.dir === "service" || !r.slot || r.status !== "active") return;
    m[r.slot] = m[r.slot] || { offer: 0, want: 0 };
    m[r.slot][r.dir]++;
  });
  /* Напряжённость = запросов на одно предложение. Абсолютная разница
     ▼−▲ на этом корпусе даёт нули и минусы и ничего не показывает;
     отношение работает при любом размере выборки. */
  var def = Object.keys(m).map(function (k) {
    var o = m[k].offer, w = m[k].want;
    return { slot: k, o: o, w: w, t: o ? w / o : (w ? 99 : 0) };
  }).sort(function (x, y) { return y.t - x.t; }).slice(0, 7);

  var covered = 0;
  a.required.forEach(function (sid) {
    var has = S.rows.some(function (r) {
      return r.dir === "offer" && r.slot === sid && r.status === "active" &&
             !conflictOf(r) && (fitOf(r) === "fits" || fitOf(r) === "refit");
    });
    if (has) covered++;
  });
  var conflicted = vis.filter(function (r) { return !!conflictOf(r); }).length;

  document.getElementById("railR").innerHTML =
    '<div class="sec"><span class="eyebrow">архетип · регламент</span>' +
      '<select id="archsel" style="width:100%;background:oklch(0.21 0.013 100);border:1px solid var(--line-1);' +
      'border-radius:3px;padding:5px 7px;font-size:12.5px;color:var(--fg-1);outline:none">' +
      S.feed.archetypes.map(function (x) {
        return '<option value="' + x.id + '"' + (x.id === S.arch ? " selected" : "") + ">" +
          esc(x.title) + " · " + x.yearFrom + "–" + x.yearTo + "</option>";
      }).join("") + "</select>" +
      '<div class="mono" style="font-size:10px;color:var(--accent);margin-top:5px">' +
        a.yearFrom + "–" + a.yearTo + " · " + a.ruleset.toUpperCase() + " · " + esc(a.region) + "</div>" +
      '<div style="font-size:11.5px;color:var(--fg-4);margin-top:5px;line-height:1.4">' + esc(a.blurb) + "</div>" +
    "</div>" +
    '<div class="sec">' + paperdoll(172, null) + "</div>" +
    '<div class="sec" style="display:grid;grid-template-columns:1fr 1fr;gap:8px">' +
      '<div><span class="eyebrow">слот закрыт</span><div class="num" style="font-size:19px;color:var(--fg-1)">' +
        covered + "/" + a.required.length + "</div></div>" +
      '<div><span class="eyebrow">конфликтов</span><div class="num" style="font-size:19px;color:' +
        (conflicted ? "var(--rust)" : "var(--fg-4)") + '">' + conflicted + "</div></div>" +
    "</div>" +
    '<div class="sec"><span class="eyebrow">дефицит рынка</span>' +
      '<div style="font-size:11px;color:var(--fg-4);margin-bottom:6px;line-height:1.4">' +
        "запросов на одно предложение — где выше, там ищут мастера, а не лот</div>" +
      '<table class="mini"><thead><tr><th>слот</th><th>▲</th><th>▼</th><th>▼/▲</th></tr></thead><tbody>' +
      def.map(function (d) {
        var hot = d.t >= 0.8, warm = d.t >= 0.5;
        return '<tr data-f="slot" data-v="' + d.slot + '"><td style="color:var(--fg-2)">' +
          esc(S.slotById[d.slot].short) + "</td><td>" + d.o + "</td><td>" + d.w +
          '</td><td style="color:' + (hot ? "var(--rust)" : warm ? "var(--brass)" : "var(--fg-5)") + '">' +
          (d.t >= 99 ? "—" : d.t.toFixed(2)) + "</td></tr>";
      }).join("") + "</tbody></table></div>" +
    '<div class="sec"><span class="eyebrow">мои обмеры</span>' +
      Object.keys(S.body).map(function (k) {
        return '<div class="kv"><span>' + esc(MEASURE_RU[k] || k) + "</span><span>" + S.body[k] + " см</span></div>";
      }).join("") +
      '<button class="btn sm" style="margin-top:8px;width:100%" data-act="profile">изменить обмеры</button></div>';
}

function renderStatus() {
  var vis = visible(), m = S.feed.meta;
  var offers = vis.filter(function (r) { return r.dir === "offer"; });
  var withM = offers.filter(function (r) { return r.measures && Object.keys(r.measures).length; }).length;
  var withP = offers.filter(function (r) { return r.photos; }).length;
  document.getElementById("status").innerHTML =
    "<span><b>" + vis.length + "</b> из " + S.rows.length + " записей</span>" +
    "<span>с обмерами <b>" + (offers.length ? Math.round(withM / offers.length * 100) : 0) + "%</b>" +
    " · с фото <b>" + (offers.length ? Math.round(withP / offers.length * 100) : 0) + "%</b> предложений</span>" +
    "<span>источников <b>" + S.feed.sources.length + "</b></span>" +
    "<span>фид <b>" + esc(m.generated) + "</b>" + (m.synthetic ? " · демо-корпус, не рыночные данные" : "") + "</span>" +
    (m.ratesStub ? '<span style="color:var(--rust)">курс — заглушка</span>' : "");
}

/* ── боковая карточка лота ── */
function renderDrawer() {
  var lay = document.getElementById("layer");
  if (!S.open) { lay.innerHTML = ""; return; }
  var arr = S.rows.filter(function (x) { return x.id === S.open; });
  if (!arr.length) { lay.innerHTML = ""; return; }
  var r = arr[0], a = S.archById[S.arch], cf = conflictOf(r), fit = fitOf(r);
  var mk = r.maker ? S.makerById[r.maker] : null, src = S.srcById[r.source];
  var sl = r.slot ? S.slotById[r.slot] : null;

  var peers = S.rows.filter(function (x) { return x.dir === "offer" && x.slot === r.slot && x.priceRub; });
  var sp = peers.map(function (x) { return x.priceRub; }).sort(function (x, y) { return x - y; });
  var pct = sp.length ? Math.round(sp.filter(function (p) { return p < r.priceRub; }).length / sp.length * 100) : null;
  var med = sp.length ? sp[Math.floor(sp.length / 2)] : null;
  var body = "";

  if (r.dir !== "service") {
    body += '<div class="dsec"><span class="eyebrow">фото · ' + (r.photos || 0) + "</span>" +
      (r.photos
        ? '<div class="photos">' + Array.apply(null, { length: Math.min(r.photos, 8) }).map(function (_, i) {
            return '<div class="photo">' + (i + 1) + "</div>"; }).join("") + "</div>"
        : '<div class="notice">Фото нет. Для б/у это ключевой пробел: состояние стали без фотографии ' +
          "не проверяется, а пост удалят через час после сделки — парсер обязан качать вложения " +
          "при первом же обходе (docs/DATA_SOURCES.md §1).</div>") + "</div>";

    var lo = Math.min(a.yearFrom, r.yearFrom) - 40, hi = Math.max(a.yearTo, r.yearTo) + 40, span = hi - lo;
    body += '<div class="dsec"><span class="eyebrow">период против архетипа</span>' +
      '<div class="tl"><div class="track"></div>' +
      '<div class="arch" style="left:' + ((a.yearFrom - lo) / span * 100) + "%;width:" +
        ((a.yearTo - a.yearFrom) / span * 100) + '%"></div>' +
      '<div class="lot ' + (cf ? "bad" : "") + '" style="left:' + ((r.yearFrom - lo) / span * 100) +
        "%;width:" + Math.max(1.5, (r.yearTo - r.yearFrom) / span * 100) + '%"></div>' +
      '<div class="lbl" style="left:0">' + lo + '</div><div class="lbl" style="right:0">' + hi + "</div></div>" +
      '<div style="font-size:12px;margin-top:6px;color:' + (cf ? "var(--rust)" : "var(--patina)") + '">' +
      (cf ? "Конфликт: " + (cf.kind === "early" ? "раньше" : "позже") + " окна архетипа на ~" + cf.years +
            " лет. Комиссия по аутентичности такой предмет не пропустит."
          : "Попадает в окно архетипа «" + esc(a.title) + "», " + a.yearFrom + "–" + a.yearTo + ".") +
      "</div></div>";
  }

  if (r.dir === "offer") {
    var ms = Object.keys(r.measures || {});
    body += '<div class="dsec"><span class="eyebrow">обмеры и посадка</span>' +
      (ms.length
        ? '<table class="det">' + ms.map(function (k) {
            var lo2 = r.measures[k][0], hi2 = r.measures[k][1], me = S.body[k];
            var ok = me != null && me >= lo2 && me <= hi2;
            var off = me == null ? null : (me < lo2 ? lo2 - me : me > hi2 ? me - hi2 : 0);
            return "<tr><td>" + esc(MEASURE_RU[k] || k) + "</td><td>" + lo2 + "–" + hi2 + " см " +
              (me == null ? "" : ok ? '<span class="tag patina">вы ' + me + "</span>"
                : off <= 4 ? '<span class="tag brass">вы ' + me + ", Δ" + off + "</span>"
                           : '<span class="tag rust">вы ' + me + ", Δ" + off + "</span>") + "</td></tr>";
          }).join("") + "</table>"
        : '<div class="notice">Обмеров нет — лот не участвует в размерном матче. ' +
          "Правило проекта: «лот без обмеров для матчера не существует».</div>") +
      (r.steelMm
        ? '<table class="det"><tr><td>толщина стали</td><td>' + r.steelMm + " мм</td></tr>" +
          (r.weightG ? "<tr><td>масса</td><td>" + (r.weightG / 1000).toFixed(1) + " кг</td></tr>" : "") + "</table>"
        : "") + "</div>";
  }

  if (r.dir === "want" && Object.keys(r.need || {}).length) {
    body += '<div class="dsec"><span class="eyebrow">что нужно по обмерам</span><table class="det">' +
      Object.keys(r.need).map(function (k) {
        return "<tr><td>" + esc(MEASURE_RU[k] || k) + "</td><td>" + r.need[k] + " см</td></tr>";
      }).join("") + "</table></div>";
  }

  if (r.dir !== "want") {
    body += '<div class="dsec"><span class="eyebrow">цена на фоне слота</span><table class="det">' +
      "<tr><td>эта позиция</td><td>" + fmtCur(r.priceRub) + "</td></tr>" +
      (med ? "<tr><td>медиана по слоту (" + sp.length + " лот.)</td><td>" + fmtCur(med) + "</td></tr>" : "") +
      (pct != null ? "<tr><td>перцентиль</td><td>" + pct + "%</td></tr>" : "") +
      "<tr><td>в валюте лота</td><td>" + fmtCur(r.priceRub, r.currency) + "</td></tr></table></div>";
  }

  if (mk) {
    body += '<div class="dsec"><span class="eyebrow">мастер</span><div class="card">' +
      '<div class="row-between"><div style="color:var(--fg-1)">' + esc(mk.title) +
      (mk.verified ? ' <span class="tag patina">проверен</span>' : "") + "</div>" +
      '<div class="num">' + mk.rating + "</div></div>" +
      '<div class="mono dim" style="font-size:10.5px;margin-top:4px">' + esc(mk.city) + " · " + esc(mk.country) +
      " · срок " + mk.leadDays + " дн. · очередь " + (mk.queueOpen ? "открыта" : "закрыта") + "</div></div></div>";
  }

  if (r.dir !== "service") {
    /* Порядок ранжирования: подгонка вперёд, если лот «почти подходит»;
       затем услуги именно под этот слот, и только потом «на всё» (scope *) —
       иначе точная услуга тонет под универсальными расходниками. */
    var svcAll = S.rows.filter(function (x) {
      return x.dir === "service" && (x.scope.indexOf("*") >= 0 || (r.slot && x.scope.indexOf(r.slot) >= 0));
    });
    var rank = function (x) {
      var exact = r.slot && x.scope.indexOf(r.slot) >= 0 ? 0 : 1;
      var refitFirst = (fit === "refit" && x.kind === "refit") ? -1 : 0;
      return refitFirst * 2 + exact;
    };
    var svc = svcAll.slice().sort(function (x, y) { return rank(x) - rank(y); }).slice(0, 4);
    if (svc.length) {
      body += '<div class="dsec"><span class="eyebrow">' +
        (fit === "refit" ? "не подходит на пару сантиметров — вот кто подгонит" : "услуги под этот слот") + "</span>" +
        svc.map(function (x) {
          var xm = S.makerById[x.maker];
          return '<div class="card" data-goto="' + x.id + '"><div class="row-between"><div>' + esc(x.title) +
            '</div><div class="num t-nowrap">' + fmtCur(x.priceRub) + "</div></div>" +
            '<div class="mono dim" style="font-size:10.5px;margin-top:3px">' + esc(SVC_RU[x.kind]) + " · " +
            esc(xm ? xm.title : "") + " · " + x.days + " дн. · " + (x.remote ? "по почте" : "очно") + "</div></div>";
        }).join("") + "</div>";
    }
  }

  var sim = S.rows.filter(function (x) {
    return x.id !== r.id && x.dir === r.dir && x.slot === r.slot && x.status === "active";
  }).slice(0, 5);
  if (sim.length) {
    body += '<div class="dsec"><span class="eyebrow">похожие</span>' + sim.map(function (x) {
      return '<div class="card" data-goto="' + x.id + '"><div class="row-between"><div>' + esc(x.title) +
        '</div><div class="num t-nowrap">' + fmtCur(x.priceRub) + "</div></div>" +
        '<div class="mono dim" style="font-size:10.5px;margin-top:3px">' + esc(x.period || "") +
        " · " + esc(x.city) + " · " + x.age + "д</div></div>";
    }).join("") + "</div>";
  }

  body += '<div class="dsec"><span class="eyebrow">источник</span><table class="det">' +
    "<tr><td>откуда</td><td>" + esc(src ? src.ref : "—") + "</td></tr>" +
    "<tr><td>опубликовано</td><td>" + esc(r.postedAt) + " · " + r.age + " дн. назад</td></tr>" +
    "<tr><td>статус</td><td>" + (r.status === "active" ? "активно" : "протухло") + "</td></tr></table>" +
    '<div class="notice" style="margin-top:8px">Агрегатор не перепечатывает объявление целиком: карточка — ' +
    "это нормализованные поля плюс ссылка на оригинал (docs/DATA_SOURCES.md §5).</div></div>";

  lay.innerHTML = '<div class="scrim" data-act="close"></div><div class="drawer">' +
    '<header><div style="flex:1;min-width:0">' +
      '<div class="eyebrow">' + (r.dir === "offer" ? "предложение" : r.dir === "want" ? "запрос" : "услуга") +
      " · " + esc(sl ? sl.label : (r.kind ? SVC_RU[r.kind] : "—")) + "</div>" +
      '<div class="serif" style="font-size:19px;color:var(--fg-1);margin-top:3px">' + esc(r.title) + "</div>" +
      '<div class="mono dim" style="font-size:10.5px;margin-top:4px">' + esc(r.id) + " · " +
        esc(r.city) + " · " + esc(r.country) + "</div></div>" +
    '<div style="text-align:right"><div class="num" style="font-size:18px;color:var(--fg-1)">' +
      fmtCur(r.priceRub) + "</div>" +
    '<button class="btn sm ghost" data-act="close" style="margin-top:6px">esc ✕</button></div></header>' +
    '<div class="body">' + body + "</div>" +
    '<footer><button class="btn primary" data-act="orig">открыть оригинал</button>' +
    '<button class="btn" data-act="fav">' + (S.fav[r.id] ? "★ в избранном" : "☆ в избранное") + "</button>" +
    '<div style="flex:1"></div><button class="btn ghost" data-act="close">закрыть</button></footer></div>';
}

/* ── модалки ── */
function renderModal() {
  var lay = document.getElementById("layer");
  if (S.modal === "profile") {
    lay.innerHTML = '<div class="scrim" data-act="close"></div><div class="modal">' +
      '<div class="eyebrow">профиль</div>' +
      '<div class="serif" style="font-size:20px;color:var(--fg-1);margin:4px 0 12px">Обмеры и валюта</div>' +
      '<div class="notice" style="margin-bottom:14px">Обмеры вводятся один раз — дальше весь реестр помечен ' +
        "«подойдёт / после подгонки / не тот». Допуск подгонки — 4 см.</div>" +
      Object.keys(S.body).map(function (k) {
        return '<div class="field"><label>' + esc(MEASURE_RU[k] || k) +
          '</label><input type="number" data-body="' + k + '" value="' + S.body[k] + '"></div>';
      }).join("") +
      '<div class="field"><label>валюта отображения</label><select data-set="cur">' +
        Object.keys(S.feed.currencies).map(function (c) {
          return '<option value="' + c + '"' + (c === S.cur ? " selected" : "") + ">" + c + " " +
            S.feed.currencies[c] + "</option>";
        }).join("") + "</select></div>" +
      '<div class="notice" style="margin-top:12px;color:var(--rust)">Курсы валют — заглушка из фида. ' +
        "Фид курсов не подключён, для расчётов не использовать.</div>" +
      '<div style="display:flex;gap:8px;margin-top:16px">' +
      '<button class="btn primary" data-act="close">готово</button></div></div>';
  } else if (S.modal === "sub") {
    lay.innerHTML = '<div class="scrim" data-act="close"></div><div class="modal">' +
      '<div class="eyebrow">новая подписка</div>' +
      '<div class="serif" style="font-size:20px;color:var(--fg-1);margin:4px 0 12px">Следить за этим фильтром</div>' +
      '<div class="field wide"><input id="subname" value="' + esc(describeFilter()) + '"></div>' +
      '<div class="notice" style="margin-top:10px">На тонком рынке лот живёт часами. Подписка — то, ради чего ' +
        "сюда возвращаются: реестр считает совпадения и подсвечивает новые с момента её создания.</div>" +
      '<div style="display:flex;gap:8px;margin-top:16px"><button class="btn primary" data-act="subok">сохранить</button>' +
      '<button class="btn ghost" data-act="close">отмена</button></div></div>';
  } else lay.innerHTML = "";
}

function describeFilter() {
  var p = [];
  if (S.view !== "all") p.push({ offer: "предложение", want: "спрос", service: "услуги" }[S.view]);
  if (S.f.slot) p.push(S.slotById[S.f.slot].label.toLowerCase());
  if (S.f.cent) p.push(S.f.cent + " век");
  if (S.f.region) p.push(S.f.region);
  if (S.f.country) p.push(S.f.country);
  if (S.f.cond) p.push(COND_RU[S.f.cond]);
  if (S.fitOnly) p.push("по моим обмерам");
  if (S.noConflict) p.push("без конфликта эпохи");
  if (S.priceMax != null) p.push("до " + fmtCur(S.priceMax));
  if (S.q) p.push("«" + S.q + "»");
  return p.length ? p.join(", ") : "весь реестр";
}

function snapshot() {
  return { view: S.view, q: S.q, f: JSON.parse(JSON.stringify(S.f)), priceMax: S.priceMax,
           fitOnly: S.fitOnly, noConflict: S.noConflict, arch: S.arch };
}
function applySnapshot(st) {
  S.view = st.view; S.q = st.q; S.f = JSON.parse(JSON.stringify(st.f));
  S.priceMax = st.priceMax; S.fitOnly = st.fitOnly; S.noConflict = st.noConflict;
}
function matchSub(sub) {
  var save = snapshot();
  applySnapshot(sub.st);
  var rows = visible();
  applySnapshot(save);
  var fresh = rows.filter(function (r) { return r.postedAt > sub.created && !S.seen[r.id]; }).length;
  return { total: rows.length, fresh: fresh };
}

/* ═══ 7. События ═══ */
function closeLayer() {
  S.open = null; S.modal = null;
  document.getElementById("layer").innerHTML = "";
  renderTable(); renderLeft();
}

document.addEventListener("click", function (e) {
  var t = e.target, el;
  if (!t.closest) return;
  if ((el = t.closest("[data-delsub]"))) {
    e.stopPropagation();
    S.subs.splice(+el.dataset.delsub, 1); store.set("subs", S.subs); renderLeft(); return;
  }
  if ((el = t.closest("[data-view]"))) { S.view = el.dataset.view; S.open = null; renderAll(); renderDrawer(); return; }
  if ((el = t.closest("[data-sort]"))) {
    var k = el.dataset.sort;
    S.sort = { key: k, asc: S.sort.key === k ? !S.sort.asc : true };
    renderTable(); writeHash(); return;
  }
  if ((el = t.closest("[data-sub]"))) {
    var s = S.subs[+el.dataset.sub];
    applySnapshot(s.st); S.arch = s.st.arch;
    visible().forEach(function (r) { S.seen[r.id] = 1; });
    store.set("seen", S.seen);
    renderAll(); return;
  }
  if ((el = t.closest("[data-f]"))) {
    var f = el.dataset.f, v = el.dataset.v;
    S.f[f] = S.f[f] === v ? "" : v;
    renderAll(); return;
  }
  if ((el = t.closest("[data-tgl]"))) { S[el.dataset.tgl] = !S[el.dataset.tgl]; renderAll(); return; }
  if ((el = t.closest("[data-goto]"))) { S.open = el.dataset.goto; renderTable(); renderDrawer(); return; }
  if ((el = t.closest("[data-act]"))) {
    var a = el.dataset.act;
    if (a === "close") closeLayer();
    else if (a === "reset") {
      S.q = ""; S.f = { slot: "", cent: "", region: "", cond: "", src: "", country: "", maker: "" };
      S.priceMax = null; S.fitOnly = false; S.noConflict = false; renderAll();
    } else if (a === "profile") { S.modal = "profile"; renderModal(); }
    else if (a === "savesub") { S.modal = "sub"; renderModal(); }
    else if (a === "subok") {
      var inp = document.getElementById("subname");
      S.subs.unshift({ name: (inp && inp.value) || describeFilter(), st: snapshot(),
                       created: new Date().toISOString().slice(0, 10) });
      store.set("subs", S.subs);
      S.modal = null; document.getElementById("layer").innerHTML = ""; renderLeft();
    } else if (a === "cur") {
      var ks = Object.keys(S.feed.currencies);
      S.cur = ks[(ks.indexOf(S.cur) + 1) % ks.length];
      store.set("cur", S.cur); renderAll(); renderDrawer();
    } else if (a === "fav") {
      S.fav[S.open] = !S.fav[S.open]; store.set("fav", S.fav); renderDrawer();
    } else if (a === "orig") {
      var r = S.rows.filter(function (x) { return x.id === S.open; })[0];
      toast("Оригинал: " + (r && r.sourceRef ? r.sourceRef : "источник не указан") +
            " — в рабочей версии здесь прямая ссылка на пост.");
    }
    return;
  }
  if ((el = t.closest("tbody tr[data-id]"))) {
    S.open = el.dataset.id; S.seen[S.open] = 1; store.set("seen", S.seen);
    renderTable(); renderDrawer(); return;
  }
});

function toast(msg) {
  var b = document.createElement("div");
  b.style.cssText = "position:fixed;left:50%;bottom:24px;transform:translateX(-50%);z-index:80;" +
    "background:oklch(0.24 0.013 100);border:1px solid var(--line-2);border-radius:4px;padding:9px 14px;" +
    "font-size:12.5px;color:var(--fg-1);box-shadow:0 10px 30px oklch(0.08 0.01 100/.5)";
  b.textContent = msg;
  document.body.appendChild(b);
  setTimeout(function () { if (b.parentNode) b.parentNode.removeChild(b); }, 3400);
}

document.addEventListener("input", function (e) {
  var t = e.target;
  if (t.id === "q") { S.q = t.value; renderTable(); renderStatus(); writeHash(); }
  else if (t.id === "price") {
    S.priceMax = +t.value;
    renderTable(); renderStatus(); renderLeft();
    var el = document.getElementById("price"); if (el) el.focus();
  } else if (t.dataset && t.dataset.body) {
    S.body[t.dataset.body] = +t.value || 0; store.set("body", S.body);
    renderTable(); renderRight(); renderStatus();
  }
});

document.addEventListener("change", function (e) {
  var t = e.target;
  if (t.id === "archsel") { S.arch = t.value; store.set("arch", S.arch); renderAll(); renderDrawer(); }
  else if (t.dataset && t.dataset.set === "cur") { S.cur = t.value; store.set("cur", S.cur); renderAll(); renderModal(); }
});

/* ═══ 8. URL-состояние: отфильтрованный вид можно дать ссылкой ═══ */
function writeHash() {
  var p = [];
  if (S.view !== "all") p.push("v=" + S.view);
  if (S.q) p.push("q=" + encodeURIComponent(S.q));
  Object.keys(S.f).forEach(function (k) { if (S.f[k]) p.push(k + "=" + encodeURIComponent(S.f[k])); });
  if (S.fitOnly) p.push("fit=1");
  if (S.noConflict) p.push("nc=1");
  p.push("a=" + S.arch);
  if (S.sort.key !== "age" || !S.sort.asc) p.push("s=" + S.sort.key + (S.sort.asc ? "" : "-"));
  try { history.replaceState(null, "", "#" + p.join("&")); } catch (e) {}
}
function readHash() {
  var h = (location.hash || "").replace(/^#/, "");
  if (!h) return;
  h.split("&").forEach(function (kv) {
    var i = kv.indexOf("="); if (i < 0) return;
    var k = kv.slice(0, i), v = decodeURIComponent(kv.slice(i + 1));
    if (k === "v") S.view = v;
    else if (k === "q") S.q = v;
    else if (k === "fit") S.fitOnly = true;
    else if (k === "nc") S.noConflict = true;
    else if (k === "a") S.arch = v;
    else if (k === "s") S.sort = { key: v.replace(/-$/, ""), asc: v.slice(-1) !== "-" };
    else if (k in S.f) S.f[k] = v;
  });
}

/* ═══ 9. Клавиатура ═══ */
document.addEventListener("keydown", function (e) {
  var ae = document.activeElement || {};
  if (e.key === "/" && ae.id !== "q") {
    e.preventDefault();
    var q = document.getElementById("q"); if (q) q.focus();
    return;
  }
  if (e.key === "Escape") { closeLayer(); return; }
  if (ae.tagName === "INPUT" || ae.tagName === "SELECT" || ae.tagName === "TEXTAREA") return;
  if (e.key === "j" || e.key === "k") {
    var rows = sortRows(visible());
    if (!rows.length) return;
    var i = -1;
    rows.forEach(function (r, n) { if (r.id === S.open) i = n; });
    i = e.key === "j" ? Math.min(rows.length - 1, i + 1) : Math.max(0, i <= 0 ? 0 : i - 1);
    S.open = rows[i].id; S.seen[S.open] = 1;
    renderTable(); renderDrawer();
    var el = document.querySelector('tr[data-id="' + S.open + '"]');
    if (el && el.scrollIntoView) el.scrollIntoView({ block: "nearest" });
  }
});

boot();
})();
