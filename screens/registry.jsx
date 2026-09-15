/* Реестр — двунаправленная главная: предложение · спрос · услуги
   Одна таблица, фильтруемые поля в шапке, важное — в один экран.
   Добавлено 05.09.2026. */

const Registry = ({ archetype, onOpenItem, onGoPaperdoll }) => {
  const [dir, setDir]         = React.useState("all");   // all | offer | want | service
  const [q, setQ]             = React.useState("");
  const [fSlot, setFSlot]     = React.useState("");
  const [fCent, setFCent]     = React.useState("");
  const [fRegion, setFRegion] = React.useState("");
  const [fCond, setFCond]     = React.useState("");
  const [fSrc, setFSrc]       = React.useState("");
  const [fCity, setFCity]     = React.useState("");
  const [fitOnly, setFitOnly] = React.useState(false);
  const [sort, setSort]       = React.useState({ key: "age", asc: true });
  const [hover, setHover]     = React.useState(null);

  const body = window.MY_BODY;
  const aFrom = archetype.yearFrom, aTo = archetype.yearTo;

  const slotLabel = (id) => {
    const s = archetype.slots.find(x => x.id === id);
    if (s) return { label: s.label, short: s.short };
    if (id === "weapon") return { label: "Оружие", short: "ОРУЖ." };
    return { label: id, short: id.slice(0, 6).toUpperCase() };
  };

  /* ─────────── сборка единых строк реестра ─────────── */
  const rows = React.useMemo(() => {
    const out = [];

    window.ITEMS.forEach(it => {
      const meta = window.ITEM_META[it.id] || { src: "manual", age: 30 };
      const m = window.ITEM_MEASURES[it.id];
      out.push({
        kind: "offer", id: it.id, slot: it.slot, title: it.title, sub: it.subtype,
        period: it.period, region: it.region, condition: it.condition,
        price: it.price, currency: it.currency || "₽", city: it.city,
        src: meta.src, age: meta.age, image: it.image, master: it.master,
        measures: m, fit: window.fitVerdict(m, body),
        conflict: window.periodConflict(it.period, aFrom, aTo),
        note: it.conflictNote,
      });
    });

    window.WANTS.forEach(w => {
      const need = Object.keys(w.need || {}).map(k => `${k} ${w.need[k]}`).join(" · ");
      out.push({
        kind: "want", id: w.id, slot: w.slot, title: w.title, sub: need || "без обмеров",
        period: w.period, region: w.region, condition: w.condition,
        price: w.budget, currency: w.currency, city: w.city,
        src: w.src, age: w.age, urgency: w.urgency, image: null, master: null,
        measures: null, fit: null,
        conflict: window.periodConflict(w.period, aFrom, aTo),
      });
    });

    window.SERVICES.forEach(s => {
      const mk = window.MAKERS.find(m => m.id === s.maker);
      out.push({
        kind: "service", id: s.id, slot: s.scope[0] === "*" ? "" : s.scope[0],
        scope: s.scope, title: s.title, sub: mk ? mk.title : "—",
        serviceKind: s.kind, days: s.days, remote: s.remote,
        period: null, region: mk ? mk.country : "", condition: null,
        price: s.price, currency: s.currency, city: s.city,
        src: s.src, age: s.age, measures: null, fit: null, conflict: null,
      });
    });

    return out;
  }, [aFrom, aTo]);

  /* ─────────── справочники для фильтров ─────────── */
  const slots   = [...new Set(rows.map(r => r.slot).filter(Boolean))];
  const regions = [...new Set(rows.map(r => r.region).filter(Boolean))];
  const cities  = [...new Set(rows.map(r => r.city).filter(Boolean))];

  /* ─────────── фильтрация ─────────── */
  const filtered = React.useMemo(() => {
    const needle = q.trim().toLowerCase();
    return rows.filter(r => {
      if (dir !== "all" && r.kind !== dir) return false;
      if (needle && !(`${r.title} ${r.sub} ${r.city}`.toLowerCase().includes(needle))) return false;
      if (fSlot && r.slot !== fSlot) return false;
      if (fRegion && r.region !== fRegion) return false;
      if (fCity && r.city !== fCity) return false;
      if (fCond && r.condition !== fCond) return false;
      if (fSrc && r.src !== fSrc) return false;
      if (fitOnly && !(r.fit === "fits" || r.fit === "refit")) return false;
      if (fCent) {
        const w = window.parsePeriod(r.period);
        if (!w) return false;
        const c1 = (Number(fCent) - 1) * 100, c2 = Number(fCent) * 100;
        if (w.to <= c1 || w.from >= c2) return false;
      }
      return true;
    });
  }, [rows, dir, q, fSlot, fCent, fRegion, fCond, fSrc, fCity, fitOnly]);

  const sorted = React.useMemo(() => {
    const s = [...filtered];
    const k = sort.key, sign = sort.asc ? 1 : -1;
    s.sort((a, b) => {
      let av, bv;
      if (k === "period") {
        av = (window.parsePeriod(a.period) || { from: 9999 }).from;
        bv = (window.parsePeriod(b.period) || { from: 9999 }).from;
      } else if (k === "slot") { av = a.slot || "яя"; bv = b.slot || "яя"; }
      else { av = a[k] ?? 0; bv = b[k] ?? 0; }
      if (av < bv) return -1 * sign;
      if (av > bv) return 1 * sign;
      return 0;
    });
    return s;
  }, [filtered, sort]);

  /* ─────────── дефицит: спрос без предложения ─────────── */
  const deficit = React.useMemo(() => {
    const map = {};
    rows.forEach(r => {
      if (!r.slot || r.kind === "service") return;
      map[r.slot] = map[r.slot] || { offer: 0, want: 0 };
      map[r.slot][r.kind] += 1;
    });
    return Object.entries(map)
      .map(([slot, v]) => ({ slot, ...v, gap: v.want - v.offer }))
      .sort((a, b) => b.gap - a.gap)
      .slice(0, 6);
  }, [rows]);

  const counts = {
    all:     rows.length,
    offer:   rows.filter(r => r.kind === "offer").length,
    want:    rows.filter(r => r.kind === "want").length,
    service: rows.filter(r => r.kind === "service").length,
  };

  const isSvc = dir === "service";

  const th = (key, label, align) => (
    <th onClick={() => setSort(s => ({ key, asc: s.key === key ? !s.asc : true }))}
        style={{ textAlign: align || "left", cursor: "pointer", whiteSpace: "nowrap" }}
        title="сортировать">
      {label}{sort.key === key ? <span style={{ color: "var(--accent)" }}>{sort.asc ? " ↑" : " ↓"}</span> : ""}
    </th>
  );

  const sel = (value, onChange, options, placeholder) => (
    <select value={value} onChange={e => onChange(e.target.value)} className="reg-filter">
      <option value="">{placeholder}</option>
      {options.map(o => <option key={o.v ?? o} value={o.v ?? o}>{o.l ?? o}</option>)}
    </select>
  );

  return (
    <div className="fade-in" style={{ display: "grid", gridTemplateColumns: "1fr 268px", minHeight: "calc(100vh - 56px)" }}>

      {/* ══════════ ЛЕВО: реестр ══════════ */}
      <main style={{ padding: "18px 22px 20px", minWidth: 0 }}>

        {/* строка управления */}
        <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", marginBottom: 12 }}>
          <div style={{ display: "flex", padding: 3, background: "oklch(0.20 0.013 100)", border: "1px solid var(--line-1)", borderRadius: 3 }}>
            {[["all","Всё"],["offer","▲ Предложение"],["want","▼ Спрос"],["service","◆ Услуги"]].map(([k,l]) => (
              <button key={k} onClick={() => setDir(k)} style={{
                padding: "6px 12px", fontSize: 12.5, borderRadius: 2, whiteSpace: "nowrap",
                color: dir === k ? "var(--fg-1)" : "var(--fg-4)",
                background: dir === k ? "oklch(0.30 0.013 100)" : "transparent",
                boxShadow: dir === k ? "inset 0 0 0 1px var(--line-3)" : "none",
              }}>{l}<span className="mono" style={{ marginLeft: 6, fontSize: 10, color: "var(--fg-5)" }}>{counts[k]}</span></button>
            ))}
          </div>

          <input className="reg-search" value={q} onChange={e => setQ(e.target.value)}
                 placeholder="поиск по названию, обмерам, городу…" />

          <label style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12, color: fitOnly ? "var(--fg-1)" : "var(--fg-4)", cursor: "pointer", whiteSpace: "nowrap" }}>
            <span style={{ width: 11, height: 11, border: `1px solid ${fitOnly ? "var(--accent)" : "var(--line-3)"}`, background: fitOnly ? "var(--accent)" : "transparent", borderRadius: 1 }}/>
            <input type="checkbox" checked={fitOnly} onChange={e => setFitOnly(e.target.checked)} style={{ display: "none" }}/>
            подойдёт мне по размеру
          </label>

          <div style={{ marginLeft: "auto" }} className="mono">
            <span style={{ color: "var(--fg-1)" }}>{sorted.length}</span>
            <span style={{ color: "var(--fg-4)", fontSize: 11 }}> из {rows.length}</span>
          </div>
        </div>

        {/* таблица */}
        <div className="reg-wrap">
          <table className="reg-table">
            <thead>
              <tr className="reg-head">
                <th style={{ width: 26 }}></th>
                {th("slot", "СЛОТ")}
                <th style={{ minWidth: 260 }}>НАИМЕНОВАНИЕ</th>
                {isSvc ? th("days", "СРОК", "right") : th("period", "ПЕРИОД")}
                <th>{isSvc ? "СТРАНА" : "РЕГИОН"}</th>
                {!isSvc && <th>РАЗМЕР</th>}
                {!isSvc && <th style={{ width: 46 }}>СОСТ</th>}
                {th("price", isSvc ? "ОТ" : "ЦЕНА / БЮДЖЕТ", "right")}
                <th>ГОРОД</th>
                <th style={{ width: 34 }}>ИСТ</th>
                {th("age", "ВОЗР", "right")}
              </tr>
              <tr className="reg-filters">
                <td></td>
                <td>{sel(fSlot, setFSlot, slots.map(s => ({ v: s, l: slotLabel(s).short })), "все")}</td>
                <td></td>
                <td>{!isSvc && sel(fCent, setFCent, [{v:"9",l:"IX"},{v:"10",l:"X"},{v:"11",l:"XI"},{v:"12",l:"XII"},{v:"13",l:"XIII"},{v:"14",l:"XIV"},{v:"15",l:"XV"}], "век")}</td>
                <td>{sel(fRegion, setFRegion, regions, "все")}</td>
                {!isSvc && <td></td>}
                {!isSvc && <td>{sel(fCond, setFCond, [{v:"new",l:"new"},{v:"used",l:"used"},{v:"any",l:"any"}], "—")}</td>}
                <td></td>
                <td>{sel(fCity, setFCity, cities, "все")}</td>
                <td>{sel(fSrc, setFSrc, Object.keys(window.SOURCES).map(k => ({ v: k, l: window.SOURCES[k].glyph })), "—")}</td>
                <td></td>
              </tr>
            </thead>
            <tbody>
              {sorted.map(r => {
                const sl = slotLabel(r.slot);
                const src = window.SOURCES[r.src] || window.SOURCES.manual;
                const isOffer = r.kind === "offer";
                return (
                  <tr key={r.id}
                      onMouseEnter={() => setHover(r)}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => isOffer && onOpenItem(r.id)}
                      className={`reg-row ${isOffer ? "clickable" : ""} ${hover && hover.id === r.id ? "on" : ""}`}>
                    <td style={{ textAlign: "center", color: r.kind === "offer" ? "var(--patina)" : r.kind === "want" ? "var(--brass)" : "var(--steel)" }}>
                      {r.kind === "offer" ? "▲" : r.kind === "want" ? "▼" : "◆"}
                    </td>
                    <td className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", color: "var(--fg-4)", whiteSpace: "nowrap" }}>
                      {r.kind === "service"
                        ? <span style={{ color: "var(--steel)" }}>{window.SERVICE_KINDS[r.serviceKind].glyph}</span>
                        : sl.short}
                    </td>
                    <td>
                      <div style={{ color: "var(--fg-1)", fontSize: 12.5, lineHeight: 1.25 }}>{r.title}</div>
                      <div className="mono" style={{ fontSize: 10, color: "var(--fg-5)", marginTop: 2 }}>
                        {r.sub}
                        {r.urgency && <span style={{ color: "var(--rust)", marginLeft: 8 }}>⚑ {r.urgency}</span>}
                      </div>
                    </td>
                    <td className="mono" style={{ fontSize: 11, whiteSpace: "nowrap", color: r.conflict ? "var(--rust)" : "var(--fg-3)" }}>
                      {r.kind === "service" ? `${r.days} дн.` : r.period}
                      {r.conflict && <span title={`период ${r.conflict.kind === "early" ? "раньше" : "позже"} архетипа на ~${r.conflict.years} лет`}> ⚠</span>}
                    </td>
                    <td style={{ fontSize: 11.5, color: "var(--fg-3)", whiteSpace: "nowrap" }}>{r.region}</td>
                    {!isSvc && (
                      <td>
                        {r.fit === "fits"    && <span className="tag patina">подойдёт</span>}
                        {r.fit === "refit"   && <span className="tag brass">подгонка</span>}
                        {r.fit === "no"      && <span className="tag rust">не тот</span>}
                        {r.fit === "unknown" && <span className="tag" title="в объявлении нет обмеров">нет обмеров</span>}
                        {r.fit === null && r.kind === "want" && <span className="mono" style={{ fontSize: 10, color: "var(--fg-5)" }}>запрос</span>}
                        {r.fit === null && r.kind === "service" && <span className="mono" style={{ fontSize: 10, color: "var(--fg-5)" }}>{r.remote ? "по почте" : "очно"}</span>}
                      </td>
                    )}
                    {!isSvc && (
                      <td style={{ textAlign: "center" }}>
                        {r.condition
                          ? <span title={r.condition} style={{
                              display: "inline-block", width: 7, height: 7, borderRadius: 4,
                              background: r.condition === "new" ? "var(--patina)" : r.condition === "used" ? "var(--steel-dim)" : "var(--line-3)",
                            }}/>
                          : <span className="mono" style={{ fontSize: 10, color: "var(--fg-5)" }}>—</span>}
                      </td>
                    )}
                    <td className="num" style={{ textAlign: "right", whiteSpace: "nowrap", color: "var(--fg-1)", fontSize: 12.5 }}>
                      {r.kind === "want" && <span style={{ color: "var(--fg-5)", fontSize: 10 }}>до </span>}
                      {window.fmt(r.price, r.currency)}
                    </td>
                    <td style={{ fontSize: 11.5, color: "var(--fg-3)", whiteSpace: "nowrap" }}>{r.city}</td>
                    <td className="mono" style={{ fontSize: 9.5, textAlign: "center", color: "var(--fg-4)" }} title={src.label}>{src.glyph}</td>
                    <td className="mono" style={{ textAlign: "right", fontSize: 10.5, whiteSpace: "nowrap",
                        color: r.age > 30 ? "var(--fg-5)" : r.age > 14 ? "var(--fg-4)" : "var(--fg-2)" }}
                        title={r.age > 30 ? "объявление устарело — вероятно, продано" : ""}>
                      {r.age}д
                    </td>
                  </tr>
                );
              })}
              {sorted.length === 0 && (
                <tr><td colSpan={11} style={{ padding: "40px 0", textAlign: "center", color: "var(--fg-4)" }}>
                  <div className="mono" style={{ fontSize: 11, letterSpacing: "0.14em", textTransform: "uppercase" }}>ничего не найдено</div>
                  <button className="btn" style={{ marginTop: 14 }} onClick={() => { setFSlot(""); setFCent(""); setFRegion(""); setFCond(""); setFSrc(""); setFCity(""); setQ(""); setFitOnly(false); }}>
                    сбросить фильтры
                  </button>
                </td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="mono" style={{ marginTop: 10, fontSize: 10.5, color: "var(--fg-5)", letterSpacing: "0.06em" }}>
          ▲ предложение · ▼ спрос · ◆ услуга &nbsp;|&nbsp; ⚠ конфликт периода с архетипом
          «{archetype.title}, {archetype.period}» &nbsp;|&nbsp; данные синтетические
        </div>
      </main>

      {/* ══════════ ПРАВО: контекст ══════════ */}
      <aside style={{
        borderLeft: "1px solid var(--line-1)", padding: "18px 18px 60px",
        position: "sticky", top: 56, height: "calc(100vh - 56px)", overflowY: "auto",
        background: "oklch(0.165 0.013 105)",
      }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>архетип</div>
        <button onClick={onGoPaperdoll} style={{ textAlign: "left" }}>
          <div className="serif" style={{ fontSize: 17, color: "var(--fg-1)", letterSpacing: "-0.01em" }}>
            {archetype.title}
          </div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--accent)", marginTop: 2 }}>
            {archetype.yearFrom}–{archetype.yearTo} · {archetype.ruleset.toUpperCase()}
          </div>
        </button>

        <div style={{ marginTop: 16 }}>
          <Paperdoll
            size={188}
            archetype={archetype}
            filledMap={Object.fromEntries(archetype.slots.filter(s => s.picked).map(s => [s.id, true]))}
            conflicts={Object.fromEntries(archetype.slots.filter(s => s.conflict).map(s => [s.id, true]))}
            focusSlot={hover ? hover.slot : null}
            showGrid={false}
          />
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12 }}>
          <div><div className="eyebrow">закрыто</div><div className="num" style={{ fontSize: 18, color: "var(--fg-1)" }}>{archetype.filled}/{archetype.required}</div></div>
          <div><div className="eyebrow">конфликтов</div><div className="num" style={{ fontSize: 18, color: "var(--rust)" }}>{archetype.conflicts}</div></div>
        </div>

        <div className="eyebrow" style={{ marginTop: 26, marginBottom: 8 }}>дефицит рынка</div>
        <div style={{ fontSize: 11, color: "var(--fg-4)", marginBottom: 8, lineHeight: 1.4 }}>
          запросов больше, чем предложений — здесь стоит искать мастера, а не лот
        </div>
        <table className="reg-mini">
          <thead><tr><th>слот</th><th>▲</th><th>▼</th><th>Δ</th></tr></thead>
          <tbody>
            {deficit.map(d => (
              <tr key={d.slot} onClick={() => setFSlot(d.slot)} style={{ cursor: "pointer" }}>
                <td style={{ color: "var(--fg-2)" }}>{slotLabel(d.slot).short}</td>
                <td className="num">{d.offer}</td>
                <td className="num">{d.want}</td>
                <td className="num" style={{ color: d.gap > 0 ? "var(--rust)" : "var(--fg-5)" }}>
                  {d.gap > 0 ? `+${d.gap}` : d.gap}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        <div className="eyebrow" style={{ marginTop: 26, marginBottom: 8 }}>мои обмеры</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)", lineHeight: 1.7 }}>
          {Object.entries(window.MY_BODY).map(([k, v]) => (
            <div key={k} style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--fg-5)" }}>{k}</span><span>{v} см</span>
            </div>
          ))}
        </div>

        <button className="btn" style={{ marginTop: 18, width: "100%" }}>+ разместить запрос</button>
      </aside>
    </div>
  );
};

window.Registry = Registry;
