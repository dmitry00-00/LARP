"""«Кузница» bsmith.ru — RU-мастерская полного цикла (ИСБ, HEMA, ЛАРП,
реконструкция): Drupal + Ubercart. Категории — из меню главной (~180
ссылок `/catalog/<slug>`); родительские страницы показывают плитки
подкатегорий (`article.taxonomy-term`), листовые — карточки товаров
(`article.card`: артикул, название, «2,200 руб.», картинка в `data-echo`).
Сроки изготовления живут на страницах товаров и в общем тексте («Мечи
стандартные: 2–8 недель») — по одному товару не ходим (см. ниже), срок —
в `note` источника, за полем `Maker.lead_time_days` — отдельный проход.

robots.txt (15.09.2026): `User-agent: *` → **Crawl-delay: 10**. Соблюдаем:
10 с между запросами, поэтому обход ~180 страниц — полчаса, и по 3 000
карточек товаров поодиночке не ходим (8 часов).
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

log = structlog.get_logger("hmb.import.bsmith")

SOURCE_ID = "bsmith"
BASE = "https://bsmith.ru"
CRAWL_DELAY = 10.0


def parse_menu(html: str) -> list[tuple[str, str]]:
    tree = HTMLParser(html)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in tree.css("a[href^='/catalog/']"):
        href = a.attributes.get("href") or ""
        m = re.fullmatch(r"/catalog/([^/?#]+)", href)
        label = re.sub(r"\s+", " ", a.text()).strip()
        if not m or m.group(1) in seen or not label or len(label) > 60:
            continue
        seen.add(m.group(1)); out.append((m.group(1), label))
    return out


def parse_listing(html: str) -> tuple[list[dict], str, str | None]:
    """Карточки товаров, заголовок страницы, ссылка на следующую страницу."""
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    title = h1.text().strip() if h1 is not None else ""
    items: list[dict] = []
    for card in tree.css("article.card"):
        link = card.css_first("a[href^='/catalog/']")
        name = card.css_first(".card-title")
        if link is None or name is None:
            continue
        nid = (card.attributes.get("id") or "").replace("node-", "")
        price_el = card.css_first(".card-text .h5, .card-text p")
        digits = "".join(re.findall(r"\d+", price_el.text())) if price_el is not None and "руб" in price_el.text() else ""
        sku = card.css_first(".badge")
        img = card.css_first("img[data-echo]")
        items.append({
            "external_id": nid or link.attributes["href"],
            "title": name.text().strip(),
            "url": BASE + link.attributes["href"],
            "price": int(digits) if digits else None,
            "sku": re.sub(r"\D", "", sku.text()) if sku is not None else None,
            "image_url": img.attributes.get("data-echo") if img is not None else None,
        })
    nxt = tree.css_first("li.pager-next a, a[rel='next']")
    return items, title, (BASE + nxt.attributes["href"]) if nxt is not None and nxt.attributes.get("href", "").startswith("/") else None


def ensure_source(db) -> Source:
    src = db.get(Source, SOURCE_ID)
    if src is None:
        src = Source(id=SOURCE_ID, kind="catalog", title="Кузница (bsmith.ru)", url=BASE,
                     country="RU", lang="ru", discipline="mixed", access="html", robots_ok=True,
                     note="Drupal/Ubercart; Crawl-delay 10; мастерская на заказ: сроки по типам (мечи 2–8 нед., шлемы 6–10) — в общем тексте сайта, не в карточках")
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, limit_pages: int | None = None) -> dict:
    http = http or Http(delay=CRAWL_DELAY)
    src = ensure_source(db)
    matcher = SlotMatcher(db)
    now = datetime.now(UTC)
    menu = parse_menu(http.get(BASE + "/").text)
    if limit_pages:
        menu = menu[:limit_pages]
    seen_ids: set[str] = set()
    seen = created = updated = matched = requests = 0
    unmatched: dict[str, int] = {}
    for slug, label in menu:
        url: str | None = f"{BASE}/catalog/{slug}"
        pages = 0
        while url and pages < 5:
            items, title, url = parse_listing(http.get(url).text); requests += 1; pages += 1
            for it in items:
                ext = it["external_id"]
                if ext in seen_ids:
                    continue
                seen_ids.add(ext); seen += 1
                slot_id, conf = matcher.best(it["title"], title or label)
                if slot_id:
                    matched += 1
                else:
                    unmatched[title or label] = unmatched.get(title or label, 0) + 1
                lot = db.scalar(select(Lot).where(Lot.source_id == SOURCE_ID, Lot.external_id == ext))
                if lot is None:
                    lot = Lot(source_id=SOURCE_ID, external_id=ext, direction="offer", kind="catalog",
                              condition="new", country="RU", lang="ru", provenance=f"import:{SOURCE_ID}")
                    db.add(lot); created += 1
                else:
                    updated += 1
                lot.title = it["title"][:500]
                lot.price = it["price"]; lot.currency = "RUB"
                lot.slot_id = slot_id; lot.slot_confidence = conf
                lot.source_url = it["url"]
                lot.specs = {"category": title or label, **({"sku": it["sku"]} if it["sku"] else {}), "made_to_order": True}
                lot.photos_count = 1 if it["image_url"] else 0
                lot.image_url = it["image_url"]
                lot.maker = "Кузница (bsmith.ru)"
                lot.status = "active"
            db.commit()
            log.info("bsmith.page", category=slug, n=len(items), more=bool(url))
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "last_seen": seen, "last_matched": matched, "menu_sections": len(menu), "requests": requests}
    db.flush()
    top_unmatched = sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]
    return {"sections": len(menu), "requests": requests, "seen": seen, "created": created, "updated": updated,
            "matched": matched, "coverage": round(matched / seen, 3) if seen else None, "unmatched_by_category": top_unmatched}
