/* Paperdoll — anatomical silhouette w/ body-zone overlays
   320×560 viewBox. Stylised, not anatomically detailed.
   Props:
     size       — render width in px (height proportional)
     archetype  — archetype slot list (see ARCHETYPE_CK14)
     filledMap  — { slotId: true } — which slots are equipped
     conflicts  — { slotId: true } — which slots have a conflict
     activeZone — currently hovered/active zone id
     focusSlot  — slot id to single out (used on item card "what it covers")
     onZoneHover/onZoneLeave/onZoneClick — interactivity
     compact    — drop the labels & micro-anatomy
*/

const Paperdoll = ({
  size = 320,
  archetype,
  filledMap = {},
  conflicts = {},
  activeZone = null,
  focusSlot = null,
  onZoneHover = () => {},
  onZoneLeave = () => {},
  onZoneClick = () => {},
  showGrid = true,
}) => {
  const W = 320, H = 560;
  const Z = window.BODY_ZONES;

  // build a set of zones that are equipped (any slot covering them)
  const equippedZones = new Set();
  const conflictZones = new Set();
  const focusZones = new Set();
  if (archetype) {
    archetype.slots.forEach(s => {
      const eq = !!filledMap[s.id];
      const cf = !!conflicts[s.id];
      const inFocus = focusSlot && s.id === focusSlot;
      s.zones.forEach(z => {
        if (eq) equippedZones.add(z);
        if (cf) conflictZones.add(z);
        if (inFocus) focusZones.add(z);
      });
    });
  }

  // archetype-relevant zones = union of all slot zones
  const relevantZones = new Set();
  if (archetype) archetype.slots.forEach(s => s.zones.forEach(z => relevantZones.add(z)));

  const rect = (z, key) => {
    const zo = Z[z];
    if (!zo) return null;
    const isRelevant = relevantZones.has(z);
    const isEquipped = equippedZones.has(z);
    const isConflict = conflictZones.has(z);
    const isFocus    = focusZones.has(z);
    const isActive   = activeZone === z;

    let fill = "transparent";
    let stroke = "transparent";
    let opacity = isRelevant ? 1 : 0.18;
    if (isEquipped)  fill = "oklch(0.55 0.030 235 / 0.55)";   // steel tint
    if (isConflict)  fill = "oklch(0.55 0.130 35 / 0.55)";
    if (isFocus)     fill = "oklch(0.66 0.085 78 / 0.55)";    // brass
    if (isActive)    stroke = "oklch(0.85 0.020 95 / 0.9)";

    return (
      <g
        key={key}
        style={{ cursor: isRelevant ? "pointer" : "default" }}
        onMouseEnter={() => isRelevant && onZoneHover(z)}
        onMouseLeave={() => isRelevant && onZoneLeave(z)}
        onClick={() => isRelevant && onZoneClick(z)}
      >
        <rect
          x={zo.cx - zo.w/2}
          y={zo.cy - zo.h/2}
          width={zo.w}
          height={zo.h}
          rx={4}
          fill={fill}
          stroke={stroke}
          strokeWidth={isActive ? 1.5 : 0}
          style={{
            opacity,
            transition: "fill 200ms ease, opacity 200ms ease",
            ...(isConflict ? { animation: "conflict-pulse 2.4s ease-in-out infinite" } : {}),
          }}
        />
        {/* invisible hit area on the silhouette */}
        <rect
          x={zo.cx - zo.w/2 - 4}
          y={zo.cy - zo.h/2 - 4}
          width={zo.w + 8}
          height={zo.h + 8}
          fill="transparent"
        />
      </g>
    );
  };

  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={size} style={{ display: "block", userSelect: "none" }}>
      <defs>
        <linearGradient id="pd-body" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%"  stopColor="oklch(0.31 0.013 100)" />
          <stop offset="100%" stopColor="oklch(0.22 0.013 100)" />
        </linearGradient>
        <linearGradient id="pd-shade" x1="0" x2="1" y1="0" y2="0">
          <stop offset="0%"   stopColor="oklch(0 0 0 / 0)" />
          <stop offset="50%"  stopColor="oklch(0 0 0 / 0.18)" />
          <stop offset="100%" stopColor="oklch(0 0 0 / 0)" />
        </linearGradient>
        <pattern id="pd-grid" width="20" height="20" patternUnits="userSpaceOnUse">
          <path d="M 20 0 L 0 0 0 20" fill="none" stroke="oklch(0.30 0.013 100 / 0.35)" strokeWidth="0.5"/>
        </pattern>
        {/* slight inner shadow for body */}
        <filter id="pd-inner" x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur stdDeviation="0.4"/>
        </filter>
      </defs>

      {/* grid bg */}
      {showGrid && <rect x="0" y="0" width={W} height={H} fill="url(#pd-grid)" />}

      {/* silhouette base — drawn as overlapping rounded shapes for a stylised look */}
      <g fill="url(#pd-body)" stroke="oklch(0.40 0.012 95 / 0.7)" strokeWidth="0.8">
        {/* head */}
        <ellipse cx="160" cy="60" rx="30" ry="35" />
        {/* neck */}
        <rect x="146" y="92" width="28" height="26" rx="6" />
        {/* shoulders / trapezius */}
        <path d="M 100 122 Q 160 108 220 122 L 232 156 Q 160 142 88 156 Z" />
        {/* chest */}
        <rect x="108" y="148" width="104" height="86" rx="14" />
        {/* upper arms */}
        <rect x="84"  y="156" width="28" height="80" rx="12" />
        <rect x="208" y="156" width="28" height="80" rx="12" />
        {/* elbows + forearms */}
        <rect x="80"  y="232" width="28" height="76" rx="12" />
        <rect x="212" y="232" width="28" height="76" rx="12" />
        {/* hands */}
        <ellipse cx="80"  cy="320" rx="13" ry="17" />
        <ellipse cx="240" cy="320" rx="13" ry="17" />
        {/* waist */}
        <path d="M 116 232 L 204 232 L 198 282 L 122 282 Z" />
        {/* groin / hip block */}
        <path d="M 118 280 L 202 280 L 206 320 Q 160 332 114 320 Z" />
        {/* thighs */}
        <rect x="120" y="318" width="38" height="86" rx="14" />
        <rect x="162" y="318" width="38" height="86" rx="14" />
        {/* knees */}
        <rect x="120" y="398" width="38" height="28" rx="10" />
        <rect x="162" y="398" width="38" height="28" rx="10" />
        {/* shins */}
        <rect x="122" y="424" width="34" height="72" rx="10" />
        <rect x="164" y="424" width="34" height="72" rx="10" />
        {/* feet */}
        <ellipse cx="139" cy="514" rx="22" ry="13" />
        <ellipse cx="181" cy="514" rx="22" ry="13" />
      </g>

      {/* centerline + median markers */}
      <line x1="160" y1="20" x2="160" y2="540" stroke="oklch(0.35 0.012 95 / 0.4)" strokeDasharray="2 3" strokeWidth="0.5"/>

      {/* zone overlays */}
      {Object.keys(Z).map(z => rect(z, z))}

      {/* technical labels at the corners — только в техническом режиме:
          в компактной проекции (188 px) они превращались в нечитаемый шум */}
      {showGrid && <g fontFamily="JetBrains Mono, monospace" fontSize="8" fill="oklch(0.5 0.013 95)" letterSpacing="0.5">
        <text x="6"  y="14">0,0</text>
        <text x="6"  y={H - 6}>0,{H}</text>
        <text x={W - 38} y="14">{W},0</text>
        <text x={W - 50} y={H - 6}>{W},{H}</text>
      </g>}
    </svg>
  );
};

window.Paperdoll = Paperdoll;

/* Mini paperdoll silhouette — drops zone overlays around just a focusSlot */
const PaperdollMini = ({ archetype, focusSlot, size = 110 }) => {
  return (
    <Paperdoll
      size={size}
      archetype={archetype}
      filledMap={{}}
      focusSlot={focusSlot}
      showGrid={false}
    />
  );
};
window.PaperdollMini = PaperdollMini;
