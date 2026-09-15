"""Витрины на InSales (RU): «Секира» (sekira.shop, СПб) — реконструкция +
«Мягкое протектированное оружие (ЛАРП)», аренда.

InSales отдаёт JSON без ключа: `/collection/<slug>.json?page=N&per_page=100`
→ {status, count, products[{id, title, url, available, price_min,
first_image.url, variants[{weight (кг), dimensions, quantity}],
characteristics[{title: категория VK}], description}]}. Коллекции — из меню
главной (`/collection/<slug>` + подпись), это и подсказка слота. Товар в
нескольких коллекциях — берём первую по порядку меню.
robots.txt (15.09.2026): закрыты корзина/аккаунт/админка; коллекции открыты.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

import structlog
from selectolax.parser import HTMLParser
from sqlalchemy import select

from hmb.http import Http
from hmb.models import Lot, Source
from hmb.services import service_kind_of
from hmb.slots import SlotMatcher

log = structlog.get_logger("hmb.import.insales")

SITES = {
    "sekira": {"base": "https://sekira.shop", "title": "Секира (sekira.shop)", "city": "Санкт-Петербург", "discipline": "mixed",
               "note": "InSales JSON; реконструкция + ЛАРП + аренда; ~2 240 товаров (15.09.2026)"},
}
SOURCE_ID = "sekira"
PER_PAGE = 100
_SKIP = {"all", "new", "sale", "hits", "frontpage"}


def parse_menu(html: str) -> list[tuple[str, str]]:
    tree = HTMLParser(html)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in tree.css("a[href^='/collection/']"):
        m = re.fullmatch(r"/collection/([^/?#]+)", a.attributes.get("href") or "")
        label = re.sub(r"\s+", " ", a.text()).strip()
        if not m or m.group(1) in seen or m.group(1) in _SKIP or not label or len(label) > 60:
            continue
        seen.add(m.group(1)); out.append((m.group(1), label))
    return out


def _specs(p: dict, label: str) -> dict:
    out: dict = {"category": label}
    v = (p.get("variants") or [{}])[0]
    try:
        w = float(v.get("weight") or 0)
        if w > 0:
            out["weight_g"] = int(round(w * 1000))
    except (TypeError, ValueError):
        pass
    chars = [c.get("title") for c in (p.get("characteristics") or []) if c.get("title")]
    if chars:
        out["vk_category"] = chars[0][:120]
    desc = re.sub(r"<[^>]+>", " ", p.get("description") or "")
    desc = re.sub(r"\s+", " ", desc).strip()
    if desc:
        out["description"] = desc[:400]
        if m := re.search(r"(?:общая\s+)?длина[:\s]*(\d{2,3})\s*см", desc, re.I):
            out["length_cm"] = int(m.group(1))
    if v.get("sku"):
        out["sku"] = str(v["sku"])[:40]
    return out


def ensure_source(db, sid: str) -> Source:
    cfg = SITES[sid]
    src = db.get(Source, sid)
    if src is None:
        src = Source(id=sid, kind="catalog", title=cfg["title"], url=cfg["base"], country="RU", lang="ru",
                     discipline=cfg["discipline"], access="json", robots_ok=True, note=cfg["note"])
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, limit_pages: int | None = None, site: str = SOURCE_ID) -> dict:
    http = http or Http(delay=2.0)
    cfg = SITES[site]; base = cfg["base"]
    src = ensure_source(db, site)
    matcher = SlotMatcher(db)
    now = datetime.now(UTC)
    menu = parse_menu(http.get(base + "/").text)
    seen_ids: set[str] = set()
    seen = created = updated = matched = requests = 0
    unmatched: dict[str, int] = {}
    for slug, label in menu:
        page = 1
        while True:
            if limit_pages and requests >= limit_pages:
                break
            data = http.json(f"{base}/collection/{slug}.json", params={"page": page, "per_page": PER_PAGE}); requests += 1
            products = (data or {}).get("products") or []
            for p in products:
                ext = str(p["id"])
                if ext in seen_ids:
                    continue
                seen_ids.add(ext); seen += 1
                specs = _specs(p, label)
                slot_id, conf = matcher.best(p.get("title"), label, specs.get("vk_category", "") + " · " + specs.get("description", "")[:200])
                if slot_id:
                    matched += 1
                else:
                    unmatched[label] = unmatched.get(label, 0) + 1
                lot = db.scalar(select(Lot).where(Lot.source_id == site, Lot.external_id == ext))
                if lot is None:
                    lot = Lot(source_id=site, external_id=ext, direction="offer", kind="catalog",
                              condition="new", country="RU", lang="ru", provenance=f"import:{site}")
                    db.add(lot); created += 1
                else:
                    updated += 1
                svc = service_kind_of(label, p.get("title"))
                lot.direction = "service" if svc else "offer"
                if svc:
                    specs["service_kind"] = svc
                lot.title = (p.get("title") or "")[:500]
                try:
                    lot.price = int(round(float(p.get("price_min") or 0))) or None
                except (TypeError, ValueError):
                    lot.price = None
                lot.currency = "RUB"
                lot.slot_id = slot_id; lot.slot_confidence = conf
                lot.source_url = base + (p.get("url") or f"/product/{p.get('permalink', '')}")
                lot.specs = specs
                img = p.get("first_image") or {}
                lot.image_url = (img.get("medium_url") or img.get("url") or None)
                lot.photos_count = len(p.get("images") or []) or (1 if lot.image_url else 0)
                lot.maker = cfg["title"].split(" (")[0]; lot.city = cfg["city"]
                lot.status = "active" if p.get("available") else "stale"
            db.commit()
            log.info("insales.page", site=site, collection=slug, page=page, n=len(products))
            if len(products) < PER_PAGE:
                break
            page += 1
        if limit_pages and requests >= limit_pages:
            break
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "last_seen": seen, "last_matched": matched, "collections": len(menu), "requests": requests}
    db.flush()
    top_unmatched = sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]
    return {"collections": len(menu), "requests": requests, "seen": seen, "created": created, "updated": updated,
            "matched": matched, "coverage": round(matched / seen, 3) if seen else None, "unmatched_by_category": top_unmatched}
