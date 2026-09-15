"""kleinanzeigen.de — HTML-выдача по запросу, без JS (Astro; JSON-LD у каждого
объявления). robots.txt 15.09.2026: запрещены только выдачи с радиусом
(`/*/k0*r5`…`r200`), чистый `/s-<запрос>/k0` разрешён. Ходим только по нему,
страницы `/seite:N/`, пауза ≥1.5 с.

Что берём: id, URL, заголовок, обрезанное описание из JSON-LD (это архив
`raw_text`; полный текст — на странице объявления, не ходим), цена и «VB»,
PLZ+город, дата, число фото и URL превью (не байты). Что не берём: контакты.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

import structlog
from selectolax.parser import HTMLParser
from sqlalchemy import select

from hmb.http import Http
from hmb.models import InboxItem, Source

log = structlog.get_logger("hmb.import.kleinanzeigen")

SOURCE_ID = "kleinanzeigen"
BASE = "https://www.kleinanzeigen.de"
DEFAULT_QUERIES = ["larp", "larp waffen", "larp rüstung", "polsterwaffe", "larp schwert", "larp schild", "gambeson larp"]

_PLZ_RX = re.compile(r"^\s*(\d{5})\s+(.+?)\s*$")
_PRICE_RX = re.compile(r"([\d.]+)\s*€")
_DATE_RX = re.compile(r"(Heute|Gestern|\d{2}\.\d{2}\.\d{4})(?:,\s*(\d{2}:\d{2}))?")


def ensure_source(db) -> Source:
    src = db.get(Source, SOURCE_ID)
    if src is None:
        src = Source(id=SOURCE_ID, kind="board", title="Kleinanzeigen (DE)", url=BASE, country="DE", lang="de",
                     discipline="larp", access="html", robots_ok=True,
                     note="выдача по запросу без фильтров радиуса; замер 15.09.2026: 3 002 по «larp»",
                     meta={"queries": DEFAULT_QUERIES})
        db.add(src); db.flush()
    return src


def _posted_at(text: str, now: datetime) -> datetime | None:
    m = _DATE_RX.search(text)
    if not m:
        return None
    day, hm = m.group(1), m.group(2)
    if day == "Heute":
        base = now
    elif day == "Gestern":
        base = now - timedelta(days=1)
    else:
        try:
            base = datetime.strptime(day, "%d.%m.%Y").replace(tzinfo=UTC)
        except ValueError:
            return None
    if hm:
        h, mi = hm.split(":")
        base = base.replace(hour=int(h), minute=int(mi), second=0, microsecond=0)
    return base


def parse_listing(html: str, now: datetime | None = None) -> list[dict]:
    """Чистая функция: HTML выдачи → список объявлений. Тестируется без сети."""
    now = now or datetime.now(UTC)
    doc = HTMLParser(html)
    out: list[dict] = []
    for art in doc.css("article[data-adid]"):
        adid = art.attributes.get("data-adid")
        href = art.attributes.get("data-href") or ""
        ld = {}
        for sc in art.css("script[type='application/ld+json']"):
            try:
                cand = json.loads(sc.text())
            except json.JSONDecodeError:
                continue
            if cand.get("@type") == "ImageObject":
                ld = cand
        for n in art.css("svg, script"):
            n.decompose()
        parts = [p.strip() for p in art.text(separator="\n", strip=True).split("\n") if p.strip()]
        city = country_plz = None
        for p in parts:
            m = _PLZ_RX.match(p)
            if m:
                country_plz, city = m.group(1), m.group(2); break
        price_raw = next((p for p in parts if "€" in p), None)
        price = None
        if price_raw:
            m = _PRICE_RX.search(price_raw.replace(".", ""))
            price = int(m.group(1)) if m else None
        date_txt = next((p for p in parts if _DATE_RX.search(p)), "")
        photos = len(art.css("img")) or (1 if ld.get("contentUrl") else 0)
        # число фото — бейдж на превью, отдельным числом в тексте перед PLZ
        try:
            if parts and parts[0].isdigit():
                photos = int(parts[0])
        except ValueError:
            pass
        # без JSON-LD заголовок — первая содержательная строка, но не дата и не цена
        # (поймано 15.09: «Gestern, 15:17» стало заголовком лота)
        title = ld.get("title") or next((p for p in parts if len(p) > 12 and "€" not in p and not _PLZ_RX.match(p) and not _DATE_RX.search(p)), "")
        out.append({
            "external_id": adid, "url": BASE + href if href.startswith("/") else href,
            "title": title, "description": ld.get("description") or "",
            "price": price, "price_raw": price_raw, "negotiable": bool(price_raw and "VB" in price_raw),
            "city": city, "plz": country_plz, "posted_at": _posted_at(date_txt, now),
            "photos_count": photos, "photo_urls": [ld["contentUrl"]] if ld.get("contentUrl") else [],
            "shipping": any("Versand" in p for p in parts),
        })
    return out


def run(db, http: Http | None = None, queries: list[str] | None = None, max_pages: int = 2) -> dict:
    # 4 с между запросами: при 1.5 с сайт ответил 403 на 14-м запросе (15.09).
    http = http or Http(delay=4.0)
    src = ensure_source(db)
    queries = queries or (src.meta or {}).get("queries") or DEFAULT_QUERIES
    now = datetime.now(UTC)
    seen = created = updated = 0
    per_query: dict[str, int] = {}
    # Ротация: бюджет сайта — считанные запросы на окно (15.09: 8, потом 3 до
    # 403), и прогон, всегда начинающий с первого запроса, до последних не
    # доходит никогда. Начинаем с того, на котором остановились.
    start = int((src.meta or {}).get("next_query_idx") or 0) % max(1, len(queries))
    order = queries[start:] + queries[:start]
    for q in order:
        slug = "s-" + re.sub(r"[^a-z0-9äöüß]+", "-", q.lower()).strip("-")
        n_q = 0
        for page in range(1, max_pages + 1):
            # Вторая страница — `/s-seite:2/<запрос>/k0`, НЕ `/s-<запрос>/seite:2/k0`:
            # второй вариант ищет слово «seite:2» и отдаёт 738 чужих объявлений
            # (поймано первым прогоном 15.09 — 75 мусорных строк, стёрты).
            url = f"{BASE}/{slug}/k0" if page == 1 else f"{BASE}/s-seite:{page}/{slug[2:]}/k0"
            r = http.get(url)
            if r.status_code == 403:
                # «IP-Bereich vorübergehend gesperrt» — временный бан диапазона.
                # Дальше идти бессмысленно и вредно: останавливаем ВЕСЬ прогон
                # (recruit: бюджет спрашивать внутри прогона, не только на входе).
                log.warning("kleinanzeigen.blocked", url=url)
                src.meta = {**(src.meta or {}), "blocked_at": now.isoformat(), "blocked_url": url,
                            "next_query_idx": queries.index(q) if page == 1 else (queries.index(q) + 1) % len(queries)}
                db.commit()
                per_query[q] = n_q
                return {"seen": seen, "created": created, "updated": updated, "per_query": per_query, "stopped": "403 IP blocked"}
            if r.status_code != 200:
                log.warning("kleinanzeigen.status", url=url, status=r.status_code); break
            ads = parse_listing(r.text, now)
            if not ads:
                break
            for ad in ads:
                seen += 1; n_q += 1
                item = db.scalar(select(InboxItem).where(InboxItem.source_id == SOURCE_ID, InboxItem.external_id == ad["external_id"]))
                if item is None:
                    item = InboxItem(source_id=SOURCE_ID, external_id=ad["external_id"], raw_text="", provenance="import:kleinanzeigen")
                    db.add(item); created += 1
                else:
                    updated += 1
                item.url = ad["url"]; item.title = ad["title"][:500]
                item.raw_text = f"{ad['title']}\n\n{ad['description']}".strip()
                item.price_raw = ad["price_raw"]; item.currency_raw = "EUR" if ad["price"] is not None else None
                item.city = ad["city"]; item.country = "DE"; item.lang = "de"
                item.posted_at = ad["posted_at"]; item.fetched_at = now
                item.photos_count = ad["photos_count"]; item.photo_urls = ad["photo_urls"]
                meta = dict(item.extraction_meta or {})
                meta.update({"query": q, "negotiable": ad["negotiable"], "shipping": ad["shipping"], "plz": ad["plz"], "price": ad["price"]})
                item.extraction_meta = meta
            db.commit()
            if len(ads) < 25:
                break
        per_query[q] = n_q
        src.meta = {**(src.meta or {}), "next_query_idx": (queries.index(q) + 1) % len(queries)}
        db.commit()
    src.last_polled_at = now
    src.meta = {**(src.meta or {}), "queries": queries, "last_seen": seen}
    db.commit()
    return {"seen": seen, "created": created, "updated": updated, "per_query": per_query}
