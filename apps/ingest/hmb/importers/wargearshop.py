"""WarGear Shop (wargearshop.ru, Москва) — RU-витрина на платформе Storeland:
ЛАРП-раздел (протектированное, дюраль, текстолит), ИСБ/HEMA, доспехи, щиты,
одежда, литьё.

Разметка (срез 15.09.2026): карточки `td.goodsListItem` в листингах
категорий, `?per_page=100` снимает пагинацию (в самом большом разделе 38
товаров); родительские категории карточек не показывают — только дерево.
Список категорий — из sitemap (255 URL `/catalog/…`, 3 151 `/goods/…`).
Наличия в листинге нет — все лоты `active`, это честное «неизвестно».

Что берём (DATA_SOURCES §5): название, раздел и хлебные крошки, цену и
старую цену, ссылку. Что НЕ берём: фото, описание (его в листинге нет).
robots.txt: закрыты /cart, /order, /user, /search, /compare — не ходим.
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

log = structlog.get_logger("hmb.import.wargearshop")

SOURCE_ID = "wargearshop"
BASE = "https://wargearshop.ru"
SITEMAP = f"{BASE}/sitemap"

_NUM_RX = re.compile(r"\d+")


def parse_sitemap(xml: str) -> list[str]:
    """Пути категорий из sitemap, без дублей, в порядке файла."""
    out: list[str] = []
    for loc in re.findall(r"<loc>([^<]+)</loc>", xml):
        m = re.search(r"wargearshop\.ru(/catalog/[^?#]+)", loc)
        if m and m.group(1) != "/catalog" and m.group(1) not in out:
            out.append(m.group(1))
    return out


def parse_listing(html: str) -> tuple[list[dict], str, list[str]]:
    """Карточки, заголовок раздела (h1) и хлебные крошки (без «Главная»/«Каталог»)."""
    tree = HTMLParser(html)
    h1 = tree.css_first("h1")
    title = h1.text().strip() if h1 is not None else ""
    crumbs = [a.text().strip() for a in tree.css("#site-path a")][2:]
    items: list[dict] = []
    for card in tree.css("td.goodsListItem"):
        name = card.css_first("h3.goodsListItemName a")
        if name is None:
            continue
        href = name.attributes.get("href") or ""
        m = re.search(r"/goods/([^/?#]+)", href)
        if not m:
            continue
        price_el = card.css_first("div.goodsListItemPriceNew span.num")
        old_el = card.css_first("div.goodsListItemPriceOld")
        digits = "".join(_NUM_RX.findall(price_el.text())) if price_el is not None else ""
        old_digits = "".join(_NUM_RX.findall(old_el.text())) if old_el is not None else ""
        img = card.css_first("img.goods-image-other")
        items.append({
            "external_id": m.group(1),
            "title": name.text().strip(),
            "url": href if href.startswith("http") else BASE + href,
            "price": int(digits) if digits else None,
            "price_old": int(old_digits) if old_digits else None,
            "has_photo": img is not None,
            "image_url": (img.attributes.get("src") or None) if img is not None else None,
        })
    return items, title, crumbs


def ensure_source(db) -> Source:
    src = db.get(Source, SOURCE_ID)
    if src is None:
        src = Source(id=SOURCE_ID, kind="catalog", title="WarGear Shop (wargearshop.ru)", url=BASE,
                     country="RU", lang="ru", discipline="mixed", access="html", robots_ok=True,
                     note="Москва, Storeland; ЛАРП-раздел + ИСБ/HEMA; листинги категорий ?per_page=100, категории из sitemap")
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, limit_pages: int | None = None) -> dict:
    http = http or Http()
    src = ensure_source(db)
    matcher = SlotMatcher(db)
    now = datetime.now(UTC)
    cats = parse_sitemap(http.get(SITEMAP).text)
    if limit_pages:
        cats = cats[:limit_pages]
    seen_ids: set[str] = set()
    seen = created = updated = matched = 0
    unmatched: dict[str, int] = {}
    empty_cats = 0
    for path in cats:
        items, label, crumbs = parse_listing(http.get(f"{BASE}{path}", params={"per_page": 100}).text)
        if not items:
            empty_cats += 1
            continue
        hint = " · ".join(crumbs[-2:] or [label])
        for it in items:
            ext = it["external_id"]
            if ext in seen_ids:
                continue
            seen_ids.add(ext); seen += 1
            slot_id, conf = matcher.best(it["title"], hint)
            if slot_id:
                matched += 1
            else:
                unmatched[label] = unmatched.get(label, 0) + 1
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
            lot.specs = {"category": label, "path": crumbs, **({"price_old": it["price_old"]} if it["price_old"] else {})}
            lot.photos_count = 1 if it["has_photo"] else 0
            lot.image_url = it["image_url"]
            lot.maker = "WarGear Shop"
            lot.city = "Москва"
            lot.status = "active"
        db.commit()
        log.info("wargearshop.cat", path=path, n=len(items), label=label)
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "last_seen": seen, "last_matched": matched, "categories": len(cats), "empty_categories": empty_cats}
    db.flush()
    top_unmatched = sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]
    return {"categories": len(cats), "empty_categories": empty_cats, "seen": seen, "created": created, "updated": updated,
            "matched": matched, "coverage": round(matched / seen, 3) if seen else None, "unmatched_by_category": top_unmatched}
