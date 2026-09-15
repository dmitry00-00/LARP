"""marktplaats.nl — вторая доска б/у (NL), той же группы, что kleinanzeigen.

Страница выдачи — Next.js, весь список лежит в `<script id="__NEXT_DATA__">`
(`props.pageProps.searchRequestAndResponse.listings`, по 30 на страницу,
`/p/N/`): itemId, title, description (обрезано ~200 символов), priceInfo
(priceCents + priceType: FIXED · FAST_BID «bieden» · SEE_DESCRIPTION · FREE …),
location.cityName, date («Vandaag», «Gisteren», «Eergisteren», «2 sep 26»),
imageUrls, attributes[condition ∈ Nieuw · Zo goed als nieuw · Gebruikt], vipUrl.
Разбор JSON, не разметки — ломается реже. Срез 15.09.2026: категория
«Kostuums, Theaterbenodigdheden en LARP» 2 424 объявления; по слову larp 2 713.

Запросы — внутри категории ЛАРП (`/l/<категория>/q/<запрос>/`), иначе «larp»
цепляет игрушки и одежду. Категория смешана с косплеем — слот отсеет.
robots.txt (15.09.2026): `/q/*` и `/l/*` не запрещены (запрещены `/u/*/*/q/*`).
Бюджет запросов неизвестен — пауза 3 с, остановка всего прогона на 403/429.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select

from hmb.http import Http
from hmb.models import InboxItem, Source

log = structlog.get_logger("hmb.import.marktplaats")

SOURCE_ID = "marktplaats"
BASE = "https://www.marktplaats.nl"
CATEGORY = "/l/hobby-en-vrije-tijd/kostuums-theaterbenodigdheden-en-larp"
DEFAULT_QUERIES = ["larp", "larp zwaard", "larp wapen", "larp schild", "larp harnas", "maliënkolder", "gambeson", "larp boog"]
PER_PAGE = 30

_NL_MONTHS = {"jan": 1, "feb": 2, "mrt": 3, "apr": 4, "mei": 5, "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dec": 12}
_COND = {"nieuw": "new", "zo goed als nieuw": "used", "gebruikt": "used"}


def parse_date(text: str, now: datetime) -> datetime | None:
    t = (text or "").strip().lower()
    if t == "vandaag":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if t == "gisteren":
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    if t == "eergisteren":
        return (now - timedelta(days=2)).replace(hour=0, minute=0, second=0, microsecond=0)
    m = re.fullmatch(r"(\d{1,2})\s+([a-z]{3})\.?\s+'?(\d{2,4})", t)
    if m and m.group(2) in _NL_MONTHS:
        y = int(m.group(3)); y = y + 2000 if y < 100 else y
        return datetime(y, _NL_MONTHS[m.group(2)], int(m.group(1)), tzinfo=UTC)
    return None


def parse_page(html: str, now: datetime) -> tuple[list[dict], int]:
    """Объявления страницы и общее число результатов."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return [], 0
    try:
        srr = json.loads(m.group(1))["props"]["pageProps"]["searchRequestAndResponse"]
    except (KeyError, ValueError, TypeError):
        return [], 0
    out: list[dict] = []
    for l in srr.get("listings") or []:
        if not l.get("itemId"):
            continue
        pi = l.get("priceInfo") or {}
        price = None
        if pi.get("priceType") == "FIXED" and pi.get("priceCents"):
            price = int(pi["priceCents"]) // 100
        attrs = {a.get("key"): a.get("value") for a in (l.get("attributes") or []) + (l.get("extendedAttributes") or [])}
        imgs = l.get("imageUrls") or []
        out.append({
            "external_id": l["itemId"],
            "title": l.get("title") or "",
            "description": l.get("description") or "",
            "price": price,
            "price_type": pi.get("priceType"),
            "price_raw": (f"{price} €" if price is not None else (pi.get("priceType") or "")).strip() or None,
            "city": ((l.get("location") or {}).get("cityName")) or None,
            "posted_at": parse_date(l.get("date") or "", now),
            "url": BASE + l["vipUrl"] if l.get("vipUrl") else None,
            "photos_count": len(imgs),
            "photo_urls": ["https:" + u if u.startswith("//") else u for u in imgs][:10],
            "condition": _COND.get((attrs.get("condition") or "").lower()),
            "delivery": attrs.get("delivery"),
            "type": attrs.get("type"),
        })
    return out, int(srr.get("totalResultCount") or 0)


