"""Epic Armoury — Shopify `/products.json`: номенклатура, спецификации, якоря €.

Что берём (DATA_SOURCES §5): название, тип, теги, вариант-цену, URL, и
спецификации из описания (Length / Weight / Core / Materials / Brand) —
как числа. Что НЕ берём: `body_html` целиком и фото. Ссылка на оригинал —
в `source_url`.

robots.txt (15.09.2026): `/products.json` не запрещён, `Allow: /`.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from hmb.http import Http
from hmb.models import Lot, Source
from hmb.slots import SlotMatcher

log = structlog.get_logger("hmb.import.epicarmoury")

# Все три — Shopify с открытым /products.json; robots.txt проверены 15.09.2026
# (products.json не запрещён ни у кого). Один код — три витрины.
SITES = {
    "epicarmoury": {"base": "https://epicarmoury.com", "title": "Epic Armoury (Iron Fortress)", "country": "DK", "lang": "en", "currency": "EUR",
                    "note": "Shopify products.json; замер 15.09.2026: 1 866 товаров"},
    "calimacil": {"base": "https://calimacil.com", "title": "Calimacil", "country": "CA", "lang": "en", "currency": "CAD",
                  "note": "Shopify products.json; vendor/product_type заполнены; цены — CAD (валюта магазина по умолчанию)"},
    "dein_larp_shop": {"base": "https://www.dein-larp-shop.de", "title": "Dein LARP Shop", "country": "DE", "lang": "de", "currency": "EUR",
                       "note": "Shopify products.json; product_type у всех «Artikel» — слот только по названию (немецкая номенклатура)"},
}
SOURCE_ID = "epicarmoury"   # обратная совместимость: `hmb import epicarmoury`
BASE = SITES[SOURCE_ID]["base"]

# В products.json спецификации — ПРОЗОЙ («It is 75 cm long», «around a
# fiberglass core», «latex coating»); поля «Length: 75 cm / Weight: 407 g»
# живут только на HTML-странице товара (замер 15.09.2026). Здесь — проза;
# HTML-страницы — отдельный проход, если понадобится масса.
_SPEC_RX = {
    "length_cm": re.compile(r"(?:length:?\s*|is\s+|measures\s+|approx(?:imately)?\.?\s+)?(\d{2,3}(?:[.,]\d)?)\s*cm\b(?:\s+(?:long|in\s+length|from\s+pommel))?", re.I),
    "weight_g": re.compile(r"(?:weight:?\s*|weighs\s+)(\d{2,4})\s*g(?:rams)?\b", re.I),
    "core": re.compile(r"\b(fiber\s*glass|fibre\s*glass|carbon(?:\s+fiber)?|kevlar|wooden|wood|bamboo|steel|aluminium|aluminum|pu|polyurethane|plastic)\s+(?:rod\s+)?core\b", re.I),
    "coating": re.compile(r"\b(latex|polyurethane|pu|silicone|hybrid)\s+(?:coating|coated|finish|skin)\b", re.I),
    "material": re.compile(r"\b(closed[\s-]cell\s+foam|eva\s+foam|polyurethane\s+foam|pu\s+foam|foam|leather|suede|linen|cotton|wool|steel|brass|latex)\b", re.I),
}
_TAG_RX = re.compile(r"<[^>]+>")


def _specs(body_html: str) -> dict:
    text = _TAG_RX.sub("\n", body_html or "")
    out: dict = {}
    m = _SPEC_RX["length_cm"].search(text)
    if m:
        # «75 cm long» — да; «5 cm wide» — нет: без хвоста long/length берём
        # только явное «length:» или «is N cm».
        span = text[max(0, m.start() - 12):m.end() + 12].lower()
        if any(k in span for k in ("long", "length", "is ", "measures", "approx")) and "wide" not in span and "diameter" not in span:
            out["length_cm"] = float(m.group(1).replace(",", "."))
    m = _SPEC_RX["weight_g"].search(text)
    if m:
        out["weight_g"] = float(m.group(1))
    m = _SPEC_RX["core"].search(text)
    if m:
        out["core"] = m.group(1).lower().replace(" ", "")
    m = _SPEC_RX["coating"].search(text)
    if m:
        out["coating"] = m.group(1).lower()
    mats = sorted({x.lower() for x in _SPEC_RX["material"].findall(text)})
    if mats:
        out["materials"] = mats[:6]
    return out


def ensure_source(db, sid: str = SOURCE_ID) -> Source:
    cfg = SITES[sid]
    src = db.get(Source, sid)
    if src is None:
        src = Source(id=sid, kind="catalog", title=cfg["title"], url=cfg["base"],
                     country=cfg["country"], lang=cfg["lang"], discipline="larp", access="json", robots_ok=True,
                     note=cfg["note"])
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, limit_pages: int | None = None, site: str = SOURCE_ID) -> dict:
    http = http or Http()
    cfg = SITES[site]; base = cfg["base"]
    src = ensure_source(db, site)
    matcher = SlotMatcher(db)
    now = datetime.now(UTC)
    seen = created = updated = matched = 0
    unmatched: dict[str, int] = {}
    page = 1
    while True:
        if limit_pages and page > limit_pages:
            break
        data = http.json(f"{base}/products.json", params={"limit": 250, "page": page})
        products = data.get("products") or []
        if not products:
            break
        for p in products:
            seen += 1
            ext = str(p["id"])
            variants = p.get("variants") or []
            prices = [float(v["price"]) for v in variants if v.get("price")]
            price = int(round(min(prices))) if prices else None
            ptype = p.get("product_type") or ""
            tags = ", ".join(p.get("tags") or [])
            slot_id, conf = matcher.best(p.get("title"), ptype, tags)
            if slot_id:
                matched += 1
            else:
                unmatched[ptype or "(no type)"] = unmatched.get(ptype or "(no type)", 0) + 1
            specs = _specs(p.get("body_html") or "")
            specs["product_type"] = ptype
            specs["vendor"] = p.get("vendor")
            specs["tags"] = tags[:300]     # чтобы `hmb reslot` считал витрину теми же полями, что импорт
            lot = db.scalar(select(Lot).where(Lot.source_id == site, Lot.external_id == ext))
            if lot is None:
                lot = Lot(source_id=site, external_id=ext, direction="offer", kind="catalog",
                          condition="new", country=cfg["country"], lang=cfg["lang"], provenance=f"import:{site}")
                db.add(lot); created += 1
            else:
                updated += 1
            lot.title = p["title"][:500]
            lot.price = price; lot.currency = cfg["currency"]
            lot.slot_id = slot_id; lot.slot_confidence = conf
            lot.source_url = f"{base}/products/{p['handle']}"
            lot.specs = specs
            lot.photos_count = len(p.get("images") or [])
            imgs = p.get("images") or []
            lot.image_url = (imgs[0].get("src") or "")[:800] if imgs and isinstance(imgs[0], dict) else None
            lot.maker = p.get("vendor")
            lot.posted_at = datetime.fromisoformat(p["published_at"]) if p.get("published_at") else None
            lot.status = "active" if any(v.get("available") for v in variants) else "stale"
        db.commit()
        log.info("shopify.page", site=site, page=page, n=len(products))
        page += 1
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "last_seen": seen, "last_matched": matched}
    db.flush()
    top_unmatched = sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]
    return {"seen": seen, "created": created, "updated": updated, "matched": matched,
            "coverage": round(matched / seen, 3) if seen else None, "unmatched_by_type": top_unmatched}
