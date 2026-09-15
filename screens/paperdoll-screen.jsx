/* Paperdoll screen — archetype viewer */

const PaperdollScreen = ({ archetype, onOpenItem, onGoMarket }) => {
  const [activeZone, setActiveZone] = React.useState(null);
  const [pinnedZone, setPinnedZone] = React.useState(null);

  const filledMap = {};
  const conflicts = {};
  archetype.slots.forEach(s => {
    if (s.picked) filledMap[s.id] = true;
    if (s.conflict) conflicts[s.id] = true;
  });

  const zoneSlots = (zoneId) =>
    archetype.slots.filter(s => s.zones.includes(zoneId));

  const shownZone = activeZone || pinnedZone;

  // Aggregate stats
  const total = archetype.slots.length;
  const filled = archetype.slots.filter(s => s.picked).length;
  const conflictCount = archetype.slots.filter(s => s.conflict).length;
  const pct = Math.round((filled / total) * 100);

  return (
    <div className="fade-in" style={{ padding: "20px 32px 80px" }}>

      {/* Top: archetype selector + selection header in one strip */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "minmax(360px, auto) 1fr",
        gap: 32,
        alignItems: "end",
        padding: "8px 0 18px",
        borderBottom: "1px solid var(--line-1)",
        marginBottom: 22,
      }}>
        <div>
          <div className="eyebrow" style={{ marginBottom: 6 }}>архетип</div>
          <div className="h-lg" style={{ fontSize: 34, lineHeight: 1.05, whiteSpace: "nowrap" }}>
            {archetype.title}<span style={{ color: "var(--fg-3)" }}>, {archetype.period}</span>
          </div>
        </div>
        <div style={{ minWidth: 0, display: "flex", flexDirection: "column", gap: 12, alignItems: "stretch" }}>
          <ArchetypeBar value={archetype.id} onChange={() => {}} />
          <div style={{ display: "flex", gap: 28, alignItems: "end", justifyContent: "flex-end" }}>
            <StatBlock label="закрыто" value={`${filled}/${total}`} accent="patina" />
            <StatBlock label="конфликты" value={String(conflictCount)} accent={conflictCount ? "rust" : "fg-4"} />
            <StatBlock label="готовность" value={`${pct}%`} accent="brass" />
          </div>
        </div>
      </div>

      <div style={{ fontSize: 13.5, color: "var(--fg-3)", maxWidth: 820, marginBottom: 22 }}>
        {archetype.blurb}
      </div>

      {/* Main 3-column layout */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "300px 1fr 360px",
        gap: 28,
        minHeight: 720,
      }}>

        {/* ============ LEFT — layer index ============ */}
        <aside>
          <div className="eyebrow" style={{ marginBottom: 10 }}>система слоёв</div>
          <div style={{
            border: "1px solid var(--line-1)",
            borderRadius: 3,
            padding: "16px 16px 4px",
            background: "oklch(0.19 0.013 105)",
          }}>
            <LayerKey n="01" name="Подоспех" sub="гамбезон · стёганка · подкольчужник" tone="bone"/>
            <LayerKey n="02" name="Кольчуга" sub="хауберк · хауберджон · мантия" tone="steel"/>
            <LayerKey n="03" name="Латы" sub="кираса · наручи · поножи · шлем" tone="brass"/>
            <LayerKey n="04" name="Налатник" sub="сюрко · табард · ливрея" tone="patina" last/>
          </div>

          {/* Conflict log */}
          <div className="eyebrow" style={{ marginTop: 28, marginBottom: 10 }}>конфликты</div>
          <div style={{
            border: "1px solid var(--rust-dim, oklch(0.42 0.080 35 / 0.7))",
            background: "oklch(0.20 0.030 35 / 0.18)",
            borderRadius: 3, padding: "12px 14px",
            fontSize: 12.5, color: "var(--fg-2)",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
              <span className="mono" style={{ color: "var(--rust)", fontSize: 10.5, letterSpacing: "0.14em", textTransform: "uppercase" }}>⚠ период</span>
            </div>
            <div style={{ color: "var(--fg-1)", lineHeight: 1.4 }}>
              Наколенники со створками
            </div>
            <div style={{ color: "var(--fg-4)", marginTop: 4 }}>
              ок. 1340 — на ~40 лет раньше архетипа
            </div>
            <div style={{ marginTop: 10, display: "flex", gap: 6 }}>
              <button className="btn" style={{ padding: "5px 9px", fontSize: 11 }}>заменить</button>
              <button className="btn ghost" style={{ padding: "5px 9px", fontSize: 11, color: "var(--fg-4)" }}>принять как</button>
            </div>
          </div>

          <div className="eyebrow" style={{ marginTop: 28, marginBottom: 10 }}>исторические ссылки</div>
          <div style={{ fontSize: 12.5, color: "var(--fg-3)", lineHeight: 1.55 }}>
            Основной источник: <span style={{ color: "var(--fg-1)" }}>надгробие Йиндржиха из Липы</span>,
            Збраслав, ок. 1395.{" "}
            <button style={{ color: "var(--accent)", textDecoration: "underline", textUnderlineOffset: 3 }}>см. галерею →</button>
          </div>
        </aside>

        {/* ============ CENTER — silhouette ============ */}
        <div style={{
          position: "relative",
          background: "oklch(0.155 0.013 105)",
          border: "1px solid var(--line-1)",
          borderRadius: 3,
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          paddingTop: 60,
          paddingBottom: 60,
          minHeight: 660,
        }}>
          {/* corners */}
          <Crosshair pos="tl"/><Crosshair pos="tr"/>
          <Crosshair pos="bl"/><Crosshair pos="br"/>

          {/* legend in corner */}
          <div style={{
            position: "absolute", top: 18, left: 22,
            display: "flex", flexDirection: "column", gap: 6,
            fontSize: 11, color: "var(--fg-4)",
            fontFamily: "var(--font-mono)", letterSpacing: "0.06em",
            whiteSpace: "nowrap",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 14, height: 8, background: "oklch(0.55 0.022 235 / 0.7)" }}/>экипировано
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 14, height: 8, background: "oklch(0.55 0.130 35 / 0.7)" }}/>конфликт
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 14, height: 8, background: "oklch(0.30 0.013 100)", border: "1px solid var(--line-3)" }}/>в архетипе
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8, opacity: 0.4 }}>
              <span style={{ width: 14, height: 8, background: "oklch(0.30 0.013 100)", border: "1px solid var(--line-2)" }}/>вне архетипа
            </div>
          </div>

          {/* shotcaller / facing label */}
          <div style={{
            position: "absolute", top: 18, right: 22,
            fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--fg-4)",
            letterSpacing: "0.14em", textTransform: "uppercase",
          }}>
            проекция · фронт · 1:1
          </div>

          {/* footer scale */}
          <div style={{
            position: "absolute", bottom: 18, left: 0, right: 0,
            display: "flex", justifyContent: "center", gap: 28,
            fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--fg-5)",
            letterSpacing: "0.14em",
          }}>
            <span>h ≈ 178 см</span>
            <span>23 зон</span>
            <span>14 слотов</span>
            <span>{filled}/{total} закрыто</span>
          </div>

          <Paperdoll
            size={320}
            archetype={archetype}
            filledMap={filledMap}
            conflicts={conflicts}
            activeZone={shownZone}
            onZoneHover={setActiveZone}
            onZoneLeave={() => setActiveZone(null)}
            onZoneClick={(z) => setPinnedZone(pz => pz === z ? null : z)}
          />

          {/* Layer popover */}
          {shownZone && (
            <ZoneLayerPopover
              zone={shownZone}
              slots={zoneSlots(shownZone)}
              onPick={onOpenItem}
              onClose={() => { setPinnedZone(null); setActiveZone(null); }}
              onFind={onGoMarket}
            />
          )}
        </div>

        {/* ============ RIGHT — required positions ============ */}
        <aside>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 12 }}>
            <div className="eyebrow">требуемые позиции</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--fg-3)" }}>
              <span style={{ color: "var(--fg-1)" }}>{filled}</span>/<span>{total}</span>
            </div>
          </div>

          {/* progress bar */}
          <div style={{
            position: "relative", height: 6,
            background: "oklch(0.20 0.013 100)", border: "1px solid var(--line-1)",
            borderRadius: 999, marginBottom: 18, overflow: "hidden",
          }}>
            <div style={{
              position: "absolute", left: 0, top: 0, bottom: 0,
              width: `${pct}%`,
              background: "linear-gradient(90deg, var(--brass-dim), var(--brass))",
            }}/>
            {conflictCount > 0 && (
              <div style={{
                position: "absolute", left: `${(filled - conflictCount) / total * 100 + 1}%`,
                top: 0, bottom: 0, width: `${conflictCount / total * 100}%`,
                background: "var(--rust)",
                opacity: 0.85,
              }}/>
            )}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            {archetype.slots.map((s, i) => (
              <SlotRow key={s.id}
                slot={s}
                onHover={() => setActiveZone(s.zones[0])}
                onLeave={() => setActiveZone(null)}
                onFind={() => onGoMarket(s.id)}
              />
            ))}
          </div>

          <div style={{ marginTop: 22, padding: "14px 14px", border: "1px solid var(--line-2)", borderRadius: 3, background: "oklch(0.21 0.013 100)" }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>оценка кита</div>
            <div className="num" style={{ fontSize: 22, color: "var(--fg-1)" }}>
              ~{window.fmt(298400)}
            </div>
            <div style={{ fontSize: 12, color: "var(--fg-4)", marginTop: 4 }}>
              с учётом 4 незакрытых позиций по медианной цене рынка
            </div>
          </div>
        </aside>

      </div>
    </div>
  );
};

