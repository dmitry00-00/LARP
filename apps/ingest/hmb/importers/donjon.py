"""Донжон (donjon.ru, Москва) — первая RU-витрина: новое, б/у («Барахолка»), аренда.

HTML-витрина собственной сборки (не Shopify/InSales): карточки в листингах
категорий, 48 на страницу, `?page=N`. В карточке — id товара, название,
цена в копейках (`input.product_price`), наличие («В наличии: N»), короткое
описание во всплывашке. Разбор — по срезу разметки 15.09.2026, см. тест.

Что берём (DATA_SOURCES §5): название, категорию, цену, наличие, ссылку,
короткое описание — в `specs`, фразу про размер как есть («Размер XL» —
ловушка «размер L не существует», хранить сырьём). Что НЕ берём: фото,
контакты продавцов-комитентов (в «Барахолке» они кодами «(ЧП ИВ)» — код
оставляем в названии как пришёл, расшифровки не знаем).

robots.txt (15.09.2026): `User-Agent: *` без Disallow, только Sitemap.
Sitemap: 6 896 товаров, 394 URL категорий; обходим листинги ~60 разделов
меню (родительские «Оружие»/«Доспехи» дублируют детей — пропускаем), а не
6 896 карточек по одной.
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

log = structlog.get_logger("hmb.import.donjon")

SOURCE_ID = "donjon"
BASE = "https://donjon.ru"
PER_PAGE = 48

# Разделы-родители в меню: их листинги — объединение детей. Не обходим.
_PARENTS = {"oruzhie", "dospehi_em", "odezhda-i-obuv", "juvelirnye-ukrashenija-amulety-i-aksessuary",
            "predmety-byta", "soputstvujushie-tovary", "novinki"}
# Барахолка — б/у от комитентов: kind=ad, condition=used.
_USED_CATEGORY = "bu"

_SIZE_RX = re.compile(r"размер[^.;,]{0,40}", re.I)
_LEN_RX = re.compile(r"(?:длин[аы]\s*(?:клинка|общая)?[^\d]{0,12})(\d{2,3})\s*(?:см|cm)", re.I)
_WEIGHT_RX = re.compile(r"(?:вес|масса)[^\d]{0,12}(\d(?:[.,]\d{1,2})?)\s*кг", re.I)


def parse_menu(html: str) -> list[tuple[str, str]]:
    """Разделы меню: [(slug, подпись)], без родителей и без служебных."""
    tree = HTMLParser(html)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for a in tree.css("a[href^='/category/']"):
        href = a.attributes.get("href") or ""
        m = re.fullmatch(r"/category/([^/?#]+)/", href)
        if not m:
            continue
        slug = m.group(1)
        label = (a.text() or "").strip()
        if slug in seen or slug in _PARENTS or not label or len(label) > 60:
            continue
        seen.add(slug)
        out.append((slug, label))
    return out


def parse_listing(html: str) -> tuple[list[dict], int]:
    """Карточки листинга и номер последней страницы."""
    tree = HTMLParser(html)
    items: list[dict] = []
    for card in tree.css("div.good__item"):
        pid = card.css_first("input[name='productID']")
        name = card.css_first("div.name")
        if pid is None or name is None:
            continue
        price_el = card.css_first("input.product_price")
        price = None
        if price_el is not None and (price_el.attributes.get("value") or "").isdigit():
            price = int(price_el.attributes["value"]) // 100
        link = card.css_first("a[href^='/product/']")
        avail_el = card.css_first("div.avail b")
        avail = int(avail_el.text()) if avail_el is not None and avail_el.text().strip().isdigit() else None
        desc_el = card.css_first("div.desc-popup p.text")
        img = card.css_first("div.img img")
        items.append({
            "external_id": pid.attributes.get("value"),
            "title": name.text().strip(),
            "price": price,
            "url": BASE + link.attributes.get("href") if link is not None else None,
            "available": avail,
            "description": desc_el.text().strip() if desc_el is not None else "",
            "has_photo": bool(img is not None and "default.jpg" not in (img.attributes.get("src") or "")),
            "image_url": (BASE + img.attributes["src"]) if img is not None and "default.jpg" not in (img.attributes.get("src") or "") and (img.attributes.get("src") or "").startswith("/") else None,
        })
    pages = [int(x) for x in re.findall(r"\?page=(\d+)", html)]
    return items, (max(pages) if pages else 1)


def _specs(desc: str, category: str) -> dict:
    out: dict = {"category": category}
    if desc:
        out["description"] = desc[:400]
        if m := _SIZE_RX.search(desc):
            out["size_raw"] = m.group(0).strip()
        if m := _LEN_RX.search(desc):
            out["length_cm"] = int(m.group(1))
        if m := _WEIGHT_RX.search(desc):
            out["weight_g"] = int(float(m.group(1).replace(",", ".")) * 1000)
    return out


def ensure_source(db) -> Source:
    src = db.get(Source, SOURCE_ID)
    if src is None:
        src = Source(id=SOURCE_ID, kind="catalog", title="Донжон (donjon.ru)", url=BASE,
                     country="RU", lang="ru", discipline="mixed", access="html", robots_ok=True,
                     note="Москва; новое + Барахолка (б/у комитентов) + аренда; листинги категорий по 48, ?page=N")
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, limit_pages: int | None = None, categories: list[str] | None = None) -> dict:
    http = http or Http()
    src = ensure_source(db)
    matcher = SlotMatcher(db)
    now = datetime.now(UTC)
    first = http.get(f"{BASE}/category/{_USED_CATEGORY}/").text
    menu = parse_menu(first)
    if categories:
        menu = [(s, l) for s, l in menu if s in categories]
    # Барахолка — первой: товар, встреченный в ней, должен стать б/у-объявлением,
    # а не карточкой витрины, если он вдруг числится и в обычном разделе.
    menu.sort(key=lambda sl: sl[0] != _USED_CATEGORY)
    seen_ids: set[str] = set()
    seen = created = updated = matched = 0
    unmatched: dict[str, int] = {}
    requests = 1
    for slug, label in menu:
        page = 1
        while True:
            if limit_pages and requests >= limit_pages:
                break
            html = first if (slug == _USED_CATEGORY and page == 1) else http.get(f"{BASE}/category/{slug}/", params={"page": page} if page > 1 else None).text
            if not (slug == _USED_CATEGORY and page == 1):
                requests += 1
            items, last = parse_listing(html)
            for it in items:
                ext = it["external_id"]
                if not ext or ext in seen_ids:
                    continue        # товар в нескольких разделах — берём первый (более специфичный по порядку меню)
                seen_ids.add(ext); seen += 1
                is_used = slug == _USED_CATEGORY
                slot_id, conf = matcher.best(it["title"], label, it["description"][:200])
                if slot_id:
                    matched += 1
                else:
                    unmatched[label] = unmatched.get(label, 0) + 1
                lot = db.scalar(select(Lot).where(Lot.source_id == SOURCE_ID, Lot.external_id == ext))
                if lot is None:
                    lot = Lot(source_id=SOURCE_ID, external_id=ext, direction="offer",
                              kind="ad" if is_used else "catalog", country="RU", lang="ru",
                              provenance=f"import:{SOURCE_ID}", posted_at=None)
                    db.add(lot); created += 1
                else:
                    updated += 1
                lot.title = it["title"][:500]
                lot.price = it["price"]; lot.currency = "RUB"
                lot.condition = "used" if is_used else "new"
                lot.slot_id = slot_id; lot.slot_confidence = conf
                lot.source_url = it["url"]
                lot.specs = _specs(it["description"], label)
                lot.photos_count = 1 if it["has_photo"] else 0
                lot.image_url = None if is_used else it["image_url"]   # б/у комитентов — без фото, только ссылка
                lot.maker = None if is_used else "Донжон"
                lot.city = "Москва"
                lot.status = "active" if (it["available"] or 0) > 0 else "stale"
            db.commit()
            log.info("donjon.page", category=slug, page=page, n=len(items), last=last)
            if page >= last:
                break
            page += 1
        if limit_pages and requests >= limit_pages:
            break
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "last_seen": seen, "last_matched": matched, "menu_sections": len(menu), "requests": requests}
    db.flush()
    top_unmatched = sorted(unmatched.items(), key=lambda kv: -kv[1])[:25]
    return {"sections": len(menu), "requests": requests, "seen": seen, "created": created, "updated": updated,
            "matched": matched, "coverage": round(matched / seen, 3) if seen else None, "unmatched_by_category": top_unmatched}
