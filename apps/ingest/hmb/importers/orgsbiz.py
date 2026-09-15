"""Витрины на платформе orgs.biz (VK-магазины с зеркалом): «Мечи из Печи»
(Нижнекамск) — фабричное ПУ-оружие для ЛАРП, 13 позиций с полными
спецификациями («Общая длина: 109 см · Клинок 78 см · Вес 0.4 кг ·
Плотность: 30 шор») — первые RU-лоты, у которых есть всё для проверки по
регламенту. Один код на все `*.orgs.biz`: главная страница со schema.org
Product (name · url · description · цена).

robots.txt (15.09.2026): `Allow: /`, `Allow: /product*`.
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

log = structlog.get_logger("hmb.import.orgsbiz")

SITES = {
    "mechiizpechi": {"base": "https://mechiizpechi.orgs.biz", "title": "Мечи из Печи", "city": "Нижнекамск",
                     "note": "фабричное ПУ-оружие для ЛАРП (стекловолоконный сердечник, 30 Шор А); главная = весь каталог"},
}
SOURCE_ID = "mechiizpechi"

_SPEC_RX = {
    "length_cm": re.compile(r"общая\s+длина[:\s]*(\d{2,3})\s*см", re.I),
    "blade_cm": re.compile(r"клинок[:\s]*(\d{2,3})\s*см", re.I),
    "weight_g": re.compile(r"вес[:\s]*(\d(?:[.,]\d{1,2})?)\s*кг", re.I),
    "hardness_shore_a": re.compile(r"(?:плотность|жёсткость|жесткость)[:\s]*(\d{2})\s*шор|(\d{2})\s*шор", re.I),
}


def parse_product(html: str) -> str:
    """Полное описание со страницы товара — на главной оно обрезано «…»."""
    tree = HTMLParser(html)
    el = tree.css_first("[itemprop='description']")
    return el.text().strip() if el is not None else ""


def _specs(desc: str) -> dict:
    out: dict = {}
    for key, rx in _SPEC_RX.items():
        m = rx.search(desc)
        if m:
            val = float(next(g for g in m.groups() if g).replace(",", "."))
            out[key] = int(val * 1000) if key == "weight_g" else int(val)
    if desc:
        out["description"] = desc[:400]
    return out


def parse_home(html: str, base: str) -> list[dict]:
    tree = HTMLParser(html)
    items: list[dict] = []
    for node in tree.css("[itemtype='http://schema.org/Product']"):
        url_el = node.css_first("[itemprop='url']")
        name_el = node.css_first("[itemprop='name']")
        if url_el is None or name_el is None:
            continue
        href = url_el.attributes.get("href") or ""
        m = re.search(r"/product/(\d+)", href)
        if not m:
            continue
        price_el = node.css_first(".product-price")
        digits = "".join(re.findall(r"\d+", price_el.text())) if price_el is not None else ""
        desc_el = node.css_first("[itemprop='description']")
        items.append({
            "external_id": m.group(1),
            "title": re.sub(r"\s+", " ", name_el.text()).strip(),
            "url": base + href if href.startswith("/") else href,
            "price": int(digits) if digits else None,
            "description": desc_el.text().strip() if desc_el is not None else "",
            "has_photo": node.css_first("[itemprop='image']") is not None,
            "image_url": (node.css_first("[itemprop='image']").attributes.get("src") or None) if node.css_first("[itemprop='image']") is not None else None,
        })
    return items


def ensure_source(db, sid: str) -> Source:
    cfg = SITES[sid]
    src = db.get(Source, sid)
    if src is None:
        src = Source(id=sid, kind="catalog", title=f"{cfg['title']} ({cfg['base'].split('//')[1]})", url=cfg["base"],
                     country="RU", lang="ru", discipline="larp", access="html", robots_ok=True, note=cfg["note"])
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, limit_pages: int | None = None, site: str = SOURCE_ID) -> dict:
    http = http or Http()
    cfg = SITES[site]
    src = ensure_source(db, site)
    matcher = SlotMatcher(db)
    now = datetime.now(UTC)
    items = parse_home(http.get(cfg["base"] + "/").text, cfg["base"])
    seen = created = updated = matched = with_specs = 0
    for it in items:
        seen += 1
        if it["description"].endswith("…"):
            it["description"] = parse_product(http.get(it["url"]).text) or it["description"]
        slot_id, conf = matcher.best(it["title"], None, it["description"][:200])
        if slot_id:
            matched += 1
        specs = _specs(it["description"])
        if "length_cm" in specs or "weight_g" in specs:
            with_specs += 1
        lot = db.scalar(select(Lot).where(Lot.source_id == site, Lot.external_id == it["external_id"]))
        if lot is None:
            lot = Lot(source_id=site, external_id=it["external_id"], direction="offer", kind="catalog",
                      condition="new", country="RU", lang="ru", provenance=f"import:{site}")
            db.add(lot); created += 1
        else:
            updated += 1
        lot.title = it["title"][:500]
        lot.price = it["price"]; lot.currency = "RUB"
        lot.slot_id = slot_id; lot.slot_confidence = conf
        lot.source_url = it["url"]
        lot.specs = specs
        lot.photos_count = 1 if it["has_photo"] else 0
        lot.image_url = it["image_url"]    # VK-подписанные URL: могут протухнуть, тогда картинка просто не покажется
        lot.maker = cfg["title"]; lot.city = cfg["city"]
        lot.status = "active"
    db.commit()
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "last_seen": seen, "last_matched": matched}
    db.flush()
    return {"seen": seen, "created": created, "updated": updated, "matched": matched, "with_specs": with_specs,
            "coverage": round(matched / seen, 3) if seen else None}