def ensure_source(db) -> Source:
    src = db.get(Source, SOURCE_ID)
    if src is None:
        src = Source(id=SOURCE_ID, kind="board", title="marktplaats.nl", url=BASE + CATEGORY,
                     country="NL", lang="nl", discipline="larp", access="html", robots_ok=True,
                     note="Next.js, список в __NEXT_DATA__; категория «Kostuums, Theaterbenodigdheden en LARP»; по 30 на страницу",
                     meta={"gate": "slot"})   # категория смешана с косплеем: без слота — не лот, а off_topic
        db.add(src); db.flush()
    return src


def run(db, http: Http | None = None, queries: list[str] | None = None, max_pages: int = 3) -> dict:
    http = http or Http(delay=3.0)
    src = ensure_source(db)
    queries = queries or (src.meta or {}).get("queries") or DEFAULT_QUERIES
    now = datetime.now(UTC)
    seen = created = updated = 0
    per_query: dict[str, int] = {}
    start = int((src.meta or {}).get("next_query_idx") or 0) % max(1, len(queries))
    order = queries[start:] + queries[:start]
    for q in order:
        slug = re.sub(r"[^a-z0-9ëéïü]+", "+", q.lower()).strip("+")
        n_q = 0
        for page in range(1, max_pages + 1):
            url = f"{BASE}{CATEGORY}/q/{slug}/" + (f"p/{page}/" if page > 1 else "")
            r = http.get(url)
            if r.status_code in (403, 429):
                log.warning("marktplaats.blocked", url=url, status=r.status_code)
                src.meta = {**(src.meta or {}), "blocked_at": now.isoformat(), "blocked_url": url,
                            "next_query_idx": queries.index(q) if page == 1 else (queries.index(q) + 1) % len(queries)}
                db.commit(); per_query[q] = n_q
                return {"seen": seen, "created": created, "updated": updated, "per_query": per_query, "stopped": f"{r.status_code}"}
            if r.status_code != 200:
                log.warning("marktplaats.status", url=url, status=r.status_code); break
            ads, total = parse_page(r.text, now)
            if not ads:
                break
            for ad in ads:
                seen += 1; n_q += 1
                item = db.scalar(select(InboxItem).where(InboxItem.source_id == SOURCE_ID, InboxItem.external_id == ad["external_id"]))
                if item is None:
                    item = InboxItem(source_id=SOURCE_ID, external_id=ad["external_id"], raw_text="", provenance="import:marktplaats")
                    db.add(item); created += 1
                else:
                    updated += 1
                item.url = ad["url"]; item.title = ad["title"][:500]
                item.raw_text = f"{ad['title']}\n\n{ad['description']}".strip()
                item.price_raw = ad["price_raw"]; item.currency_raw = "EUR" if ad["price"] is not None else None
                item.city = ad["city"]; item.country = "NL"; item.lang = "nl"
                item.posted_at = ad["posted_at"]; item.fetched_at = now
                item.photos_count = ad["photos_count"]; item.photo_urls = ad["photo_urls"]
                meta = dict(item.extraction_meta or {})
                meta.update({"query": q, "price": ad["price"], "price_type": ad["price_type"], "condition": ad["condition"],
                             "delivery": ad["delivery"], "type": ad["type"], "negotiable": ad["price_type"] == "FAST_BID"})
                item.extraction_meta = {k: v for k, v in meta.items() if v is not None}
            db.commit()
            log.info("marktplaats.page", query=q, page=page, n=len(ads), total=total)
            if page * PER_PAGE >= total or len(ads) < PER_PAGE:
                break
        per_query[q] = n_q
        src.meta = {**(src.meta or {}), "next_query_idx": (queries.index(q) + 1) % len(queries)}
        db.commit()
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "queries": queries, "last_seen": seen}
    db.commit()
    return {"seen": seen, "created": created, "updated": updated, "per_query": per_query}
