"""Витрины на OXID eShop (DE): Andracor (andracor.com, Берлин, группа maskworld)
— ЛАРП-одежда, доспехи, оружие, грим. Категории — из меню главной
(`/de/c/produktkategorien/...`), листинг — `div.products a.product`
(название, подпись подраздела в `.product-brand`, цена, картинка), по 48,
пагинация `?pgNr=N` (робот не запрещает query). robots.txt (15.09.2026):
закрыты /admin, /core, newsletter — каталог открыт.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

import structlog
from selectolax.parser import HTMLParser
from sqlalchemy import select

from hmb.http import Http
from hmb.models import Lot, Source
from hmb.slots import SlotMatcher

log = structlog.get_logger("hmb.import.oxid")

SITES = {
    "andracor": {"base": "https://www.andracor.com", "cat_prefix": "/de/c/produktkategorien/", "title": "Andracor",
                 "country": "DE", "lang": "de", "currency": "EUR", "note": "OXID eShop; листинги по 48, ?pgNr=N"},
}
SOURCE_ID = "andracor"


def parse_menu(html: str, base: str, prefix: str) -> list[str]:
    out: list[str] = []
    for u in re.findall(r'href="(' + re.escape(base) + re.escape(prefix) + r'[^"#?]+)"', html):
        if u not in out:
            out.append(u)
    return out


def parse_listing(html: str) -> tuple[list[dict], str, int]:
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    title = re.sub(r"\s+", " ", h1.text()).strip() if h1 is not None else ""
    items: list[dict] = []
    for a in tree.css("div.products a.product"):
        name = a.css_first(".product-name"); price = a.css_first(".price"); img = a.css_first("img"); sub = a.css_first(".product-brand")
        href = a.attributes.get("href") or ""
        m = re.search(r"--(\d+)$", href)
        if name is None or not href:
            continue
        digits = re.sub(r"[^\d,]", "", price.text()) if price is not None else ""
        items.append({
            "external_id": m.group(1) if m else href.rsplit("/", 1)[-1],
            "title": re.sub(r"\s+", " ", name.text()).strip(),
            "sub": re.sub(r"\s+", " ", sub.text()).strip() if sub is not None else "",
            "price": int(round(float(digits.replace(",", ".")))) if digits else None,
            "url": href,
            "image_url": img.attributes.get("src") if img is not None else None,
        })
    pages = [int(x) for x in re.findall(r"pgNr=(\d+)", html)]
    return items, title, (max(pages) if pages else 0)


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
    cats = parse_menu(http.get(base + "/").text, base, cfg["cat_prefix"])
    seen_ids: set[str] = set()
    seen = created = updated = matched = requests = 0
    unmatched: dict[str, int] = {}
    for url in cats:
        page = 0
        while True:
            if limit_pages and requests >= limit_pages:
                break
            items, label, last = parse_listing(http.get(url, params={"pgNr": page} if page else None).text); requests += 1
            for it in items:
                ext = it["external_id"]
                if ext in seen_ids:
                    continue
                seen_ids.add(ext); seen += 1
                slot_id, conf = matcher.best(it["title"], (it["sub"] + " · " + label).strip(" ·"))
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
                lot.specs = {"category": label, **({"sub": it["sub"]} if it["sub"] else {})}
                lot.image_url = it["image_url"]; lot.photos_count = 1 if it["image_url"] else 0
                lot.maker = cfg["title"]
                lot.status = "active"
            db.commit()
            log.info("oxid.page", site=site, url=url[len(base):], page=page, n=len(items), last=last)
            if page >= last or not items:
                break
            page += 1
        if limit_pages and requests >= limit_pages:
            break
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "last_seen": seen, "last_matched": matched, "categories": len(cats), "requests": requests}
    db.flush()
    top_unmatched = sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]
    return {"categories": len(cats), "requests": requests, "seen": seen, "created": created, "updated": updated,
            "matched": matched, "coverage": round(matched / seen, 3) if seen else None, "unmatched_by_category": top_unmatched}