/* ───────── stat block ───────── */
const StatBlock = ({ label, value, accent = "fg-1" }) => (
  <div style={{ textAlign: "right" }}>
    <div className="eyebrow" style={{ marginBottom: 4 }}>{label}</div>
    <div className="num" style={{
      fontSize: 24,
      color: `var(--${accent})`,
      fontWeight: 500,
    }}>{value}</div>
  </div>
);

/* ───────── layer key row ───────── */
const LayerKey = ({ n, name, sub, tone, last }) => (
  <div style={{
    display: "grid",
    gridTemplateColumns: "auto 1fr",
    gap: 12,
    padding: "10px 0",
    borderBottom: last ? "0" : "1px dashed var(--line-1)",
  }}>
    <div className="mono" style={{
      color: `var(--${tone})`,
      fontSize: 11, letterSpacing: "0.12em",
      paddingTop: 2,
    }}>{n}</div>
    <div>
      <div style={{ fontSize: 13.5, color: "var(--fg-1)" }}>{name}</div>
      <div style={{ fontSize: 11.5, color: "var(--fg-4)", marginTop: 2 }}>{sub}</div>
    </div>
  </div>
);

/* ───────── crosshair corner ───────── */
const Crosshair = ({ pos }) => {
  const map = {
    tl: { top: 8, left: 8 }, tr: { top: 8, right: 8 },
    bl: { bottom: 8, left: 8 }, br: { bottom: 8, right: 8 },
  };
  return (
    <svg width="14" height="14" viewBox="0 0 14 14"
      style={{ position: "absolute", ...map[pos], color: "var(--fg-5)", opacity: 0.6 }}>
      <path d="M 0 0 L 0 6 M 0 0 L 6 0" stroke="currentColor" strokeWidth="1" fill="none"/>
    </svg>
  );
};

