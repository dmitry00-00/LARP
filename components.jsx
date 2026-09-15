/* HMB-Market — shared components */

const { useState, useEffect, useRef, useMemo } = React;

/* ─────────────────── icon glyphs ─────────────────── */
/* Simple iconographic stand-ins for item types. Thin stroke, not illustrative.
   These are not attempts at realistic medieval gear — they're slot-type glyphs. */
const SlotGlyph = ({ kind, size = 56, color = "var(--fg-3)" }) => {
  const s = size;
  const stroke = color;
  const sw = 1.1;
  const common = { fill: "none", stroke, strokeWidth: sw, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (kind) {
    case "helm":     return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M14 42 Q14 18 32 16 Q50 18 50 42 L46 50 L18 50 Z" {...common}/>
        <path d="M32 22 L32 50" {...common}/>
        <path d="M14 42 L50 42" {...common}/>
      </svg>);
    case "cuirass":  return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M14 16 L22 12 L32 16 L42 12 L50 16 L50 50 L32 56 L14 50 Z" {...common}/>
        <path d="M22 12 L22 56 M42 12 L42 56" {...common}/>
        <path d="M32 16 L32 56" {...common} strokeDasharray="2 3"/>
      </svg>);
    case "arm":      return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M22 8 L42 8 L40 22 L24 22 Z" {...common}/>
        <ellipse cx="32" cy="30" rx="12" ry="6" {...common}/>
        <path d="M22 36 L42 36 L40 56 L24 56 Z" {...common}/>
      </svg>);
    case "leg":      return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M22 8 L42 8 L42 22 L22 22 Z" {...common}/>
        <ellipse cx="32" cy="30" rx="12" ry="6" {...common}/>
        <path d="M24 36 L40 36 L36 56 L28 56 Z" {...common}/>
      </svg>);
    case "mail":     return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        {Array.from({length:6}).map((_,r) =>
          Array.from({length:6}).map((_,c) => (
            <circle key={`${r}-${c}`} cx={10 + c*9 + (r%2?4.5:0)} cy={10 + r*8} r="3" {...common}/>
          ))
        )}
      </svg>);
    case "gambeson": return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M16 14 L48 14 L48 56 L16 56 Z" {...common}/>
        <path d="M20 18 L20 54 M28 18 L28 54 M36 18 L36 54 M44 18 L44 54" {...common} strokeDasharray="2 2"/>
      </svg>);
    case "gauntlet": return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M18 50 L18 28 L24 22 L28 14 L30 14 L30 26 L36 26 L36 14 L38 14 L40 22 L46 28 L46 50 Z" {...common}/>
      </svg>);
    case "spaulder": return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M10 38 Q32 14 54 38" {...common}/>
        <path d="M14 42 Q32 22 50 42" {...common}/>
        <path d="M18 46 Q32 30 46 46" {...common}/>
      </svg>);
    case "cuisse":   return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M22 10 L42 10 L42 36 L36 56 L28 56 L22 36 Z" {...common}/>
        <path d="M22 18 L42 18 M22 26 L42 26" {...common}/>
      </svg>);
    case "greave":   return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M22 8 Q32 6 42 8 L40 56 L24 56 Z" {...common}/>
        <path d="M32 8 L32 56" {...common} strokeDasharray="2 3"/>
      </svg>);
    case "sabaton":  return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M14 38 L42 38 L52 48 L52 54 L14 54 Z" {...common}/>
        <path d="M22 38 L24 48 M30 38 L32 48 M38 38 L40 48" {...common}/>
      </svg>);
    case "sword":    return (
      <svg width={s} height={s} viewBox="0 0 64 64">
        <path d="M32 4 L32 44" {...common}/>
        <path d="M22 44 L42 44" {...common}/>
        <path d="M32 44 L32 56" {...common}/>
        <circle cx="32" cy="58" r="3" {...common}/>
      </svg>);
    default: return null;
  }
};
window.SlotGlyph = SlotGlyph;

