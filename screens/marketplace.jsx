/* Marketplace screen — inventory mode storefront */

const Marketplace = ({ archetype, onOpenItem, onGoPaperdoll }) => {
  const [mode, setMode] = React.useState("inventory"); // "gallery" | "inventory"
  const [hoverItem, setHoverItem] = React.useState(null);
  const [mousePos, setMousePos] = React.useState({ x: 0, y: 0 });

  const items = window.ITEMS;

  // Group items by archetype slot order
  const slotOrder = archetype.slots
    .filter(s => s.id !== "aventail")
    .map(s => s.id)
    .concat(["weapon"]);

  // Only show slots that actually have items
  const groups = slotOrder.map(slotId => ({
    slotId,
    slot: archetype.slots.find(s => s.id === slotId) || { id: "weapon", label: "Оружие", short: "ОРУЖ." },
    items: items.filter(it => it.slot === slotId),
  })).filter(g => g.items.length > 0);

  // facets
  const FACETS = [
    {
      title: "Период",
      key: "period",
      options: ["XII в.", "XIII в.", "XIV в.", "XV в.", "XVI в."],
      active: ["XIV в."],
    },
    {
      title: "Регион",
      key: "region",
      options: ["Чехия / Богемия", "Германия", "Италия", "Скандинавия", "Польша", "Русь"],
      active: ["Чехия / Богемия", "Германия"],
    },
    {
      title: "Дисциплина",
      key: "disc",
      options: ["HMB", "HEMA", "Реконструкция", "LARP"],
      active: ["HMB", "Реконструкция"],
    },
    {
      title: "Состояние",
      key: "cond",
      options: ["new", "used", "vintage"],
      active: ["new", "used"],
    },
  ];

  return (
    <div className="fade-in" style={{
      display: "grid",
      gridTemplateColumns: "260px 1fr",
      gap: 0,
      minHeight: "calc(100vh - 56px)",
    }} onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}>

      {/* ============== LEFT: facets ============== */}
      <aside style={{
        borderRight: "1px solid var(--line-1)",
        padding: "24px 22px 60px",
        position: "sticky",
        top: 56,
        height: "calc(100vh - 56px)",
        overflowY: "auto",
        background: "oklch(0.165 0.013 105)",
      }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>фасеты</div>
        <div className="serif" style={{ fontSize: 22, color: "var(--fg-1)", letterSpacing: "-0.015em" }}>
          Найти{"\u00A0"}предметы
        </div>
        <div style={{ marginTop: 6, fontSize: 12, color: "var(--fg-4)" }}>
          в рамках архетипа{" "}
          <button onClick={onGoPaperdoll} style={{ color: "var(--accent)", textDecoration: "underline", textUnderlineOffset: 3, cursor: "pointer" }}>
            «{archetype.title}, {archetype.period}»
          </button>
        </div>

        {/* price slider */}
        <div style={{ marginTop: 28 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>цена · ₽</div>
          <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 11, color: "var(--fg-3)" }}>
            <span>8 000</span>
            <span style={{ color: "var(--fg-4)" }}>—</span>
            <span>180 000</span>
          </div>
          <div style={{
            position: "relative", marginTop: 10, height: 24,
          }}>
            {/* histogram inside */}
            <div style={{ position: "absolute", inset: "8px 0", display: "flex", alignItems: "end", gap: 1 }}>
              {[3,5,7,11,14,18,22,28,24,19,15,12,9,7,5,3,2,1,2,1].map((h, i) => (
                <div key={i} style={{
                  flex: 1, height: `${h * 3}%`,
                  background: i >= 4 && i <= 14 ? "var(--accent)" : "var(--line-2)",
                  opacity: i >= 4 && i <= 14 ? 0.7 : 0.4,
                  borderRadius: 1,
                }}/>
              ))}
            </div>
            {/* range handles */}
            <div style={{ position: "absolute", left: "20%", top: 0, bottom: 0, width: 2, background: "var(--accent)" }}/>
            <div style={{ position: "absolute", left: "75%", top: 0, bottom: 0, width: 2, background: "var(--accent)" }}/>
          </div>
          <div className="mono" style={{ marginTop: 6, fontSize: 11, color: "var(--fg-2)" }}>
            32 000 — 130 000{"\u00A0"}₽
          </div>
        </div>

        {FACETS.map(f => (
          <div key={f.key} style={{ marginTop: 28 }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>{f.title}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {f.options.map(o => {
                const on = f.active.includes(o);
                return (
                  <button key={o} style={{
                    display: "grid",
                    gridTemplateColumns: "1fr auto",
                    alignItems: "center",
                    padding: "5px 8px", borderRadius: 2,
                    fontSize: 12.5, color: on ? "var(--fg-1)" : "var(--fg-3)",
                    background: on ? "oklch(0.26 0.013 100)" : "transparent",
                    borderLeft: on ? "2px solid var(--accent)" : "2px solid transparent",
                    transition: "all 120ms ease",
                    width: "100%",
                    textAlign: "left",
                    gap: 8,
                  }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                      <span style={{
                        width: 10, height: 10, border: `1px solid ${on ? "var(--accent)" : "var(--line-3)"}`,
                        background: on ? "var(--accent)" : "transparent",
                        display: "inline-block", borderRadius: 1, flexShrink: 0,
                      }}/>
                      <span style={{ whiteSpace: "nowrap" }}>{o}</span>
                    </span>
                    <span className="mono" style={{ color: "var(--fg-5)", fontSize: 10.5 }}>
                      {Math.floor(20 + ((o.length * 37) % 280))}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>
        ))}

        <div style={{ marginTop: 28, padding: "12px 12px", border: "1px dashed var(--line-2)", borderRadius: 3, fontSize: 11.5, color: "var(--fg-4)", lineHeight: 1.5 }}>
          Включить лоты из других регионов с доставкой?{" "}
          <button style={{ color: "var(--fg-2)", textDecoration: "underline", textUnderlineOffset: 2 }}>включить</button>
        </div>
      </aside>

      {/* ============== RIGHT: storefront ============== */}
      <main style={{ padding: "24px 32px 80px", minWidth: 0 }}>
        {/* Header row */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", gap: 20, marginBottom: 22 }}>
          <div>
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              <span style={{ color: "var(--accent)" }}>●</span>{"\u00A0"}архетип / {archetype.region.toLowerCase()} / {archetype.period.toLowerCase()}
            </div>
            <div className="h-xl">{archetype.title}, <span style={{ color: "var(--fg-3)" }}>{archetype.period}</span></div>
            <div style={{ marginTop: 10, fontSize: 13.5, color: "var(--fg-3)", maxWidth: 680 }}>
              {archetype.blurb}
            </div>
          </div>
          {/* mode toggle */}
          <div style={{ display: "flex", alignItems: "center", gap: 10, flexShrink: 0 }}>
            <span className="mono" style={{ color: "var(--fg-4)", fontSize: 10.5, letterSpacing: "0.14em", textTransform: "uppercase" }}>режим</span>
            <div style={{
              display: "flex", padding: 3, background: "oklch(0.20 0.013 100)",
              border: "1px solid var(--line-1)", borderRadius: 3,
            }}>
              {[
                ["inventory","Инвентарь"],
                ["gallery","Галерея"],
              ].map(([k,l]) => (
                <button key={k} onClick={() => setMode(k)} style={{
                  padding: "7px 14px", fontSize: 12.5, borderRadius: 2,
                  color: mode === k ? "var(--fg-1)" : "var(--fg-4)",
                  background: mode === k ? "oklch(0.30 0.013 100)" : "transparent",
                  boxShadow: mode === k ? "inset 0 0 0 1px var(--line-3)" : "none",
                  transition: "all 120ms ease",
                }}>{l}</button>
              ))}
            </div>
          </div>
        </div>

        {/* count row */}
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "10px 0", borderTop: "1px solid var(--line-1)",
          borderBottom: "1px solid var(--line-1)", marginBottom: 24,
        }}>
          <div className="mono" style={{ fontSize: 11.5, color: "var(--fg-3)", letterSpacing: "0.08em" }}>
            <span style={{ color: "var(--fg-1)" }}>247</span> лот· найдено
            <span style={{ margin: "0 14px", color: "var(--fg-5)" }}>|</span>
            <span style={{ color: "var(--fg-1)" }}>8</span> закрывают позиции архетипа
            <span style={{ margin: "0 14px", color: "var(--fg-5)" }}>|</span>
            <span style={{ color: "var(--rust)" }}>1</span> конфликт по периоду
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 12, color: "var(--fg-3)" }}>
            <span>Сортировка:</span>
            <button style={{ color: "var(--fg-1)" }}>период · ↓</button>
            <button>цена</button>
            <button>дата</button>
          </div>
        </div>

        {/* ============== inventory layout ============== */}
        {mode === "inventory" && (
          <div style={{ display: "grid", gap: 36 }}>
            {groups.map(g => (
              <SlotSection
                key={g.slotId}
                slot={g.slot}
                items={g.items}
                archetype={archetype}
                onHover={setHoverItem}
                onLeave={() => setHoverItem(null)}
                onOpen={onOpenItem}
              />
            ))}
          </div>
        )}

        {/* gallery mode */}
        {mode === "gallery" && (
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
            gap: 12,
          }}>
            {items.map(it => (
              <ListingCard key={it.id}
                item={it}
                onHover={setHoverItem}
                onLeave={() => setHoverItem(null)}
                onOpen={() => onOpenItem(it.id)}
              />
            ))}
          </div>
        )}
      </main>

      {/* hover preview — mini paperdoll projection */}
      {hoverItem && (
        <div className="mini-pop" style={{
          left: mousePos.x + 18,
          top: mousePos.y + 18,
          width: 220,
        }}>
          <div className="eyebrow" style={{ marginBottom: 4 }}>встанет на</div>
          <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
            <div style={{ flexShrink: 0 }}>
              <Paperdoll
                size={90}
                archetype={archetype}
                focusSlot={hoverItem.slot}
                showGrid={false}
              />
            </div>
            <div style={{ minWidth: 0, fontSize: 12 }}>
              <div style={{ color: "var(--fg-1)" }}>{archetype.slots.find(s => s.id === hoverItem.slot)?.label || hoverItem.subtype}</div>
              <div className="mono" style={{ color: "var(--fg-4)", fontSize: 10, marginTop: 4, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                слот {hoverItem.slot}
              </div>
              {hoverItem.conflictNote && (
                <div style={{ color: "var(--rust)", fontSize: 11, marginTop: 6, lineHeight: 1.4 }}>
                  ⚠ {hoverItem.conflictNote}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

/* ───────── slot section (inventory mode) ───────── */
const SlotSection = ({ slot, items, archetype, onHover, onLeave, onOpen }) => {
  if (!slot && items.length === 0) return null;
  const slotLabel = slot?.label || "Оружие";
  const shortLabel = slot?.short || "ОРУЖ.";
  return (
    <section>
      <header style={{
        display: "grid",
        gridTemplateColumns: "auto 1fr auto",
        gap: 16, alignItems: "center",
        marginBottom: 12,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <span className="mono" style={{
            color: "var(--accent)", fontSize: 10.5, letterSpacing: "0.18em",
            padding: "3px 7px", border: "1px solid var(--accent-dim)", borderRadius: 2,
            background: "oklch(0.22 0.040 78 / 0.2)",
          }}>{shortLabel}</span>
          <h3 className="serif" style={{ margin: 0, fontSize: 22, color: "var(--fg-1)", letterSpacing: "-0.015em" }}>
            {slotLabel}
          </h3>
        </div>
        <div style={{
          height: 1, background: "linear-gradient(90deg, var(--line-2), transparent)",
        }}/>
        <div className="mono" style={{ fontSize: 11, color: "var(--fg-4)", letterSpacing: "0.08em" }}>
          <span style={{ color: "var(--fg-1)" }}>{items.length}</span> предлож.{"\u00A0"}·{"\u00A0"}
          <span style={{ color: "var(--patina)" }}>{Math.floor(items.length * 0.6)} new</span>{"\u00A0"}/{"\u00A0"}
          <span style={{ color: "var(--steel)" }}>{Math.ceil(items.length * 0.4)} used</span>
        </div>
      </header>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))",
        gap: 12,
      }}>
        {items.map(it => (
          <ListingCard key={it.id}
            item={it}
            onHover={onHover}
            onLeave={onLeave}
            onOpen={() => onOpen(it.id)}
          />
        ))}
        {items.length === 0 && (
          <div className="slot empty" style={{
            minHeight: 220, display: "grid", placeItems: "center",
            padding: 16, textAlign: "center",
          }}>
            <div>
              <div className="mono" style={{ fontSize: 10.5, color: "var(--fg-5)", letterSpacing: "0.14em", textTransform: "uppercase" }}>
                нет предложений
              </div>
              <button className="btn" style={{ marginTop: 12 }}>+ создать запрос</button>
            </div>
          </div>
        )}
      </div>
    </section>
  );
};

/* ───────── listing card ───────── */
const ListingCard = ({ item, onHover, onLeave, onOpen }) => {
  return (
    <article
      onMouseEnter={() => onHover(item)}
      onMouseLeave={onLeave}
      onClick={onOpen}
      className="slot"
      style={{
        cursor: "pointer",
        display: "flex", flexDirection: "column",
        transition: "transform 140ms ease, border-color 140ms ease",
      }}
    >
      <div style={{ position: "relative", aspectRatio: "1 / 1", borderBottom: "1px solid var(--line-1)" }}>
        <ItemThumb item={item} />
        {/* corner badges */}
        <div style={{ position: "absolute", top: 8, right: 8, display: "flex", gap: 4 }}>
          <span className={`tag ${item.condition === "new" ? "patina" : "steel"}`}>{item.condition}</span>
          {item.conflictNote && <span className="tag rust" title={item.conflictNote}>⚠</span>}
        </div>
      </div>
      <div style={{ padding: "10px 12px 12px", display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
        <div style={{ fontSize: 13, color: "var(--fg-1)", lineHeight: 1.3, textWrap: "pretty" }}>
          {item.title}
        </div>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          <Tag>{item.period}</Tag>
          <Tag>{item.region}</Tag>
        </div>
        <div style={{ marginTop: "auto", display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "end" }}>
          <div style={{ minWidth: 0 }}>
            <div className="mono" style={{ fontSize: 10, color: "var(--fg-5)", letterSpacing: "0.08em", textTransform: "uppercase", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
              {item.master !== "—" ? item.master : "без мастера"}
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)", whiteSpace: "nowrap" }}>
              ⌖ {item.city}
            </div>
          </div>
          <div className="num" style={{ fontSize: 15, color: "var(--fg-1)", fontWeight: 500, whiteSpace: "nowrap" }}>
            {window.fmt(item.price)}
          </div>
        </div>
      </div>
    </article>
  );
};

window.Marketplace = Marketplace;