/* ───────── slot row (right column) ───────── */
const SlotRow = ({ slot, onHover, onLeave, onFind }) => {
  const filled = !!slot.picked;
  const conflict = !!slot.conflict;
  return (
    <div
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto",
        gap: 12, alignItems: "center",
        padding: "8px 10px",
        borderRadius: 2,
        background: "oklch(0.20 0.013 100)",
        border: "1px solid var(--line-1)",
        ...(conflict ? { borderColor: "oklch(0.45 0.110 35 / 0.7)" } : {}),
        transition: "background 120ms ease, border-color 120ms ease",
      }}
    >
      <div style={{
        width: 28, height: 28,
        background: filled
          ? (conflict ? "oklch(0.30 0.080 35 / 0.5)" : "oklch(0.27 0.022 235 / 0.7)")
          : "oklch(0.18 0.013 100)",
        border: `1px solid ${filled ? "var(--line-3)" : "var(--line-1)"}`,
        borderRadius: 2,
        display: "grid", placeItems: "center",
        color: filled ? "var(--fg-1)" : "var(--fg-5)",
      }}>
        {filled ? (conflict ? "⚠" : "✓") : "+"}
      </div>
      <div>
        <div style={{ fontSize: 13, color: "var(--fg-1)" }}>{slot.label}</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 2 }}>
          {slot.short}{filled ? " · подобран" : " · пусто"}
        </div>
      </div>
      <div>
        {!filled ? (
          <button onClick={onFind} className="btn ghost" style={{ padding: "5px 9px", fontSize: 11, color: "var(--accent)" }}>
            найти ↗
          </button>
        ) : conflict ? (
          <button onClick={onFind} className="btn ghost" style={{ padding: "5px 9px", fontSize: 11, color: "var(--rust)" }}>
            заменить ↗
          </button>
        ) : (
          <span className="mono" style={{ fontSize: 10, color: "var(--patina)", letterSpacing: "0.1em" }}>OK</span>
        )}
      </div>
    </div>
  );
};

