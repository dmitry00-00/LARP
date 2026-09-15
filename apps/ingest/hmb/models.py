"""Схема HMB-Market — первая версия, 15.09.2026, под ЛАРП.

Контракт — `docs/DOMAIN_MODEL.md` §1 с поправками записки о пересмотре ниши:
одна таблица `lots` на обе стороны рынка (`direction`), регламент — справочник
систем игр с числовыми пределами, обмеры тела — только там, где размер
физически решает. Провенанс у каждой строки: откуда пришла и когда
(recruit, миграция 0048 — заведено постфактум; здесь — с первой таблицы).

Что НЕ хранится намеренно (DATA_SOURCES §5): тексты чужих объявлений как
публикация (только `raw_text` в `inbox_items` как рабочий архив), контакты
продавцов, чужие фото (только число и ссылки на оригинал).
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from kernel.db.fx import CurrencyRateMixin


def _now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Source(TimestampMixin, Base):
    """Откуда берём. `kind`: shop · catalog · board · api · vk · tg · calendar · ruleset."""

    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2))
    lang: Mapped[str | None] = mapped_column(String(8))
    discipline: Mapped[str | None] = mapped_column(String(16))   # larp · hmb · reenact · hema · mixed
    access: Mapped[str | None] = mapped_column(String(16))       # json · html · wall · antibot
    robots_ok: Mapped[bool | None] = mapped_column(Boolean)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # У курсора обхода обязан быть писатель (recruit: 17 дней никто не писал
    # `last_polled_at`). Писатель — importers/*.py, читатель — `hmb status`.
    note: Mapped[str | None] = mapped_column(Text)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class InboxItem(TimestampMixin, Base):
    """Сырьё. `raw_text` — архив, из него всё пересобирается."""

    __tablename__ = "inbox_items"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_inbox_source_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    url: Mapped[str | None] = mapped_column(String(800))
    title: Mapped[str | None] = mapped_column(String(500))
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    price_raw: Mapped[str | None] = mapped_column(String(64))
    currency_raw: Mapped[str | None] = mapped_column(String(16))
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(2))
    lang: Mapped[str | None] = mapped_column(String(8))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, nullable=False)
    photos_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    photo_urls: Mapped[list[str] | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="raw", nullable=False, index=True)
    classified_as: Mapped[str | None] = mapped_column(String(16))     # offer · want · service · digest · other
    skip_reason: Mapped[str | None] = mapped_column(String(64))
    extraction_meta: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    provenance: Mapped[str] = mapped_column(String(32), default="import", nullable=False)


class Slot(Base):
    """Словарь позиций. `group`: weapon · shield · armour · clothing · accessory · camp · sfx."""

    __tablename__ = "slots"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    group: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    label_ru: Mapped[str] = mapped_column(String(120), nullable=False)
    label_en: Mapped[str] = mapped_column(String(120), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("slots.id"))
    zones: Mapped[list[str] | None] = mapped_column(JSON)
    layer: Mapped[int | None] = mapped_column(Integer)
    measures: Mapped[list[str] | None] = mapped_column(JSON)   # какие обмеры решают: chest · head · length_cm · weight_g …
    aliases: Mapped[list["SlotAlias"]] = relationship(back_populates="slot", cascade="all, delete-orphan")


class SlotAlias(Base):
    __tablename__ = "slot_aliases"
    __table_args__ = (UniqueConstraint("slot_id", "alias", name="uq_alias_slot"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[str] = mapped_column(ForeignKey("slots.id"), nullable=False, index=True)
    alias: Mapped[str] = mapped_column(String(120), nullable=False)
    lang: Mapped[str] = mapped_column(String(8), nullable=False)      # ru · en · de · nl · kk
    origin: Mapped[str | None] = mapped_column(String(64))             # seed · epicarmoury · wargearshop …
    slot: Mapped[Slot] = relationship(back_populates="aliases")


class Lot(TimestampMixin, Base):
    """Предмет: предложение или запрос. `kind`: ad (объявление) · catalog (витрина магазина)."""

    __tablename__ = "lots"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_lot_source_ext"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    direction: Mapped[str] = mapped_column(String(8), nullable=False, index=True)   # offer · want
    kind: Mapped[str] = mapped_column(String(8), nullable=False, default="ad", index=True)
    slot_id: Mapped[str | None] = mapped_column(ForeignKey("slots.id"), index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    price: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(8))
    price_rub: Mapped[int | None] = mapped_column(Integer)
    price_usd: Mapped[int | None] = mapped_column(Integer)
    condition: Mapped[str] = mapped_column(String(12), default="unknown", nullable=False)   # new · used · damaged · unknown
    city: Mapped[str | None] = mapped_column(String(120))
    country: Mapped[str | None] = mapped_column(String(2))
    lang: Mapped[str | None] = mapped_column(String(8))
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id"), nullable=False, index=True)
    source_url: Mapped[str | None] = mapped_column(String(800))
    external_id: Mapped[str] = mapped_column(String(128), nullable=False)
    inbox_item_id: Mapped[int | None] = mapped_column(ForeignKey("inbox_items.id"))
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # Спецификации предмета — не обмеры тела: length_cm, blade_cm, weight_g,
    # core, material, brand, chest_cm, head_cm … (что есть — то есть).
    specs: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    photos_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Решение владельца 15.09: картинки витрин показываем ПО ПРЯМОЙ ССЫЛКЕ на CDN
    # магазина (копии у нас нет; пропал товар — пропала картинка). Заполняется
    # только у kind=catalog; фото частных объявлений (kind=ad) не републикуем.
    image_url: Mapped[str | None] = mapped_column(String(800))
    maker: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(12), default="active", nullable=False, index=True)   # active · stale · sold · dead
    provenance: Mapped[str] = mapped_column(String(32), default="import", nullable=False)
    slot_confidence: Mapped[float | None] = mapped_column(Float)


class Game(TimestampMixin, Base):
    """Игра из календаря (kogda-igra.ru) — источник всплесков спроса и реестр сообществ."""

    __tablename__ = "games"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)          # id kogda-igra
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    begin: Mapped[str | None] = mapped_column(String(10))               # YYYY-MM-DD как отдаёт API
    region: Mapped[str | None] = mapped_column(String(64))
    players_count: Mapped[int | None] = mapped_column(Integer)
    game_type: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str | None] = mapped_column(String(64))
    vk_club: Mapped[str | None] = mapped_column(String(120), index=True)
    telegram_channel: Mapped[str | None] = mapped_column(String(120), index=True)
    polygon_name: Mapped[str | None] = mapped_column(String(200))
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source_update_date: Mapped[str | None] = mapped_column(String(40))
    raw: Mapped[dict[str, Any] | None] = mapped_column(JSON)


class Ruleset(Base):
    """Правила системы игры — то, чем считается `conflict` для ЛАРП."""

    __tablename__ = "rulesets"

    id: Mapped[str] = mapped_column(String(48), primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str | None] = mapped_column(String(40))
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    lang: Mapped[str] = mapped_column(String(8), nullable=False)
    country: Mapped[str | None] = mapped_column(String(2))
    accessed_at: Mapped[str] = mapped_column(String(10), nullable=False)      # дата обращения — число без даты враньё
    note: Mapped[str | None] = mapped_column(Text)
    limits: Mapped[list["RulesetLimit"]] = relationship(back_populates="ruleset", cascade="all, delete-orphan")


class RulesetLimit(Base):
    """Один числовой предел: (класс, метрика, оператор, значение, единица)."""

    __tablename__ = "ruleset_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ruleset_id: Mapped[str] = mapped_column(ForeignKey("rulesets.id"), nullable=False, index=True)
    weapon_class: Mapped[str] = mapped_column(String(48), nullable=False)    # slot id или группа: sword_1h, polearm, bow, shield_large …
    metric: Mapped[str] = mapped_column(String(32), nullable=False)          # length_cm · weight_g · weight_g_per_m · hardness_shore_a · draw_kg · head_mm · diagonal_cm · mass_kg_per_m2 · padding_mm
    op: Mapped[str] = mapped_column(String(4), nullable=False)               # <= · >= · <
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(16), nullable=False)
    quote: Mapped[str | None] = mapped_column(Text)                          # дословно из источника
    ruleset: Mapped[Ruleset] = relationship(back_populates="limits")


class CurrencyRate(Base, CurrencyRateMixin):
    __tablename__ = "currency_rates"
