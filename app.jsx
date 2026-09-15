/* HMB-Market — app shell */

const App = () => {
  const [route, setRoute] = React.useState("registry");
  const [itemId, setItemId] = React.useState(window.FEATURED_ITEM_ID);

  const archetype = window.ARCHETYPE_CK14;

  // Tweaks
  const defaults = window.HMB_TWEAK_DEFAULTS;
  const [t, setTweak] = window.useTweaks(defaults);

  // Apply tweaks to CSS variables
  React.useEffect(() => {
    const root = document.documentElement;
    // accent is a hex / oklch string
    const a = t.accent || "oklch(0.760 0.085 78)";
    root.style.setProperty("--accent", a);
    root.style.setProperty("--accent-dim", `color-mix(in oklch, ${a}, oklch(0.18 0.013 100) 35%)`);

    const serifMap = {
      Newsreader: '"Newsreader", ui-serif, Georgia, serif',
      "Source Serif 4": '"Source Serif 4", ui-serif, Georgia, serif',
      Cormorant: '"Cormorant Garamond", ui-serif, Georgia, serif',
    };
    root.style.setProperty("--font-serif", serifMap[t.serif] || serifMap.Newsreader);

    const sansMap = {
      "Hanken Grotesk": '"Hanken Grotesk", ui-sans-serif, system-ui, sans-serif',
      "Schibsted Grotesk": '"Schibsted Grotesk", ui-sans-serif, system-ui, sans-serif',
      "Geist": '"Geist", ui-sans-serif, system-ui, sans-serif',
    };
    root.style.setProperty("--font-sans", sansMap[t.sans] || sansMap["Hanken Grotesk"]);
  }, [t.accent, t.serif, t.sans]);

  const openItem = (id) => { setItemId(id); setRoute("item"); window.scrollTo({ top: 0 }); };
  const goMarket = (slotId) => { setRoute("marketplace"); window.scrollTo({ top: 0 }); };
  const goPaperdoll = () => { setRoute("paperdoll"); window.scrollTo({ top: 0 }); };

  let screen;
  if (route === "registry") {
    screen = <Registry
      archetype={archetype}
      onOpenItem={openItem}
      onGoPaperdoll={goPaperdoll}
    />;
  } else if (route === "marketplace") {
    screen = <Marketplace
      archetype={archetype}
      onOpenItem={openItem}
      onGoPaperdoll={goPaperdoll}
    />;
  } else if (route === "paperdoll") {
    screen = <PaperdollScreen
      archetype={archetype}
      onOpenItem={openItem}
      onGoMarket={goMarket}
    />;
  } else {
    screen = <ItemScreen
      itemId={itemId}
      archetype={archetype}
      onBack={() => setRoute("marketplace")}
      onOpenItem={openItem}
      onGoMarket={goMarket}
    />;
  }

  return (
    <div className="app" data-screen-label={route === "registry" ? "01 Реестр · спрос и предложение" : route === "marketplace" ? "02 Витрина (инвентарь)" : route === "paperdoll" ? "03 Paperdoll · Архетип" : "04 Карточка предмета"}>
      <TopBar route={route} onRoute={(r) => { setRoute(r); window.scrollTo({ top: 0 }); }} />
      {screen}

      {/* Tweaks panel */}
      <window.TweaksPanel title="Tweaks · HMB-Market">
        <window.TweakSection label="Акцент-металл">
          <window.TweakColor
            label="оттенок"
            value={t.accent}
            onChange={(v) => setTweak("accent", v)}
            options={[
              "#bf9a45",
              "#8a93a5",
              "#7faa92",
              "#d8cfb4",
            ]}
          />
        </window.TweakSection>
        <window.TweakSection label="Типографика">
          <window.TweakSelect
            label="засечный"
            value={t.serif}
            onChange={(v) => setTweak("serif", v)}
            options={["Newsreader", "Source Serif 4", "Cormorant"]}
          />
          <window.TweakSelect
            label="гротеск"
            value={t.sans}
            onChange={(v) => setTweak("sans", v)}
            options={["Hanken Grotesk", "Schibsted Grotesk", "Geist"]}
          />
        </window.TweakSection>
      </window.TweaksPanel>
    </div>
  );
};

const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(<App />);
