"""Объявление → лот. Без LLM: правила + словарь слотов.

Порядок как в recruit: гейты ПОМЕЧАЮТ, не удаляют (`status='skipped'` +
`skip_reason`), отсев обратим из `raw_text`. Три решения на объявление:

1. направление — `want` по маркерам «ищу / куплю / suche / gezocht / wtb»,
   иначе `offer`;
2. тип — `digest`, если в тексте несколько цен/позиций списком (прайс
   мастерской — не 20 лотов и не один лот, урок recruit 14.09);
3. слот — `SlotMatcher.best(title, description)`; нет слота → лот всё
   равно создаётся (виден в реестре), `slot_id=NULL`, `needs_review`.

Состояние: `used` по маркерам б/у, `new` по «neu/new/новый» без «gebraucht»,
иначе `unknown` — неизвестность отдельно от «плохое» (DOMAIN_MODEL §2.3).
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from hmb.models import InboxItem, Lot, Source
from hmb.slots import SlotMatcher
from kernel.db.fx import to_rub_usd
from kernel.skills.salary import parse_salary

_WANT = re.compile(r"\b(ищу|куплю|купим|нужен|нужна|нужны|в поиске|suche|gesucht|kaufe|gezocht|zoek|wtb|looking for|wanted|szukam)\b", re.I)
_USED = re.compile(r"\b(б/у|бу|б\.у\.|used|second[- ]hand|gebraucht|gebrauchsspuren|gebrauchter|gebrauchte|gebruikt|tweedehands|getragen|benutzt|wenig genutzt|bespielt|pre-owned|worn)\b", re.I)
_NEW = re.compile(r"\b(новый|новая|новое|new|neu|neuwertig|ungetragen|nieuw|ovp|unbenutzt)\b", re.I)
_DIGEST_PRICE = re.compile(r"\d+\s*(?:€|eur|₽|руб|тг|₸|грн|zł|\$)", re.I)
# Маркеры сделки — для лент «всего подряд» (TG-каналы игр): пост без слота и
# без такого маркера — не про снаряжение → `off_topic` (помечаем, не удаляем).
# Только ГЛАГОЛЫ сделки: «цена»/«руб» есть у любого анонса (взнос игры), и 9 из
# 9 первых «лотов» из каналов оказались анонсами с ценой взноса (15.09).
_SALE = re.compile(r"\b(продам|продаю|продаётся|продается|продажа|куплю|отдам|обменяю|сдам в аренду|сдаю|verkaufe|zu verkaufen|suche|tausche|te koop)\b", re.I)
_GATED_KINDS = ("tg", "vk", "calendar")

_NEGATION = re.compile(r"\b(nicht|kein|keine|не|no|not)\s+(?:mehr\s+)?(gebraucht|used|б/у|new|neu)\b", re.I)


def direction_of(text: str) -> str:
    head = text[:200]
    return "want" if _WANT.search(head) else "offer"


def condition_of(text: str) -> str:
    t = _NEGATION.sub(" ", text)
    if _USED.search(t):
        return "used"
    if _NEW.search(t):
        return "new"
    return "unknown"


def is_digest(text: str) -> bool:
    return len(_DIGEST_PRICE.findall(text)) >= 4 or text.count("\n-") + text.count("\n•") + text.count("\n*") >= 5


def classify_pending(db: Session, limit: int = 5000) -> dict:
    matcher = SlotMatcher(db)
    items = db.scalars(select(InboxItem).where(InboxItem.status == "raw").limit(limit)).all()
    gated = {sid for sid, kind in db.execute(select(Source.id, Source.kind)) if kind in _GATED_KINDS}
    # Доски со смешанной категорией (marktplaats: ЛАРП + косплей + фурсьюты + детские
    # коляски по слову «larp» в названии категории): без слота — не наш предмет.
    slot_gated = {sid for sid, meta in db.execute(select(Source.id, Source.meta)) if (meta or {}).get("gate") == "slot"}
    n = created = updated = skipped = no_slot = want = off_topic = 0
    for it in items:
        n += 1
        text = it.raw_text or ""
        if len(text.strip()) < 8:
            it.status = "skipped"; it.skip_reason = "empty"; skipped += 1; continue
        d = direction_of(text)
        slot_id, conf = matcher.best(it.title, None, text)
        if it.source_id in gated and not (_SALE.search(text[:300]) and matcher.match((it.title or "") + " " + text[:300])):
            # лента игры: маркер сделки и слот — оба в НАЧАЛЕ поста, не где-то в теле
            # лента игры: анонс, отчёт, оргвопросы — не лот. Слот ∧ маркер сделки — оба.
            it.status = "skipped"; it.skip_reason = "off_topic"; it.classified_as = "other"; off_topic += 1
            it.extraction_meta = {**(it.extraction_meta or {}), "slot_id": slot_id}
            continue
        if it.source_id in slot_gated and not slot_id:
            it.status = "skipped"; it.skip_reason = "off_topic"; it.classified_as = "other"; off_topic += 1
            it.extraction_meta = {**(it.extraction_meta or {}), "slot_id": None, "gate": "slot"}
            continue
        if is_digest(text):
            it.status = "classified"; it.classified_as = "digest"; skipped += 1; continue
        want += d == "want"
        if not slot_id:
            no_slot += 1
        price = None; cur = it.currency_raw
        meta = it.extraction_meta or {}
        if meta.get("price") not in (None, ""):
            try:
                price = int(float(meta["price"]))
            except (TypeError, ValueError):
                price = None
        elif it.price_raw:
            ps = parse_salary(it.price_raw)
            price = ps.low or ps.high; cur = cur or ps.currency
        rub, usd = to_rub_usd(price, cur) if price else (None, None)
        lot = db.scalar(select(Lot).where(Lot.source_id == it.source_id, Lot.external_id == it.external_id))
        if lot is None:
            lot = Lot(source_id=it.source_id, external_id=it.external_id, direction=d, kind="ad", title=(it.title or text[:120])[:500],
                      provenance=it.provenance); db.add(lot); created += 1
        else:
            updated += 1
        # доска аренды (allrpg «Склад»): позиция только с ценой аренды — услуга `rent`
        if meta.get("service_kind"):
            d = "service"
        lot.direction = d; lot.title = (it.title or text[:120])[:500]
        lot.price = price; lot.currency = cur; lot.price_rub = rub; lot.price_usd = usd
        # Структурное состояние от площадки (marktplaats: «Nieuw / Zo goed als nieuw /
        # Gebruikt») надёжнее регекса по тексту — берём его, если импортёр положил.
        lot.condition = meta.get("condition") or condition_of(text)
        lot.city = it.city; lot.country = it.country; lot.lang = it.lang
        lot.source_url = it.url; lot.inbox_item_id = it.id; lot.posted_at = it.posted_at
        lot.slot_id = slot_id; lot.slot_confidence = conf; lot.photos_count = it.photos_count
        lot.specs = {k: v for k, v in {"negotiable": meta.get("negotiable"), "shipping": meta.get("shipping"),
                                       "service_kind": meta.get("service_kind"), "price_rent": meta.get("price_rent")}.items() if v is not None}
        lot.status = "active"
        it.status = "extracted"; it.classified_as = d
        it.extraction_meta = {**meta, "slot_id": slot_id, "slot_confidence": conf, "needs_review": slot_id is None,
                              "classified_at": datetime.now(UTC).isoformat()}
    db.flush()
    return {"seen": n, "lots_created": created, "lots_updated": updated, "skipped_or_digest": skipped,
            "off_topic": off_topic, "want": want, "no_slot": no_slot,
            "no_slot_share": round(no_slot / max(1, n - skipped - off_topic), 3)}
