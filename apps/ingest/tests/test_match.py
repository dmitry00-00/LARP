"""Матчер спроса (Г2.2): оценка по условиям и идемпотентность `matches`."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from hmb.match import WantSpec, match_spec, run_wants, score, spec_from_filters
from hmb.models import Base, InboxItem, Lot, Source
from hmb.slots import seed_slots


@pytest.fixture()
def db():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        seed_slots(s)
        s.add(Source(id="t", kind="board", title="t", url="x"))
        s.add_all([
            Lot(source_id="t", external_id="1", direction="offer", kind="ad", slot_id="helmet", title="Бацинет стальной", price=9000, currency="RUB", price_rub=9000, condition="used", country="RU", status="active", specs={"head_cm": 59}),
            Lot(source_id="t", external_id="2", direction="offer", kind="ad", slot_id="helmet", title="Салад", price=30000, currency="RUB", price_rub=30000, condition="new", country="RU", status="active"),
            Lot(source_id="t", external_id="3", direction="offer", kind="ad", slot_id="helmet", title="Helm", price=100, currency="EUR", price_rub=10000, condition="unknown", country="DE", status="active"),
            Lot(source_id="t", external_id="4", direction="offer", kind="ad", slot_id="sword_1h", title="Меч", price=1000, currency="RUB", price_rub=1000, country="RU", status="active"),
            Lot(source_id="t", external_id="5", direction="offer", kind="ad", slot_id="helmet", title="Шлем протухший", price=100, currency="RUB", price_rub=100, country="RU", status="stale"),
        ])
        s.commit()
        yield s


def test_score_conditions():
    spec = WantSpec(slots=["helmet"], max_price_rub=10000, countries=["RU"], condition="used", need={"head_cm": (57, 61)})
    ok = Lot(slot_id="helmet", price_rub=9000, condition="used", country="RU", specs={"head_cm": 59}, title="Бацинет")
    sc, why = score(spec, ok)
    assert sc >= 0.95 and why == {"slot": "ok", "budget": "ok", "country": "ok", "condition": "ok", "size": "ok"}
    near = Lot(slot_id="helmet", price_rub=11000, condition="unknown", country="DE", specs={}, title="x")
    sc2, why2 = score(spec, near)
    assert why2["budget"] == "near" and why2["country"] == "gap" and why2["size"] == "unknown" and sc2 < sc
    assert score(spec, Lot(slot_id="sword_1h", price_rub=1, title="x"))[0] == 0.0     # слот обязателен


def test_match_spec_filters_and_ranks(db):
    res = match_spec(db, spec_from_filters({"slot": "helmet", "priceMax": 10000, "country": "RU"}))
    titles = [o.title for o, _, _ in res]
    assert titles == ["Бацинет стальной"]           # 30 000 — мимо бюджета; DE — не та страна; протухший — не active
    res_any = match_spec(db, spec_from_filters({"slot": "helmet", "priceMax": 12000}), min_score=0.5)
    assert {o.title for o, _, _ in res_any} == {"Бацинет стальной", "Helm"}


def test_run_wants_idempotent(db):
    it = InboxItem(source_id="t", external_id="w1", raw_text="Ищу бацинет до 10000 ₽, Москва", status="extracted")
    db.add(it); db.flush()
    db.add(Lot(source_id="t", external_id="w1", direction="want", kind="ad", slot_id="helmet", title="Ищу бацинет до 10000 ₽", country="RU", status="active", inbox_item_id=it.id))
    db.commit()
    r1 = run_wants(db); r2 = run_wants(db)
    assert r1["wants"] == 1 and r1["new"] == r1["matches"] >= 1
    assert r2["new"] == 0 and r2["matches"] == r1["matches"]
