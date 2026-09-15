"""Матчер спроса (ROADMAP Г2.2): запрос → предложения, с объяснением.

Запрос — `WantSpec`: слот(ы), потолок цены в ₽, страны, состояние, размеры
(`need`: голова/грудь… или длина/масса предмета), слова. Источники запроса:
лот `direction=want` (спека извлекается из текста: слот — словарём, бюджет —
`parse_salary` из ядра, регион — страна/город лота) или подписка страницы
(`snapshot` фильтров, тот же JSON, что `S.f` в app.js).

Оценка 0..1 — сумма весов по выполненным условиям; слот обязателен (без него
кандидат не рассматривается — «лот без слота для матчера не существует»).
Веса — не калибровка, а порядок важности: бюджет > регион > состояние >
размер > слова. Жёстких условия два: слот и бюджет (превышение сверх +15 %
выбывает); регион — мягкое (доставка бывает). Калибровать будет не на чем, пока запросов три.

Как в recruit: три исхода на условие — `ok` / `gap` / `unknown`; `unknown`
(в объявлении нет размера) не штрафуется, но и не засчитывается.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from hmb.models import InboxItem, Lot, Match
from hmb.slots import SlotMatcher
from kernel.db.fx import to_rub_usd
from kernel.skills.salary import parse_salary

WEIGHTS = {"slot": 0.40, "budget": 0.25, "country": 0.15, "condition": 0.08, "size": 0.07, "words": 0.05}
_TOL = 1.15   # бюджет: до +15 % — «почти в бюджете», половина веса
_SIZE_TOL_CM = 4
_WORD_RX = re.compile(r"[a-zа-яё]{4,}", re.I)
_STOP = {"продам", "куплю", "ищу", "нужен", "нужна", "suche", "gezocht", "larp", "ларп", "mittelalter", "verkaufe", "neu", "gebraucht"}


@dataclass
class WantSpec:
    slots: list[str] = field(default_factory=list)
    max_price_rub: int | None = None
    countries: list[str] = field(default_factory=list)
    condition: str | None = None          # new · used · None = любое
    need: dict[str, tuple[float, float]] = field(default_factory=dict)   # metric → (lo, hi)
    words: set[str] = field(default_factory=set)
    direction: str = "offer"              # что ищем: offer или service (аренда)


def spec_from_want(db: Session, want: Lot, matcher: SlotMatcher | None = None) -> WantSpec:
    matcher = matcher or SlotMatcher(db)
    item = db.get(InboxItem, want.inbox_item_id) if want.inbox_item_id else None
    text = f"{want.title}\n{item.raw_text if item else ''}"
    slots = [want.slot_id] if want.slot_id else matcher.match(text)[:3]
    max_rub = want.price_rub
    if max_rub is None:
        ps = parse_salary(text, free_text=True)
        cap = ps.high or ps.low
        if cap:
            max_rub, _ = to_rub_usd(cap, ps.currency or want.currency or "RUB")
    need: dict[str, tuple[float, float]] = {}
    for k, v in ((want.specs or {}).get("need") or {}).items():
        if isinstance(v, (list, tuple)) and len(v) == 2:
            need[k] = (float(v[0]), float(v[1]))
        elif isinstance(v, (int, float)):
            need[k] = (float(v) - _SIZE_TOL_CM, float(v) + _SIZE_TOL_CM)
    words = {w.lower() for w in _WORD_RX.findall(want.title or "")} - _STOP
    svc = (want.specs or {}).get("service_kind")
    return WantSpec(slots=[s for s in slots if s], max_price_rub=max_rub, countries=[want.country] if want.country else [],
                    condition=None, need=need, words=words, direction="service" if svc else "offer")


def spec_from_filters(f: dict) -> WantSpec:
    """Подписка страницы: `{slot, country, cond, priceMax, q, need}` — ключи `S.f` app.js."""
    need = {}
    for k, v in (f.get("need") or {}).items():
        need[k] = (float(v) - _SIZE_TOL_CM, float(v) + _SIZE_TOL_CM) if isinstance(v, (int, float)) else (float(v[0]), float(v[1]))
    return WantSpec(slots=[f["slot"]] if f.get("slot") else [], max_price_rub=f.get("priceMax"),
                    countries=[f["country"]] if f.get("country") else [],
                    condition=f.get("cond") or None, need=need,
                    words={w.lower() for w in _WORD_RX.findall(f.get("q") or "")} - _STOP)


def _price_rub(lot: Lot) -> int | None:
    if lot.price_rub is not None:
        return lot.price_rub
    if lot.price is None:
        return None
    rub, _ = to_rub_usd(lot.price, lot.currency or "RUB")
    return rub


def score(spec: WantSpec, offer: Lot) -> tuple[float, dict]:
    reasons: dict = {}
    if spec.slots and offer.slot_id not in spec.slots:
        return 0.0, {"slot": "gap"}
    if not offer.slot_id:
        return 0.0, {"slot": "unknown"}
    total = WEIGHTS["slot"]; reasons["slot"] = "ok"

    price = _price_rub(offer)
    if spec.max_price_rub is None:
        reasons["budget"] = "unknown"
    elif price is None:
        reasons["budget"] = "unknown"
    elif price <= spec.max_price_rub:
        total += WEIGHTS["budget"]; reasons["budget"] = "ok"
    elif price <= spec.max_price_rub * _TOL:
        total += WEIGHTS["budget"] / 2; reasons["budget"] = "near"
    else:
        # бюджет назван и превышен больше чем на допуск — не совпадение, а раздражение
        return 0.0, {**reasons, "budget": "gap"}

    if not spec.countries:
        total += WEIGHTS["country"] / 2; reasons["country"] = "any"
    elif offer.country in spec.countries:
        total += WEIGHTS["country"]; reasons["country"] = "ok"
    else:
        reasons["country"] = "gap"

    if spec.condition is None or spec.condition == "any":
        total += WEIGHTS["condition"] / 2; reasons["condition"] = "any"
    elif offer.condition == spec.condition:
        total += WEIGHTS["condition"]; reasons["condition"] = "ok"
    elif offer.condition == "unknown":
        reasons["condition"] = "unknown"
    else:
        reasons["condition"] = "gap"

    if spec.need:
        specs = offer.specs or {}
        seen = fits = 0
        for k, (lo, hi) in spec.need.items():
            v = specs.get(k)
            if v is None:
                continue
            seen += 1
            if lo <= float(v) <= hi:
                fits += 1
        if seen == 0:
            reasons["size"] = "unknown"
        elif fits == seen:
            total += WEIGHTS["size"]; reasons["size"] = "ok"
        else:
            reasons["size"] = "gap"
    else:
        reasons["size"] = "n/a"

    if spec.words:
        hay = {w.lower() for w in _WORD_RX.findall(offer.title or "")}
        hit = len(spec.words & hay)
        if hit:
            total += WEIGHTS["words"] * min(1.0, hit / max(1, len(spec.words)))
            reasons["words"] = f"{hit}/{len(spec.words)}"
        else:
            reasons["words"] = "0"
    return round(total, 3), reasons


def candidates(db: Session, spec: WantSpec, limit: int = 2000) -> list[Lot]:
    q = select(Lot).where(Lot.status == "active", Lot.direction == spec.direction)
    if spec.slots:
        q = q.where(Lot.slot_id.in_(spec.slots))
    if spec.countries:
        q = q.where(Lot.country.in_(spec.countries))
    return list(db.scalars(q.order_by(Lot.posted_at.desc().nullslast(), Lot.id.desc()).limit(limit)))


def match_spec(db: Session, spec: WantSpec, top: int = 20, min_score: float = 0.5) -> list[tuple[Lot, float, dict]]:
    out = []
    for offer in candidates(db, spec):
        sc, why = score(spec, offer)
        if sc >= min_score:
            out.append((offer, sc, why))
    out.sort(key=lambda t: (-t[1], -(t[0].id)))
    return out[:top]


def run_wants(db: Session, top: int = 20) -> dict:
    """Все живые запросы → таблица `matches` (идемпотентно; новые строки — это и есть алерт)."""
    matcher = SlotMatcher(db)
    wants = list(db.scalars(select(Lot).where(Lot.direction == "want", Lot.status == "active")))
    new = total = 0
    per_want: dict[int, int] = {}
    for w in wants:
        spec = spec_from_want(db, w, matcher)
        res = match_spec(db, spec, top=top)
        per_want[w.id] = len(res)
        for offer, sc, why in res:
            total += 1
            m = db.scalar(select(Match).where(Match.want_id == w.id, Match.offer_id == offer.id))
            if m is None:
                db.add(Match(want_id=w.id, offer_id=offer.id, score=sc, reasons=why)); new += 1
            else:
                m.score = sc; m.reasons = why
    db.commit()
    return {"wants": len(wants), "matches": total, "new": new, "per_want": per_want}
