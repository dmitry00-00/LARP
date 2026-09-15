"""БД → `site/data/feed.json` по контракту страницы (`site/README.md`).

Контракт держит `gen_seed.py`: meta · rates · currencies · slots · archetypes ·
makers · sources · lots. Здесь `meta.synthetic=false`, `lots` — из таблицы,
`slots` — из словаря (с алиасами: страница ищет по ним). Архетипы — пока из
прежнего фида (ИСБ, 8 штук): своих под ЛАРП ещё нет, и это честно
помечено в `meta.archetypesNote`. Поле `photos` — число; `image` — прямая ссылка
на картинку в CDN магазина только у витрин (решение владельца 15.09): копии не
храним, фото частных объявлений не републикуем.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from hmb import config
from hmb.models import Lot, Match, Slot, Source
from kernel.db.fx import get_usd_per


def _country_of(src: Source) -> str:
    return src.country or "—"


RU_SHARE = 0.6   # решение владельца 15.09: RU и DE/NL одновременно, ориентир — RU


def _select_lots(db: Session, max_lots: int) -> list[Lot]:
    """Что попадает в фид при потолке страницы (~5 000 строк, site/README).

    Объявления — все и первыми (их мало, они и есть рынок). Витрины —
    по квоте: RU-магазинам RU_SHARE остатка, остальным — остальное; внутри
    группы источники чередуются по кругу, чтобы ни одна витрина не вытесняла
    другие. До 15.09 сортировка шла по `posted_at`, и 4 500 RU-карточек без
    даты публикации (donjon, wargearshop) в фид не попадали вовсе.
    """
    # объявления и услуги — всегда целиком: их мало, и это две из трёх сторон рынка
    ads = list(db.scalars(select(Lot).where(Lot.status == "active", (Lot.kind == "ad") | (Lot.direction == "service"))
                          .order_by(Lot.posted_at.desc().nullslast(), Lot.id.desc())))
    by_src: dict[str, list[Lot]] = {}
    for l in db.scalars(select(Lot).where(Lot.status == "active", Lot.kind == "catalog", Lot.direction != "service").order_by(Lot.id)):
        by_src.setdefault(l.source_id, []).append(l)
    room = max(0, max_lots - len(ads))
    ru = [v for k, v in by_src.items() if (v[0].country or "") == "RU"]
    other = [v for k, v in by_src.items() if (v[0].country or "") != "RU"]

    def round_robin(groups: list[list[Lot]], limit: int) -> list[Lot]:
        out: list[Lot] = []
        idx = [0] * len(groups)
        while len(out) < limit:
            progressed = False
            for gi, g in enumerate(groups):
                if idx[gi] < len(g) and len(out) < limit:
                    out.append(g[idx[gi]]); idx[gi] += 1; progressed = True
            if not progressed:
                break
        return out

    ru_lots = round_robin(ru, int(room * RU_SHARE)) if other else round_robin(ru, room)
    other_lots = round_robin(other, room - len(ru_lots))
    if len(ru_lots) + len(other_lots) < room:      # у одной группы не хватило — добираем другой
        ru_lots = round_robin(ru, room - len(other_lots))
    return ads + ru_lots + other_lots


def build(db: Session, max_lots: int = 5000) -> dict:
    prev = {}
    if config.SITE_FEED.exists():
        try:
            prev = json.loads(config.SITE_FEED.read_text())
        except json.JSONDecodeError:
            prev = {}
    usd_per = get_usd_per()
    rub_per_usd = 1.0 / usd_per["RUB"]
    rates = {c: round(rub_per_usd * usd_per[c], 4) for c in ("USD", "EUR", "KZT", "UAH", "GBP", "PLN") if c in usd_per}
    rates["RUB"] = 1.0
    slots = []
    for s in db.scalars(select(Slot).order_by(Slot.group, Slot.id)):
        short = re.split(r" / | \(", s.label_ru)[0].upper()
        slots.append({"id": s.id, "label": s.label_ru, "short": short[:14], "group": s.group,
                      "zones": s.zones or [], "layer": s.layer, "measures": s.measures or [],
                      "aliases": [a.alias for a in s.aliases]})
    sources = {src.id: src for src in db.scalars(select(Source))}
    lots = []
    now = datetime.now(UTC)
    match_counts = dict(db.execute(select(Match.want_id, func.count()).where(Match.want_id.isnot(None)).group_by(Match.want_id)).all())
    for l in _select_lots(db, max_lots):
        src = sources.get(l.source_id)
        posted = l.posted_at
        if posted is not None and posted.tzinfo is None:
            posted = posted.replace(tzinfo=UTC)   # SQLite отдаёт naive даже при timezone=True
        age = (now - posted).days if posted else None
        lots.append({
            "id": f"{'o' if l.direction == 'offer' else 's' if l.direction == 'service' else 'w'}-{l.source_id}-{l.external_id}",
            "dir": l.direction,
            # у услуги `kind` на странице — вид услуги (rent · custom · …), у предметов — ad · catalog
            "kind": (l.specs or {}).get("service_kind", "custom") if l.direction == "service" else l.kind,
            "days": (l.specs or {}).get("days"), "scope": [l.slot_id] if l.slot_id else ["*"], "remote": False,
            "slot": l.slot_id, "title": l.title,
            "period": None, "yearFrom": None, "yearTo": None, "region": None,
            "condition": l.condition, "price": l.price_rub if l.price_rub is not None else l.price, "priceNative": l.price,
            "currency": "RUB" if l.price_rub is not None else l.currency, "currencyNative": l.currency,
            "city": l.city, "country": l.country, "measures": {k: v for k, v in (l.specs or {}).items() if k in ("length_cm", "blade_cm", "weight_g", "hardness_shore_a", "chest_cm", "head_cm")},
            "steelMm": None, "weightG": (l.specs or {}).get("weight_g"), "photos": l.photos_count,
            # картинка — прямая ссылка на CDN магазина (решение владельца 15.09), только у витрин
            "image": l.image_url if l.kind == "catalog" else None,
            "maker": l.maker, "source": l.source_id, "sourceRef": (src.title if src else l.source_id), "sourceUrl": l.source_url,
            "postedAt": posted.date().isoformat() if posted else None, "age": age,
            "provenance": l.provenance, "status": l.status, "slotConfidence": l.slot_confidence,
            "matchCount": match_counts.get(l.id) if l.direction == "want" else None,   # матчер Г2.2, таблица matches
        })
    makers_seen = sorted({x["maker"] for x in lots if x.get("maker")})
    makers = [{"id": m, "title": m, "country": None, "city": None, "leadDays": None, "queueOpen": None, "spec": [], "rating": None, "verified": False} for m in makers_seen]
    counts = {
        "offers": sum(1 for x in lots if x["dir"] == "offer"), "wants": sum(1 for x in lots if x["dir"] == "want"),
        "ads": sum(1 for x in lots if x["kind"] == "ad"), "catalog": sum(1 for x in lots if x["kind"] == "catalog"),
        "services": sum(1 for x in lots if x["dir"] == "service"),
        "withSlot": sum(1 for x in lots if x["slot"]),
    }
    feed = {
        "meta": {"generated": now.date().isoformat(), "generator": "apps/ingest/hmb/export_feed.py", "synthetic": False,
                 "note": "Живые данные из БД приёма (SQLite). Витрина магазинов — kind=catalog, объявления — kind=ad. Чужие описания и фото не републикуются: карточка ведёт на оригинал.",
                 "ratesStub": False, "ratesNote": "kernel.db.fx: статический фолбэк до первого фетча; в ₽ через якорь USD.",
                 "archetypesNote": "Архетипы — прежние (ИСБ, 05.09); под ЛАРП ещё не построены.",
                 "counts": counts, "truncatedTo": max_lots, "sourcesPolled": {sid: (s.last_polled_at.isoformat() if s.last_polled_at else None) for sid, s in sources.items()}},
        "rates": rates, "currencies": prev.get("currencies") or ["RUB", "USD", "EUR", "KZT"],
        "slots": slots, "archetypes": prev.get("archetypes") or [],
        "makers": makers,
        "sources": [{"id": s.id, "kind": s.kind, "ref": s.url, "label": s.title, "country": s.country} for s in sources.values()],
        "lots": lots,
    }
    return feed


def write(db: Session) -> dict:
    feed = build(db)
    config.SITE_FEED.write_text(json.dumps(feed, ensure_ascii=False))
    seed_js = config.SITE_FEED.parent.parent / "seed.js"
    seed_js.write_text("window.HMB_SEED = " + json.dumps(feed, ensure_ascii=False) + ";\n")
    return {"lots": len(feed["lots"]), "slots": len(feed["slots"]), "counts": feed["meta"]["counts"], "written": [str(config.SITE_FEED), str(seed_js)]}
