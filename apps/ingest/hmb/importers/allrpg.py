"""allrpg.info «Склад» — единственная профильная RU-доска с открытой выдачей:
аренда/продажа антуража между ролевиками (Москва/СПб). Маленькая (13
позиций 15.09.2026), без дат, зато с обеими ценами — аренды и продажи.
Разметка: `div.publication` → `publication_header a` (ссылка `/exchange/<id>/`),
`publication_price` («Цена аренды:», «Цена продажи:», регион — `.inverted`),
`publication_annotation`, `publication_tags`. robots.txt: закрыты /people/, /go/.
Пишем в `inbox_items` как объявления; лот с ценой аренды без продажи —
`direction=service`, вид `rent`.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

import structlog
from selectolax.parser import HTMLParser
from sqlalchemy import select

from hmb.http import Http
from hmb.models import InboxItem, Source

log = structlog.get_logger("hmb.import.allrpg")

SOURCE_ID = "allrpg"
BASE = "https://www.allrpg.info"
URL = f"{BASE}/exchange/"


def parse_page(html: str) -> list[dict]:
    tree = HTMLParser(html)
    out: list[dict] = []
    for pub in tree.css("div.publication"):
        head = pub.css_first(".publication_header a")
        if head is None:
            continue
        m = re.search(r"/exchange/(\d+)/", head.attributes.get("href") or "")
        prices = {"rent": None, "sale": None}; region = None
        for pr in pub.css(".publication_price"):
            t = re.sub(r"\s+", " ", pr.text()).strip()
            if "inverted" in (pr.attributes.get("class") or ""):
                region = t; continue
            digits = "".join(re.findall(r"\d+", t.split(":")[-1]))
            if "аренд" in t.lower():
                prices["rent"] = int(digits) if digits else None
            elif "продаж" in t.lower():
                prices["sale"] = int(digits) if digits else None
        ann = pub.css_first(".publication_annotation")
        tags = [a.text().strip() for a in pub.css(".publication_tags a")]
        img = pub.css_first("a.publication_preview_image")
        out.append({
            "external_id": m.group(1) if m else head.text().strip()[:64],
            "title": head.text().strip(),
            "url": head.attributes.get("href"),
            "description": ann.text().strip() if ann is not None else "",
            "price_sale": prices["sale"], "price_rent": prices["rent"],
            "city": region, "tags": tags,
            "photos_count": 1 if img is not None else 0,
        })
    return out


def ensure_source(db) -> Source:
    src = db.get(Source, SOURCE_ID)
    if src is None:
        src = Source(id=SOURCE_ID, kind="board", title="allrpg.info «Склад»", url=URL, country="RU", lang="ru",
                     discipline="larp", access="html", robots_ok=True, note="аренда/продажа антуража между ролевиками; ~13 позиций, без дат")
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, limit_pages: int | None = None) -> dict:
    http = http or Http(delay=2.0)
    src = ensure_source(db)
    now = datetime.now(UTC)
    ads = parse_page(http.get(URL).text)
    seen = created = updated = 0
    for ad in ads:
        seen += 1
        item = db.scalar(select(InboxItem).where(InboxItem.source_id == SOURCE_ID, InboxItem.external_id == ad["external_id"]))
        if item is None:
            item = InboxItem(source_id=SOURCE_ID, external_id=ad["external_id"], raw_text="", provenance="import:allrpg")
            db.add(item); created += 1
        else:
            updated += 1
        item.url = ad["url"]; item.title = ad["title"][:500]
        item.raw_text = f"{ad['title']}\n\n{ad['description']}\n\n{' · '.join(ad['tags'])}".strip()
        price = ad["price_sale"] if ad["price_sale"] is not None else ad["price_rent"]
        item.price_raw = f"{price} ₽" if price is not None else None; item.currency_raw = "RUB" if price is not None else None
        item.city = ad["city"]; item.country = "RU"; item.lang = "ru"
        item.posted_at = None; item.fetched_at = now; item.photos_count = ad["photos_count"]
        item.extraction_meta = {**(item.extraction_meta or {}), "price": price, "price_rent": ad["price_rent"], "price_sale": ad["price_sale"],
                                "tags": ad["tags"], "service_kind": "rent" if ad["price_sale"] is None and ad["price_rent"] is not None else None}
    db.commit()
    src.last_polled_at = now; src.meta = {**(src.meta or {}), "last_seen": seen}
    db.commit()
    return {"seen": seen, "created": created, "updated": updated}