/* ─────────────────── item thumbnail ─────────────────── */
const ItemThumb = ({ item, size = "auto", showLabel = true }) => {
  if (!item) return null;
  return (
    <div style={{ position: "relative", height: "100%", width: "100%" }}>
      <div className="placeholder" style={{
        position: "absolute", inset: 0,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <SlotGlyph kind={item.image} size={ size === "auto" ? "60%" : size } color="oklch(0.65 0.013 95 / 0.7)" />
      </div>
      {/* corner ID */}
      <div className="mono" style={{
        position: "absolute", top: 6, left: 6,
        fontSize: 9, color: "var(--fg-5)", letterSpacing: "0.1em"
      }}>{item.id.toUpperCase()}</div>
      {showLabel && (
        <div style={{
          position: "absolute", left: 8, right: 8, bottom: 8,
          display: "flex", justifyContent: "space-between", alignItems: "end",
          gap: 6, fontSize: 11,
        }}>
          <span style={{ color: "var(--fg-4)", textTransform: "uppercase", letterSpacing: "0.08em", fontFamily: "var(--font-mono)", fontSize: 9.5 }}>
            {item.subtype.split(",")[0]}
          </span>
        </div>
      )}
    </div>
  );
};
window.ItemThumb = ItemThumb;

/* ─────────────────── tag ─────────────────── */
const Tag = ({ children, tone, mono = true, style }) => (
  <span className={`tag ${tone || ""}`} style={{ fontFamily: mono ? undefined : "var(--font-sans)", textTransform: mono ? undefined : "none", letterSpacing: mono ? undefined : "0.01em", fontSize: mono ? undefined : 11, ...(style||{}) }}>
    {children}
  </span>
);
window.Tag = Tag;

/* ─────────────────── topbar ─────────────────── */
const TopBar = ({ route, onRoute }) => {
  const links = [
    { id: "registry",    label: "Реестр" },
    { id: "marketplace", label: "Витрина" },
    { id: "paperdoll",   label: "Архетип" },
    { id: "item",        label: "Карточка" },
  ];
  const nOffer = (window.ITEMS || []).length;
  const nWant  = (window.WANTS || []).length;
  const nSvc   = (window.SERVICES || []).length;
  return (
    <header className="topbar">
      <div className="brand">
        <div className="mark">
          {/* mark glyph: serif H over crossed bevel */}
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M3 3 L11 11 L19 3" stroke="currentColor" strokeWidth="1.4"/>
            <path d="M3 19 L11 11 L19 19" stroke="currentColor" strokeWidth="1.4"/>
            <circle cx="11" cy="11" r="2" fill="currentColor"/>
          </svg>
        </div>
        <div className="name">HMB-Market<em>ru · β</em></div>
      </div>
      <nav className="nav">
        {links.map((l, i) => (
          <button
            key={l.id}
            className={`nav-item ${route === l.id ? "active" : ""}`}
            onClick={() => onRoute(l.id)}
          >
            <span className="num">{String(i+1).padStart(2,"0")}</span>
            {l.label}
          </button>
        ))}
      </nav>
      <div className="topbar-right">
        <span className="pill" style={{ whiteSpace: "nowrap" }} title="предложение · спрос · услуги">
          <span className="dot"/>{nOffer} ▲ · {nWant} ▼ · {nSvc} ◆
        </span>
        <span className="mono" style={{ color: "var(--fg-4)", fontSize: 11, whiteSpace: "nowrap" }}>kit: Чешский рыцарь · 8/12</span>
        <button className="btn ghost" style={{ padding: "6px 10px" }}>войти</button>
      </div>
    </header>
  );
};
window.TopBar = TopBar;

/* ─────────────────── archetype selector ─────────────────── */
const ArchetypeBar = ({ value, onChange }) => (
  <div className="archetype-select" role="tablist">
    {window.ARCHETYPES.map(a => (
      <button
        key={a.id}
        className={value === a.id ? "on" : ""}
        onClick={() => onChange(a.id)}
        title={`${a.label}, ${a.period} · ${a.region}`}
      >
        {a.label} <span className="mono" style={{ color: "var(--fg-5)", marginLeft: 4 }}>{a.period}</span>
      </button>
    ))}
  </div>
);
window.ArchetypeBar = ArchetypeBar;

/* ─────────────────── price formatter ─────────────────── */
window.fmt = window.formatPrice;
