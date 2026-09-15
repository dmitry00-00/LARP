/* Item Card screen */

const ItemScreen = ({ itemId, archetype, onBack, onOpenItem, onGoMarket }) => {
  const item = window.ITEMS.find(i => i.id === itemId) || window.ITEMS.find(i => i.id === window.FEATURED_ITEM_ID);
  const detail = window.ITEM_DETAILS[item.id] || window.ITEM_DETAILS[window.FEATURED_ITEM_ID];
  const [photoIdx, setPhotoIdx] = React.useState(0);

  // Find slots covered by this item across archetype
  const coveredSlots = archetype.slots.filter(s => s.id === item.slot || (item.slot === "helm" && s.id === "aventail"));

  return (
    <div className="fade-in" style={{ padding: "20px 32px 80px" }}>

      {/* breadcrumbs */}
      <div className="mono" style={{
        fontSize: 11, color: "var(--fg-4)",
        letterSpacing: "0.1em", textTransform: "uppercase",
        marginBottom: 18,
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <button onClick={onBack} style={{ color: "var(--fg-3)" }}>витрина</button>
        <span style={{ color: "var(--fg-5)" }}>/</span>
        <span>шлемы</span>
        <span style={{ color: "var(--fg-5)" }}>/</span>
        <span>бацинеты</span>
        <span style={{ color: "var(--fg-5)" }}>/</span>
        <span style={{ color: "var(--fg-2)" }}>{item.id.toUpperCase()}</span>
      </div>

      {/* main two columns */}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1.35fr) minmax(0, 1fr)", gap: 36 }}>

        {/* ===== LEFT — gallery + provenance ===== */}
        <div>
          {/* photo gallery */}
          <div style={{
            position: "relative",
            aspectRatio: "1 / 1",
            background: "oklch(0.16 0.013 105)",
            border: "1px solid var(--line-1)",
            borderRadius: 3,
            overflow: "hidden",
            display: "grid", placeItems: "center",
          }}>
            <div className="placeholder" style={{ position: "absolute", inset: 0 }}/>
            <div style={{ position: "relative", zIndex: 1 }}>
              <SlotGlyph kind={item.image} size={260} color="oklch(0.75 0.013 95 / 0.85)" />
            </div>
            {/* photo counter / zoom */}
            <div style={{
              position: "absolute", top: 14, left: 16,
              fontFamily: "var(--font-mono)", fontSize: 10.5, color: "var(--fg-4)",
              letterSpacing: "0.14em", textTransform: "uppercase",
            }}>
              ph_{String(photoIdx + 1).padStart(2, "0")}{"\u00A0"}/{"\u00A0"}{String(detail.photos).padStart(2, "0")}
            </div>
            <div style={{
              position: "absolute", top: 14, right: 16,
              display: "flex", gap: 8,
            }}>
              <button className="btn ghost" style={{ padding: "5px 9px", fontSize: 11, background: "oklch(0.15 0.013 100 / 0.6)" }}>⌖ zoom</button>
              <button className="btn ghost" style={{ padding: "5px 9px", fontSize: 11, background: "oklch(0.15 0.013 100 / 0.6)" }}>360°</button>
            </div>
            <div style={{
              position: "absolute", bottom: 14, left: 0, right: 0,
              display: "flex", justifyContent: "center", gap: 12,
              fontFamily: "var(--font-mono)", fontSize: 10, color: "var(--fg-4)",
              letterSpacing: "0.14em",
            }}>
              <span>лот · {item.id}</span>
              <span style={{ color: "var(--fg-5)" }}>·</span>
              <span>1/1 масштаб</span>
              <span style={{ color: "var(--fg-5)" }}>·</span>
              <span>2160×2160 px</span>
            </div>
          </div>

          {/* thumbnail strip */}
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(${detail.photos}, 1fr)`,
            gap: 6, marginTop: 8,
          }}>
            {Array.from({ length: detail.photos }).map((_, i) => (
              <button key={i} onClick={() => setPhotoIdx(i)}
                className="slot"
                style={{
                  aspectRatio: "1 / 1",
                  cursor: "pointer",
                  borderColor: i === photoIdx ? "var(--accent)" : "var(--line-1)",
                  boxShadow: i === photoIdx ? "inset 0 0 0 1px var(--accent)" : "none",
                  padding: 0,
                }}>
                <div className="placeholder" style={{ position: "absolute", inset: 0 }}/>
                <div style={{ position: "relative", display: "grid", placeItems: "center", height: "100%", zIndex: 1 }}>
                  <SlotGlyph kind={item.image} size={28} color="oklch(0.55 0.013 95 / 0.7)" />
                </div>
              </button>
            ))}
          </div>

          {/* Construction & material */}
          <section style={{ marginTop: 36 }}>
            <SectionHeader number="01" title="Конструкция и материал" />
            <p style={{ fontSize: 14, color: "var(--fg-2)", lineHeight: 1.6, textWrap: "pretty" }}>
              {detail.construction}{" "}{detail.material}
            </p>
          </section>

          {/* Provenance */}
          <section style={{ marginTop: 36 }}>
            <SectionHeader number="02" title="История предмета" subtitle="provenance" />
            <ol style={{
              listStyle: "none",
              padding: 0, margin: 0,
              borderLeft: "1px solid var(--line-2)",
              paddingLeft: 22,
              position: "relative",
            }}>
              {detail.provenance.map((p, i) => (
                <li key={i} style={{
                  position: "relative",
                  paddingBottom: 18,
                }}>
                  <span style={{
                    position: "absolute",
                    left: -28,
                    top: 4,
                    width: 9, height: 9, borderRadius: "50%",
                    background: "var(--accent)",
                    boxShadow: "0 0 0 4px var(--bg-0)",
                  }}/>
                  <div className="mono" style={{ fontSize: 10.5, letterSpacing: "0.12em", color: "var(--fg-4)" }}>
                    {p.date}
                  </div>
                  <div style={{ marginTop: 4, color: "var(--fg-1)", fontSize: 13.5 }}>
                    {p.text}
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {/* Reference artifact */}
          <section style={{ marginTop: 36 }}>
            <SectionHeader number="03" title="Исторический референс" subtitle="реплика" />
            <div style={{
              display: "grid",
              gridTemplateColumns: "160px 1fr",
              gap: 16,
              border: "1px solid var(--line-1)",
              borderRadius: 3,
              padding: 16,
              background: "oklch(0.19 0.013 105)",
            }}>
              <div style={{
                aspectRatio: "1 / 1",
                background: "oklch(0.13 0.013 105)",
                borderRadius: 2,
                overflow: "hidden",
                position: "relative",
                border: "1px solid var(--line-2)",
              }}>
                <div className="placeholder" style={{ position: "absolute", inset: 0, opacity: 0.5 }}/>
                <div style={{ position: "relative", display: "grid", placeItems: "center", height: "100%", color: "var(--fg-5)" }}>
                  <span className="mono" style={{ fontSize: 9, letterSpacing: "0.14em" }}>МУЗЕЙНОЕ ФОТО</span>
                </div>
              </div>
              <div>
                <div className="eyebrow">артефакт</div>
                <div className="serif" style={{ fontSize: 17, color: "var(--fg-1)", marginTop: 4, letterSpacing: "-0.01em" }}>
                  {detail.referenceArtifact.title}
                </div>
                <div style={{ marginTop: 6, fontSize: 12.5, color: "var(--fg-3)", lineHeight: 1.5 }}>
                  {detail.referenceArtifact.blurb}
                </div>
                <button className="btn ghost" style={{ padding: "6px 0", marginTop: 12, fontSize: 11.5, color: "var(--accent)" }}>
                  открыть карточку артефакта →
                </button>
              </div>
            </div>
          </section>

          {/* Price chart */}
          <section style={{ marginTop: 36 }}>
            <SectionHeader number="04" title="Распределение цен" subtitle="бацинет · к. XIV в." />
            <PriceChart detail={detail} />
          </section>
        </div>

        {/* ===== RIGHT — meta column ===== */}
        <aside style={{ position: "sticky", top: 80, alignSelf: "start" }}>
          {/* Title block */}
          <div className="eyebrow" style={{ marginBottom: 6 }}>
            бацинет с авентейлом · {item.subtype}
          </div>
          <h1 className="h-lg" style={{ margin: 0 }}>
            {item.title}
          </h1>
          <div style={{ marginTop: 10, display: "flex", gap: 6, flexWrap: "wrap" }}>
            <Tag tone="brass">{item.period}</Tag>
            <Tag>{item.region}</Tag>
            <Tag tone="patina">new</Tag>
            <Tag>{item.discipline}</Tag>
          </div>

          {/* price row */}
          <div style={{
            marginTop: 22,
            padding: "18px 0 20px",
            borderTop: "1px solid var(--line-1)",
            borderBottom: "1px solid var(--line-1)",
            display: "grid",
            gridTemplateColumns: "1fr auto",
            alignItems: "end",
            gap: 16,
          }}>
            <div>
              <div className="num" style={{ fontSize: 38, color: "var(--fg-1)", fontWeight: 500, letterSpacing: "-0.02em", lineHeight: 1 }}>
                {window.fmt(item.price)}
              </div>
              <div className="mono" style={{ fontSize: 11, color: "var(--fg-4)", letterSpacing: "0.1em", marginTop: 8, textTransform: "uppercase" }}>
                выше медианы рынка на{" "}
                <span style={{ color: "var(--brass)" }}>+{Math.round((item.price - detail.market.median) / detail.market.median * 100)}%</span>
                <span style={{ marginLeft: 10, color: "var(--fg-5)" }}>·</span>
                <span style={{ marginLeft: 10 }}>{detail.market.myPercentile}-й перцентиль</span>
              </div>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <button className="btn primary" style={{ padding: "10px 20px" }}>Купить · 1 клик</button>
              <button className="btn">Связаться · @zhihar.forge</button>
            </div>
          </div>

          {/* What it covers (paperdoll mini) */}
          <section style={{ marginTop: 22 }}>
            <SectionHeader number="A" title="Занимает на paperdoll" subtitle={`${coveredSlots.length} слот${coveredSlots.length > 1 ? "а" : ""}`} compact />
            <div style={{
              display: "grid",
              gridTemplateColumns: "auto 1fr",
              gap: 16,
              marginTop: 6,
              padding: "12px 14px",
              background: "oklch(0.19 0.013 105)",
              border: "1px solid var(--line-1)",
              borderRadius: 3,
            }}>
              <div style={{ display: "grid", placeItems: "center" }}>
                <Paperdoll
                  size={130}
                  archetype={archetype}
                  focusSlot={item.slot}
                  showGrid={false}
                />
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 6, paddingTop: 8 }}>
                {coveredSlots.map(s => (
                  <div key={s.id} style={{ display: "flex", alignItems: "baseline", gap: 8, fontSize: 12.5 }}>
                    <span className="mono" style={{ color: "var(--brass)", fontSize: 10, letterSpacing: "0.12em" }}>
                      {s.layers.map(l => `0${l}`).join("·")}
                    </span>
                    <span style={{ color: "var(--fg-1)" }}>{s.label}</span>
                    <span className="mono" style={{ marginLeft: "auto", color: "var(--fg-5)", fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase" }}>
                      {s.zones.length} зон
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Measurements */}
          <section style={{ marginTop: 22 }}>
            <SectionHeader number="B" title="Размеры и материал" compact />
            <dl style={{ margin: 0 }}>
              {detail.measurements.map(m => (
                <div key={m.k} className="meta-row">
                  <dt>{m.k}</dt>
                  <dd>
                    <span className="num">{m.v}</span>
                    {m.note && <span style={{ color: "var(--fg-4)", marginLeft: 10, fontSize: 11.5 }}>· {m.note}</span>}
                  </dd>
                </div>
              ))}
              <div className="meta-row">
                <dt>Мастер</dt>
                <dd style={{ color: "var(--fg-1)" }}>{item.master}</dd>
              </div>
              <div className="meta-row">
                <dt>Локация</dt>
                <dd>{item.city}</dd>
              </div>
            </dl>
          </section>

          {/* Compatible archetypes */}
          <section style={{ marginTop: 22 }}>
            <SectionHeader number="C" title="Совместимо с архетипами" compact />
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {detail.fitsArchetypes.map(a => (
                <div key={a.id} style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 80px auto",
                  gap: 12, alignItems: "center",
                  padding: "8px 12px",
                  background: "oklch(0.19 0.013 105)",
                  border: "1px solid var(--line-1)",
                  borderRadius: 2,
                }}>
                  <div>
                    <div style={{ fontSize: 12.5, color: "var(--fg-1)" }}>{a.label}</div>
                    {a.note && <div style={{ fontSize: 11, color: "var(--fg-4)", marginTop: 2 }}>{a.note}</div>}
                  </div>
                  <div style={{ position: "relative", height: 4, background: "oklch(0.20 0.013 100)", borderRadius: 999, overflow: "hidden" }}>
                    <div style={{
                      position: "absolute", left: 0, top: 0, bottom: 0,
                      width: `${a.fit * 100}%`,
                      background: a.fit > 0.8 ? "var(--patina)" : a.fit > 0.5 ? "var(--brass)" : "var(--rust)",
                    }}/>
                  </div>
                  <span className="num" style={{ fontSize: 11, color: "var(--fg-3)", minWidth: 30, textAlign: "right" }}>
                    {Math.round(a.fit * 100)}%
                  </span>
                </div>
              ))}
            </div>
          </section>

          {/* Seller */}
          <section style={{ marginTop: 22 }}>
            <SectionHeader number="D" title="Продавец" compact />
            <div style={{
              display: "grid",
              gridTemplateColumns: "48px 1fr auto",
              gap: 14, alignItems: "center",
              padding: 14,
              background: "oklch(0.19 0.013 105)",
              border: "1px solid var(--line-1)",
              borderRadius: 3,
            }}>
              <div style={{
                width: 48, height: 48,
                background: "linear-gradient(135deg, oklch(0.32 0.013 100), oklch(0.22 0.013 100))",
                border: "1px solid var(--line-3)",
                borderRadius: 2,
                display: "grid", placeItems: "center",
                fontFamily: "var(--font-serif)", fontSize: 22, color: "var(--brass)",
              }}>Ж</div>
              <div style={{ minWidth: 0 }}>
                <div style={{ display: "flex", alignItems: "baseline", gap: 8, flexWrap: "wrap" }}>
                  <span style={{ color: "var(--fg-1)", fontSize: 14, whiteSpace: "nowrap" }}>{detail.seller.name}</span>
                  <span className="mono" style={{ color: "var(--patina)", fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", whiteSpace: "nowrap" }}>● верифицирован</span>
                </div>
                <div className="mono" style={{ fontSize: 11, color: "var(--fg-4)", marginTop: 4, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {detail.seller.handle}
                </div>
                <div style={{ marginTop: 4, fontSize: 11.5, color: "var(--fg-3)" }}>
                  ★ {detail.seller.rep} <span style={{ color: "var(--fg-5)" }}>({detail.seller.reviewCount} отзыв)</span>
                </div>
              </div>
              <button className="btn ghost" style={{ padding: "6px 10px", fontSize: 11.5, whiteSpace: "nowrap" }}>профиль →</button>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
};

/* ───────── section header ───────── */
const SectionHeader = ({ number, title, subtitle, compact }) => (
  <header style={{
    display: "grid",
    gridTemplateColumns: "auto 1fr auto",
    gap: 12, alignItems: "baseline",
    marginBottom: compact ? 10 : 14,
  }}>
    <span className="mono" style={{
      color: "var(--accent)",
      fontSize: compact ? 10.5 : 11,
      letterSpacing: "0.16em",
      padding: compact ? "2px 6px" : "3px 8px",
      border: "1px solid var(--accent-dim)",
      borderRadius: 2,
      background: "oklch(0.22 0.040 78 / 0.18)",
    }}>{number}</span>
    <h3 className={compact ? "" : "serif"} style={{
      margin: 0,
      fontSize: compact ? 14 : 22,
      fontFamily: compact ? "var(--font-sans)" : "var(--font-serif)",
      color: "var(--fg-1)",
      letterSpacing: compact ? "0" : "-0.015em",
      fontWeight: compact ? 500 : 400,
    }}>{title}</h3>
    {subtitle && (
      <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)", letterSpacing: "0.1em", textTransform: "uppercase" }}>
        {subtitle}
      </span>
    )}
  </header>
);

/* ───────── price chart ───────── */
const PriceChart = ({ detail }) => {
  const points = window.PRICE_POINTS;
  const xMin = 30, xMax = 130;
  const W = 100, H = 180;
  const xScale = (x) => ((x - xMin) / (xMax - xMin)) * 100;
  return (
    <div style={{
      padding: "20px 22px",
      background: "oklch(0.18 0.013 105)",
      border: "1px solid var(--line-1)",
      borderRadius: 3,
    }}>
      {/* legend */}
      <div style={{ display: "flex", gap: 18, alignItems: "center", marginBottom: 14, fontSize: 11.5 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--fg-3)" }}>
          <span style={{ width: 10, height: 10, background: "var(--patina)", borderRadius: "50%" }}/> new ({detail.market.newCount})
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 6, color: "var(--fg-3)" }}>
          <span style={{ width: 10, height: 10, background: "var(--steel-dim)", borderRadius: "50%" }}/> used ({detail.market.usedCount})
        </span>
        <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 6, color: "var(--fg-3)" }}>
          <span style={{ width: 14, height: 2, background: "var(--bone)", boxShadow: "0 0 4px var(--bone)" }}/> этот лот
        </span>
      </div>

      {/* main plot */}
      <div style={{
        position: "relative",
        height: 170,
        marginBottom: 30,
      }}>
        {/* gridlines */}
        {[40, 60, 80, 100, 120].map(g => (
          <div key={g} style={{
            position: "absolute",
            left: `${xScale(g)}%`,
            top: 0, bottom: 30,
            borderLeft: "1px dashed var(--line-1)",
          }}/>
        ))}

        {/* horizontal axes for new/used */}
        <div style={{
          position: "absolute", left: 0, right: 0, top: 30,
          height: 1, background: "var(--line-2)",
        }}/>
        <div style={{
          position: "absolute", left: 0, right: 0, top: 100,
          height: 1, background: "var(--line-2)",
        }}/>

        {/* row labels */}
        <span className="mono" style={{ position: "absolute", left: 0, top: 6, fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.12em" }}>new</span>
        <span className="mono" style={{ position: "absolute", left: 0, top: 76, fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.12em" }}>used</span>

        {/* points */}
        {points.map((p, i) => {
          const y = p.c === "new" ? 30 : 100;
          const left = xScale(p.x);
          return (
            <div key={i} style={{
              position: "absolute",
              left: `calc(${left}% - 5px)`,
              top: y + 6,
              width: 10, height: 10,
              borderRadius: "50%",
              background: p.mine
                ? "var(--bone)"
                : (p.c === "new" ? "oklch(0.66 0.055 168 / 0.7)" : "oklch(0.56 0.024 240 / 0.7)"),
              border: p.mine ? "2px solid var(--bone)" : "1px solid oklch(0.4 0.014 95 / 0.5)",
              boxShadow: p.mine ? "0 0 12px var(--bone)" : "none",
              zIndex: p.mine ? 5 : 1,
            }}/>
          );
        })}

        {/* median marker */}
        <div style={{
          position: "absolute",
          left: `${xScale(detail.market.median / 1000)}%`,
          top: 30, bottom: 0,
          width: 0,
          borderLeft: "1px solid var(--fg-3)",
        }}>
          <span className="mono" style={{
            position: "absolute", top: -16, left: 4,
            fontSize: 9.5, color: "var(--fg-3)", letterSpacing: "0.12em",
            background: "oklch(0.18 0.013 105)",
            padding: "0 4px",
          }}>med 71к</span>
        </div>

        {/* p25-p75 band */}
        <div style={{
          position: "absolute",
          left: `${xScale(detail.market.p25 / 1000)}%`,
          width: `${xScale(detail.market.p75 / 1000) - xScale(detail.market.p25 / 1000)}%`,
          top: 130,
          height: 10,
          background: "oklch(0.55 0.060 90 / 0.18)",
          border: "1px solid oklch(0.45 0.060 90 / 0.6)",
          borderRadius: 1,
        }}/>
        <span className="mono" style={{
          position: "absolute", top: 145,
          left: `${xScale(detail.market.p25 / 1000)}%`,
          fontSize: 9, color: "var(--fg-5)", letterSpacing: "0.1em",
        }}>p25–p75</span>

        {/* x-axis labels */}
        {[30, 50, 70, 90, 110, 130].map(t => (
          <span key={t} className="mono" style={{
            position: "absolute",
            left: `calc(${xScale(t)}% - 12px)`,
            bottom: 0,
            fontSize: 10, color: "var(--fg-4)", letterSpacing: "0.08em",
          }}>{t}к</span>
        ))}

        {/* mine arrow */}
        <div style={{
          position: "absolute",
          left: `calc(${xScale(78)}% - 8px)`,
          top: -10,
          fontSize: 11, color: "var(--fg-1)",
          fontFamily: "var(--font-mono)", letterSpacing: "0.1em",
        }}>
          ↓ этот лот
        </div>
      </div>

      {/* summary row */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: 18,
        paddingTop: 14,
        borderTop: "1px solid var(--line-1)",
      }}>
        <Stat label="на рынке сейчас" value={detail.market.newCount + detail.market.usedCount} unit="лот" />
        <Stat label="медиана" value={"71"} unit="тыс. ₽" />
        <Stat label="средний возраст" value={detail.market.avgListingAge} />
        <Stat label="перцентиль лота" value={detail.market.myPercentile + "-й"} accent="brass" />
      </div>
    </div>
  );
};

const Stat = ({ label, value, unit, accent = "fg-1" }) => (
  <div>
    <div className="eyebrow" style={{ marginBottom: 4 }}>{label}</div>
    <div style={{ display: "baseline", display: "flex", alignItems: "baseline", gap: 6 }}>
      <span className="num" style={{ fontSize: 22, color: `var(--${accent})`, fontWeight: 500 }}>{value}</span>
      {unit && <span className="mono" style={{ fontSize: 10.5, color: "var(--fg-4)", letterSpacing: "0.1em" }}>{unit}</span>}
    </div>
  </div>
);

window.ItemScreen = ItemScreen;