/* ───────── zone layer popover ───────── */
const ZoneLayerPopover = ({ zone, slots, onFind, onClose, onPick }) => {
  if (!slots.length) return null;
  const Z = window.BODY_ZONES[zone];

  // Re-sort by layer 1→4
  const byLayer = {};
  slots.forEach(s => {
    s.layers.forEach(L => {
      if (!byLayer[L]) byLayer[L] = [];
      byLayer[L].push(s);
    });
  });
  const layerKeys = [1, 2, 3, 4];

  return (
    <div style={{
      position: "absolute",
      right: 24, top: 70,
      width: 290,
      background: "oklch(0.20 0.013 100 / 0.97)",
      backdropFilter: "blur(8px)",
      border: "1px solid var(--line-3)",
      borderRadius: 3,
      padding: 14,
      boxShadow: "0 24px 40px oklch(0.05 0 0 / 0.5)",
      pointerEvents: "auto",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <div>
          <div className="eyebrow">зона</div>
          <div className="serif" style={{ fontSize: 18, color: "var(--fg-1)" }}>{Z.label}</div>
        </div>
        <button onClick={onClose} style={{ color: "var(--fg-4)", fontSize: 11, padding: 4 }}>✕</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {layerKeys.map(L => {
          const slotsForLayer = (byLayer[L] || []);
          const layerNames = { 1: "Подоспех", 2: "Кольчуга", 3: "Латы", 4: "Налатник" };
          const layerTones = { 1: "bone", 2: "steel", 3: "brass", 4: "patina" };
          const slot = slotsForLayer[0]; // simplification: 1 slot per layer per zone
          const item = slot?.picked ? window.ITEMS.find(i => i.id === slot.picked) : null;

          return (
            <div key={L} style={{
              display: "grid",
              gridTemplateColumns: "26px 36px 1fr auto",
              gap: 10, alignItems: "center",
              padding: "8px 8px",
              background: slot ? "oklch(0.23 0.013 100)" : "oklch(0.18 0.013 100)",
              borderRadius: 2,
              border: "1px solid var(--line-1)",
              opacity: slot ? 1 : 0.5,
            }}>
              <div className="mono" style={{ color: `var(--${layerTones[L]})`, fontSize: 11, letterSpacing: "0.12em" }}>
                0{L}
              </div>
              <div style={{
                width: 36, height: 36,
                background: item
                  ? "linear-gradient(180deg, oklch(0.27 0.013 100), oklch(0.20 0.013 100))"
                  : "oklch(0.18 0.013 100)",
                border: `1px solid ${item ? "var(--line-3)" : "var(--line-2)"}`,
                borderRadius: 2,
                display: "grid", placeItems: "center",
                color: item ? "var(--fg-2)" : "var(--fg-5)",
              }}>
                {item ? <SlotGlyph kind={item.image} size={26}/> : "+"}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 12, color: slot ? "var(--fg-1)" : "var(--fg-4)" }}>
                  {layerNames[L]}
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.08em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {item ? item.master : (slot ? "не подобран" : "не требуется")}
                </div>
              </div>
              {item ? (
                <button onClick={() => onPick(item.id)} className="btn ghost" style={{ padding: "3px 6px", fontSize: 10, color: "var(--fg-4)" }}>
                  →
                </button>
              ) : slot ? (
                <button onClick={() => onFind(slot.id)} className="btn ghost" style={{ padding: "3px 6px", fontSize: 10, color: "var(--accent)" }}>
                  найти
                </button>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
};

window.PaperdollScreen = PaperdollScreen;
