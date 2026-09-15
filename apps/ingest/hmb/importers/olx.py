"""OLX (kz / ua) — открытый JSON `api/v1/offers/?query=` (замер сборщика
15.09.2026 через WebFetch: без токена, поля id/url/title/created_time/
last_refresh_time/description/params/location/photos).

⚠ НЕ ПРОВЕРЕН ПРОГОНОМ: с сетевого выхода этой машины OLX отдаёт 403 на весь
сайт (CloudFront, узел CPH), независимо от User-Agent — гео-блок, не robots.
Запускать из Казахстана/Украины (база проекта — KZ). Первый прогон — с
`--max-pages 1` и сверкой полей с этим модулем.

Ключи: на olx.kz «ларп» мёртв (2 нерелевантных); работают «доспех»,
«кольчуга», казахские «сауыт», «берен», «кіреуке». На olx.ua «ларп»/«larp»
работают.
"""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from hmb.http import Http
from hmb.models import InboxItem, Source

log = structlog.get_logger("hmb.import.olx")

SITES = {
    "olx_kz": {"base": "https://www.olx.kz", "country": "KZ", "lang": "ru", "currency": "KZT",
               "queries": ["доспех", "кольчуга", "сауыт", "берен", "кіреуке", "меч тренировочный", "щит средневековый"]},
    "olx_ua": {"base": "https://www.olx.ua", "country": "UA", "lang": "uk", "currency": "UAH",
               "queries": ["ларп", "larp", "обладунки", "кольчуга", "меч латексний"]},
}


def ensure_source(db, sid: str) -> Source:
    cfg = SITES[sid]
    src = db.get(Source, sid)
    if src is None:
        src = Source(id=sid, kind="board", title=f"OLX ({cfg['country']})", url=cfg["base"], country=cfg["country"],
                     lang=cfg["lang"], discipline="mixed", access="json", robots_ok=True,
                     note="api/v1/offers без токена; 403 с EU-egress (CloudFront) — запускать из KZ/UA",
                     meta={"queries": cfg["queries"]})
        db.add(src); db.flush()
    return src


def _param(offer: dict, key: str):
    for p in offer.get("params") or []:
        if p.get("key") == key:
            return p.get("value") or {}
    return {}


def _ts(s: str | None):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def run(db, http: Http | None = None, sites: list[str] | None = None, max_pages: int = 2) -> dict:
    http = http or Http()
    now = datetime.now(UTC)
    result: dict = {}
    for sid in sites or list(SITES):
        cfg = SITES[sid]; src = ensure_source(db, sid)
        seen = created = 0
        for q in (src.meta or {}).get("queries") or cfg["queries"]:
            for page in range(1, max_pages + 1):
                r = http.get(f"{cfg['base']}/api/v1/offers/", params={"query": q, "limit": 40, "offset": (page - 1) * 40},
                             headers={"Accept": "application/json"})
                if r.status_code != 200:
                    log.warning("olx.status", site=sid, q=q, status=r.status_code); break
                offers = (r.json() or {}).get("data") or []
                if not offers:
                    break
                for o in offers:
                    seen += 1
                    ext = str(o["id"])
                    item = db.scalar(select(InboxItem).where(InboxItem.source_id == sid, InboxItem.external_id == ext))
                    if item is None:
                        item = InboxItem(source_id=sid, external_id=ext, raw_text="", provenance=f"import:{sid}")
                        db.add(item); created += 1
                    price = _param(o, "price")
                    loc = o.get("location") or {}
                    item.url = o.get("url"); item.title = (o.get("title") or "")[:500]
                    item.raw_text = f"{o.get('title') or ''}\n\n{o.get('description') or ''}".strip()
                    item.price_raw = str(price.get("value")) if price.get("value") is not None else None
                    item.currency_raw = price.get("currency") or cfg["currency"]
                    item.city = (loc.get("city") or {}).get("name"); item.country = cfg["country"]; item.lang = cfg["lang"]
                    item.posted_at = _ts(o.get("last_refresh_time") or o.get("created_time")); item.fetched_at = now
                    photos = o.get("photos") or []
                    item.photos_count = len(photos); item.photo_urls = [p.get("link") for p in photos[:3] if p.get("link")]
                    item.extraction_meta = {**(item.extraction_meta or {}), "query": q, "price": price.get("value"),
                                            "negotiable": bool(price.get("negotiable")), "region": (loc.get("region") or {}).get("name")}
                db.commit()
                if len(offers) < 40:
                    break
        src.last_polled_at = now; src.meta = {**(src.meta or {}), "last_seen": seen}; db.commit()
        result[sid] = {"seen": seen, "created": created}
    return result
