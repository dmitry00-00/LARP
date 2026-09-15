"""Витрины на Shopware 6 (DE): Mytholon (mytholon.com) — ЛАРП-одежда, доспехи,
полстерное оружие; ~6 800 URL в sitemap (варианты размеров — отдельными URL).

robots.txt (15.09.2026): **`Disallow: /*?`** — любой запрос с query-string,
то есть и пагинация листинга `?p=2`. Соблюдаем: с каждой категории берём
только ПЕРВУЮ страницу (48 карточек), категории — из sitemap (URL без
числового хвоста). Покрытие каталога поэтому частичное и честно
считается: `seen` против суммы «N Artikel» по категориям в `meta`.
Карточка: `div.product-box[data-product-information]` = {id, name, brand,
price} + ссылка + картинка. По страницам товаров не ходим.
"""
from __future__ import annotations

import gzip
import json
import re
from datetime import UTC, datetime

import structlog
from selectolax.parser import HTMLParser
from sqlalchemy import select

from hmb.http import Http
from hmb.models import Lot, Source
from hmb.slots import SlotMatcher

log = structlog.get_logger("hmb.import.shopware")

SITES = {
    "mytholon": {"base": "https://mytholon.com", "sitemap": "https://www.mytholon.com/sitemap.xml", "title": "Mytholon",
                 "country": "DE", "lang": "de", "currency": "EUR",
                 "note": "Shopware 6; robots: Disallow /*? → только первая страница каждой категории (48), без пагинации"},
}
SOURCE_ID = "mytholon"


def sitemap_urls(http: Http, index_url: str) -> list[str]:
    idx = http.get(index_url).text
    out: list[str] = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", idx):
        r = http.get(loc)
        data = gzip.decompress(r.content).decode("utf-8", "replace") if r.content[:2] == b"\x1f\x8b" else r.text
        out += re.findall(r"<loc>([^<]+)</loc>", data)
    return out


def category_urls(urls: list[str], base: str) -> list[str]:
    """Категории — URL без числового хвоста товара (`/Name/191332M`), кроме корня и служебных."""
    cats: list[str] = []
    for u in urls:
        path = u[len(base):] if u.startswith(base) else None
        if not path or path in ("", "/") or "?" in path:
            continue
        if re.search(r"/[A-Za-z0-9]*\d[A-Za-z0-9]*$", path):     # хвост-артикул → товар
            continue
        if re.match(r"/(account|checkout|widgets|newsletter|blog|magazin|info)", path, re.I):
            continue
        if u not in cats:
            cats.append(u)
    return cats


def parse_listing(html: str) -> tuple[list[dict], str, int | None]:
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    title = h1.text().strip() if h1 is not None else ""
    m = re.search(r"(\d+)\s*(?:Artikel|Produkte)", html)
    total = int(m.group(1)) if m else None
    items: list[dict] = []
    for box in tree.css("div.product-box[data-product-information]"):
        try:
            info = json.loads(box.attributes.get("data-product-information") or "{}")
        except ValueError:
            continue
        link = box.css_first("a.product-name") or box.css_first("a[href]")
        img = box.css_first("img.product-image")
        if not info.get("id") or link is None:
            continue
        price = info.get("price")
        items.append({
            "external_id": info["id"],
            "title": (info.get("name") or link.text()).strip(),
            "brand": info.get("brand"),
            "price": int(round(float(price))) if price not in (None, "") else None,
            "url": link.attributes.get("href"),
            "image_url": (img.attributes.get("src") or img.attributes.get("data-src")) if img is not None else None,
        })
    return items, title, total


def ensure_source(db, sid: str) -> Source:
    cfg = SITES[sid]
    src = db.get(Source, sid)
    if src is None:
        src = Source(id=sid, kind="catalog", title=cfg["title"], url=cfg["base"], country=cfg["country"], lang=cfg["lang"],
                     discipline="larp", access="html", robots_ok=True, note=cfg["note"])
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, limit_pages: int | None = None, site: str = SOURCE_ID) -> dict:
    http = http or Http(delay=2.0)
    cfg = SITES[site]; base = cfg["base"]
    src = ensure_source(db, site)
    matcher = SlotMatcher(db)
    now = datetime.now(UTC)
    cats = category_urls(sitemap_urls(http, cfg["sitemap"]), base)
    if limit_pages:
        cats = cats[:limit_pages]
    seen_ids: set[str] = set()
    seen = created = updated = matched = 0
    declared = 0
    unmatched: dict[str, int] = {}
    for url in cats:
        items, label, total = parse_listing(http.get(url).text)
        declared += total or 0
        for it in items:
            ext = it["external_id"]
            if ext in seen_ids:
                continue
            seen_ids.add(ext); seen += 1
            slot_id, conf = matcher.best(it["title"], label)
            if slot_id:
                matched += 1
            else:
                unmatched[label] = unmatched.get(label, 0) + 1
            lot = db.scalar(select(Lot).where(Lot.source_id == site, Lot.external_id == ext))
            if lot is None:
                lot = Lot(source_id=site, external_id=ext, direction="offer", kind="catalog", condition="new",
                          country=cfg["country"], lang=cfg["lang"], provenance=f"import:{site}")
                db.add(lot); created += 1
            else:
                updated += 1
            lot.title = it["title"][:500]
            lot.price = it["price"]; lot.currency = cfg["currency"]
            lot.slot_id = slot_id; lot.slot_confidence = conf
            lot.source_url = it["url"]
            lot.specs = {"category": label, **({"brand": it["brand"]} if it["brand"] else {})}
            lot.image_url = it["image_url"]; lot.photos_count = 1 if it["image_url"] else 0
            lot.maker = it["brand"] or cfg["title"]
            lot.status = "active"
        db.commit()
        log.info("shopware.cat", site=site, url=url[len(base):], n=len(items), total=total)
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "last_seen": seen, "last_matched": matched, "categories": len(cats),
                "declared_total_by_categories": declared, "note_coverage": "первые страницы категорий; товары в нескольких категориях считаются раз"}
    db.flush()
    top_unmatched = sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]
    return {"categories": len(cats), "seen": seen, "declared_by_categories": declared, "created": created, "updated": updated,
            "matched": matched, "coverage": round(matched / seen, 3) if seen else None, "unmatched_by_category": top_unmatched}
