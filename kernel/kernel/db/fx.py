"""Currency rates + salary normalisation helpers.

Single anchor: ``usd_per[X]`` is the USD value of one unit of currency X
(so ``usd_per['USD'] == 1``). From it we derive BOTH base values for any
salary — USD directly, RUB via the RUB anchor. Rates come from a free,
no-key endpoint (open.er-api.com) and are refreshed hourly by the app
lifespan (Task 11); a static fallback keeps conversion working before
the first fetch and whenever the feed is unreachable.

This module is intentionally split into pure helpers (``to_rub_usd``,
``_usd_per_from_rates``) and IO (``fetch_usd_per``, ``upsert_rates``,
``load_cache_from_db``, ``refresh_rates``) so normalisation on write
(Task 12) and the hourly refresh (Task 11) can compose them without
re-fetching.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

logger = logging.getLogger("kernel.fx")


class CurrencyRateMixin:
    """Колонки таблицы курсов. Проект объявляет свою модель на СВОЁМ Base:

        class CurrencyRate(Base, CurrencyRateMixin):
            __tablename__ = "currency_rates"

    и передаёт её в IO-функции ниже. Ядро не держит собственного Base —
    две метаданных в одном процессе означали бы две «истины» о схеме
    (перенос из recruit 15.09.2026; там модель жила в app/models/currency_rate.py).
    """

    @declared_attr
    def currency(cls) -> Mapped[str]:  # noqa: N805
        return mapped_column(String(8), primary_key=True)

    @declared_attr
    def usd_per(cls) -> Mapped[Decimal]:  # noqa: N805
        return mapped_column(Numeric(18, 8), nullable=False)

    @declared_attr
    def fetched_at(cls) -> Mapped[datetime]:  # noqa: N805
        return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

# Free, no-key FX feed. ``rates[X]`` = units of X per 1 USD.
FX_API_URL = "https://open.er-api.com/v6/latest/USD"

# Currencies we normalise. Deliberately a SUPERSET of the ``Currency``
# literal in domain.py: that literal is what the API *accepts on write*
# (and what the UI offers), while this list is what we can *convert*.
# Bulk importers and the Telegram extractor write straight to the
# ``String(8)`` column, so UAH/GBP arrive whether the literal knows them
# or not — and an unknown currency silently left ``salary_*_rub`` NULL,
# which downstream reads as «вилки нет». Замер 26.07: у senior+ это
# RUR 132 · UAH 37 · USDT 11 · GBP 6 — все 100% отброшены.
SUPPORTED: tuple[str, ...] = (
    "USD", "RUB", "EUR", "KZT", "UAH", "GBP",
    # Добавлено 14.08 по замеру salary_currency_gaps: 85 вакансий с вилкой
    # не нормализовались, потому что их валюта не была в карте. Это реальные
    # валюты живой ленты (PLN 25, MMK 18, INR 14, UZS 9, CZK/CHF/JPY/NZD).
    "PLN", "INR", "CZK", "CHF", "JPY", "NZD", "MMK", "UZS",
    # Добавлено 29.08 (вечерний прогон salary_currency_gaps, по codepoint-
    # отчёту): 82 строки легитимных ISO-кодов без курса. Больше половины —
    # Залив (SAR 41, AED 5, QAR 3): в ленте есть арабские каналы.
    "SAR", "TJS", "AED", "BRL", "AZN", "BYN", "GEL", "QAR",
    "CAD", "TRY", "CNY", "JOD", "RSD",
)

# Codes that are not their own currency and are never in the feed:
#   RUR  — legacy ISO code for the pre-1998 rouble, still emitted by hh.ru
#          exports and by posts that copy them;
#   USDT — a USD-pegged stablecoin; crypto-paying posts quote it exactly
#          where others write «$», so treating it as USD is the honest
#          reading, not a rounding trick.
#   USDC — та же логика, что USDT: USD-стейблкоин.
#   $, € — СИМВОЛ утёк в колонку валюты вместо кода (замер 14.08: $×4, €×1).
#          Источник — не regex-парсер (он отдаёт коды), а LLM/импорт. Чинить
#          на месте конверсии дешевле и покрывает любой источник сразу.
# Resolved at conversion time, so they need no rate row of their own.
_ALIASES: dict[str, str] = {
    "RUR": "RUB", "USDT": "USD", "USDC": "USD", "$": "USD", "€": "EUR",
    # 29.08, salary_currency_gaps: узбекский сум приходит как SO'M в ЧЕТЫРЁХ
    # написаниях, различимых только апострофом — LLM копирует тот апостроф,
    # что был в посте. Таблица _APOSTROPHES ниже сводит их к одному ключу.
    # Кириллическое «СУМ» — тот же сум.
    "SO'M": "UZS", "СУМ": "UZS",
    # Чешская крона: в постах «Kč» (и «Kc» без диакритики), код — CZK.
    "KČ": "CZK", "KC": "CZK",
    # 29.08 (вечер): символ и кириллица гривны; турецкая лира разговорным «TL».
    "₴": "UAH", "ГРН": "UAH", "ГРН.": "UAH", "TL": "TRY",
    # 15.09 (перенос в HMB-Market, база — KZ): символ и кириллица тенге и
    # рубля в recruit замаплены не были — `classify_currency("₸")` отдавал
    # `unknown`. Для рынка, где половина цен в ₸ и ₽, это не хвост, а ядро.
    "₸": "KZT", "ТГ": "KZT", "ТГ.": "KZT", "ТЕНГЕ": "KZT", "KZT.": "KZT",
    "₽": "RUB", "РУБ": "RUB", "РУБ.": "RUB", "Р.": "RUB",   # голое «Р» — не алиас: слишком широко без замера
    "£": "GBP",
    # СОЗНАТЕЛЬНО НЕ ЗАМАПЛЕНО:
    #   «ريال» (риял, 28 строк) — без контекста это SAR (3.75/USD) ИЛИ
    #   иранский IRR (~42 000/USD): ошибка в ×11 000 раз. Решается чтением
    #   каналов этих строк, не словарём.
    #   «جنيه» (фунт, 1) — египетский или суданский, та же неоднозначность.
    #   SDG (1) — гиперинфляция; фолбэк «в разы» здесь врал бы на порядки.
}

# Апострофы, которыми пишут SO'M: прямой, типографские, modifier letters,
# штрих, акут, бэктик (та же таблица, что в alias_guard, 29.08).
_APOSTROPHES = dict.fromkeys(
    map(ord, "'" "\u2019" "\u2018" "\u02bb" "\u02bc" "\u2032" "\u00b4" "`"),
    "'",
)

# Токен ПЕРИОДА, утёкший в колонку валюты («мес», «/час», «в год»...).
# Валюты из него не сделать, а молчаливый None был неотличим от «экзотика
# без курса» — различие нужно замеру (salary_currency_gaps), поэтому
# распознаём явно. Значение честно теряется: выдумывать «наверное RUB»
# нельзя — это подстановка вердикта (AGENT_RULES §14).
_PERIOD_TOKENS = frozenset({
    "МЕС", "МЕС.", "МЕСЯЦ", "/МЕС", "В МЕСЯЦ",
    "ЧАС", "ЧАС.", "/ЧАС", "В ЧАС",
    "ГОД", "ГОД.", "/ГОД", "В ГОД", "ГОДОВЫХ",
    "MONTH", "/MONTH", "PER MONTH", "MO",
    "HOUR", "/HOUR", "PER HOUR", "HR",
    "YEAR", "/YEAR", "PER YEAR", "YR", "ANNUAL", "P.A.",
    # 29.08 (вечер): «DAY» измерен в поле валюты; русская семья — тот же класс.
    "DAY", "/DAY", "PER DAY", "ДЕНЬ", "/ДЕНЬ", "В ДЕНЬ", "СМЕНА", "ЗА СМЕНУ",
})

# Множитель, утёкший в поле валюты: «150 K» → currency='K'; узбекское
# «MING» («тысяча») — то же самое на другом языке. Оба ИЗМЕРЕНЫ 29.08.
# Валюту из множителя не достать — честный None, но свой класс в отчёте:
# это пятая причина, и лечится она в приёме, не в словаре.
_MULTIPLIER_TOKENS = frozenset({"K", "К", "MING", "ТЫС", "ТЫС.", "THOUSAND"})


def classify_currency(raw: str | None) -> tuple[str, str | None]:
    """(вид, код|норма): 'code' — конвертируемый код после нормализации;
    'period' — в поле валюты лежит период; 'empty' — пусто; 'unknown' —
    не распознано (норма возвращается для отчёта). Один классификатор и
    для конверсии, и для замера — чтобы их ответы не расходились.
    """
    if raw is None or not str(raw).strip():
        return ("empty", None)
    norm = str(raw).strip().translate(_APOSTROPHES).upper()
    norm = _ALIASES.get(norm, norm)
    if norm in _CACHE or norm in SUPPORTED:
        return ("code", norm)
    if norm in _PERIOD_TOKENS:
        return ("period", norm)
    if norm in _MULTIPLIER_TOKENS:
        return ("multiplier", norm)
    return ("unknown", norm)

# Static fallback, ``usd_per[X]`` = USD per 1 X (approx. mid-2025). Used
# until the first successful fetch and for any currency missing from the
# live feed. ``USD`` is the identity anchor and always 1.0.
_FALLBACK_USD_PER: dict[str, float] = {
    "USD": 1.0,
    "RUB": 1.0 / 90.0,
    "EUR": 1.09,
    "KZT": 1.0 / 470.0,
    "UAH": 1.0 / 41.0,
    "GBP": 1.27,
    # Приблизительные курсы (mid-2025), USD за 1 единицу. Фолбэк — до первого
    # успешного живого фетча, который их перекроет. Для бенчмарка, который и
    # так режет полосой 40k–1.5M ₽, точности «в разы» достаточно, а «нет
    # курса» стоило потери всей вилки (замер 14.08).
    "PLN": 1.0 / 4.0,        # злотый
    "INR": 1.0 / 84.0,       # рупия
    "CZK": 1.0 / 23.0,       # чешская крона
    "CHF": 1.12,             # франк (дороже доллара)
    "JPY": 1.0 / 155.0,      # иена
    "NZD": 0.60,             # новозеландский доллар
    "MMK": 1.0 / 2100.0,     # мьянманский кьят
    "UZS": 1.0 / 12700.0,    # узбекский сум
    # 29.08: SAR/AED/QAR/AZN/JOD привязаны к доллару (пег) — фолбэк почти
    # точен; остальные — той же «в разы» точности, что и блок выше.
    "SAR": 1.0 / 3.75,       # саудовский риял (пег)
    "AED": 1.0 / 3.6725,     # дирхам ОАЭ (пег)
    "QAR": 1.0 / 3.64,       # катарский риял (пег)
    "AZN": 1.0 / 1.70,       # азербайджанский манат (пег)
    "JOD": 1.0 / 0.709,      # иорданский динар (пег)
    "TJS": 1.0 / 10.6,       # таджикский сомони
    "BRL": 1.0 / 5.5,        # бразильский реал
    "BYN": 1.0 / 3.3,        # белорусский рубль
    "GEL": 1.0 / 2.7,        # грузинский лари
    "CAD": 1.0 / 1.37,       # канадский доллар
    "TRY": 1.0 / 34.0,       # турецкая лира
    "CNY": 1.0 / 7.2,        # юань
    "RSD": 1.0 / 108.0,      # сербский динар
}

# Process-wide cache of ``usd_per``, seeded with the fallback so the pure
# converter always has something to work with. Updated on fetch / load.
_CACHE: dict[str, float] = dict(_FALLBACK_USD_PER)


# ── Pure helpers ────────────────────────────────────────────────


def _usd_per_from_rates(rates: dict[str, float]) -> dict[str, float]:
    """er-api ``rates`` (X per 1 USD) → ``usd_per`` (USD per 1 X)."""
    out: dict[str, float] = {"USD": 1.0}
    for cur in SUPPORTED:
        if cur == "USD":
            continue
        r = rates.get(cur)
        if r:
            out[cur] = 1.0 / float(r)
    return out


def to_rub_usd(
    amount: float | int | Decimal | None,
    currency: str | None,
    usd_per: dict[str, float] | None = None,
) -> tuple[int | None, int | None]:
    """Convert ``amount`` in ``currency`` to ``(rub, usd)`` base values.

    Pure over the supplied ``usd_per`` map (defaults to the module
    cache). Returns ``(None, None)`` when amount/currency is missing or
    the currency has no known rate. ``usd = amount × usd_per[cur]``;
    ``rub = usd ÷ usd_per['RUB']``.

    ``amount == 0`` трактуется как ОТСУТСТВИЕ значения, а не «ноль рублей».
    Замер 14.08: у вилок вида «до 5000 $» нижний край хранился как 0 (не
    NULL); `to_rub_usd(0)` давал 0, а `COALESCE(from_rub, to_rub)` в отчётах
    брал этот 0 вместо настоящего верхнего края — 34 вакансии показывались
    как «0 ₽». Ноль-зарплата смысла не несёт ни в одной валюте, поэтому
    честнее вернуть None и дать COALESCE взять живой край.
    """
    if not amount or not currency:
        return (None, None)
    rates = usd_per if usd_per is not None else _CACHE
    kind, code = classify_currency(currency)
    if kind != "code":
        return (None, None)
    up = rates.get(code)
    if not up:
        return (None, None)
    usd = float(amount) * float(up)
    rub_anchor = rates.get("RUB")
    rub = (usd / rub_anchor) if rub_anchor else None
    return (
        int(round(rub)) if rub is not None else None,
        int(round(usd)),
    )


HOURS_PER_MONTH = 168  # 21 рабочий день × 8 ч — почасовую ставку к месяцу


def to_monthly(amount: int | None, period: str | None) -> int | None:
    """Привести сумму к МЕСЯЧНОЙ базе по периоду из парсера зарплаты.

    ``'year'`` → ÷12, ``'hour'`` → ×``HOURS_PER_MONTH``, ``'month'``/``None`` —
    без изменений. Нужно, чтобы годовые/почасовые вилки не ложились в базу как
    месячный оклад: до этого «$120k/год» считался /worth как оклад и ронял
    перцентили. Сумма ``None`` (вилки нет) или неизвестный период → как есть.
    """
    if amount is None:
        return None
    if period == "year":
        return int(round(amount / 12))
    if period == "hour":
        return int(round(amount * HOURS_PER_MONTH))
    return amount


def range_norm(
    salary_from: int | None,
    salary_to: int | None,
    currency: str | None,
) -> dict[str, int | None]:
    """Normalised base columns for a price/salary RANGE (recruit: vacancy salary).

    Best-effort over the module cache: an unknown currency yields
    ``None`` for that pair and never raises. Keys map 1:1 onto the
    ``vacancies`` columns so callers can ``setattr`` them directly.
    """
    fr_rub, fr_usd = to_rub_usd(salary_from, currency)
    to_rub, to_usd = to_rub_usd(salary_to, currency)
    return {
        "salary_from_rub": fr_rub,
        "salary_from_usd": fr_usd,
        "salary_to_rub": to_rub,
        "salary_to_usd": to_usd,
    }


def point_norm(
    salary_expected: int | None,
    currency: str | None,
) -> dict[str, int | None]:
    """Normalised base columns for a single price/salary value (recruit: candidate expected)."""
    rub, usd = to_rub_usd(salary_expected, currency)
    return {"salary_expected_rub": rub, "salary_expected_usd": usd}


vacancy_salary_norm = range_norm      # имена recruit — для читателя, пришедшего оттуда
candidate_salary_norm = point_norm


def get_usd_per() -> dict[str, float]:
    """Snapshot of the current ``usd_per`` cache (never empty)."""
    return dict(_CACHE)


def _merge_into_cache(usd_per: dict[str, float]) -> None:
    for cur, up in usd_per.items():
        if up and up > 0:
            _CACHE[cur] = float(up)


# ── IO: fetch / persist / load ──────────────────────────────────


async def fetch_usd_per(client: httpx.AsyncClient | None = None) -> dict[str, float]:
    """Fetch live rates → ``usd_per`` map.

    Raises on network/parse failure; callers that must not crash (the
    hourly refresh) wrap this in try/except.
    """
    owns = client is None
    client = client or httpx.AsyncClient(timeout=10.0)
    try:
        resp = await client.get(FX_API_URL)
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("result") != "success":
            raise ValueError(f"fx feed result={payload.get('result')!r}")
        return _usd_per_from_rates(payload.get("rates", {}))
    finally:
        if owns:
            await client.aclose()


async def load_cache_from_db(db: AsyncSession, model: type) -> None:
    """Seed the in-memory cache from stored rates (call on startup)."""
    rows = (
        await db.execute(select(model.currency, model.usd_per))
    ).all()
    if rows:
        _merge_into_cache({c: float(up) for c, up in rows if up is not None})


async def upsert_rates(db: AsyncSession, usd_per: dict[str, float], model: type) -> None:
    """Persist ``usd_per`` into ``currency_rates`` and refresh the cache.

    Dialect-agnostic upsert (manual get-or-create) so it works on both
    Postgres (prod) and SQLite (tests). A single hourly refresher means
    there's no concurrent writer to race with.
    """
    now = datetime.now(UTC)
    for cur, up in usd_per.items():
        if not up or up <= 0:
            continue
        row = await db.get(model, cur)
        if row is None:
            db.add(
                model(currency=cur, usd_per=Decimal(str(up)), fetched_at=now)
            )
        else:
            row.usd_per = Decimal(str(up))
            row.fetched_at = now
    await db.commit()
    _merge_into_cache(usd_per)


async def refresh_rates(db: AsyncSession, model: type) -> bool:
    """Fetch + persist, best-effort.

    Returns ``True`` on success, ``False`` on any failure — never raises,
    so the hourly background task can't crash the app.
    """
    try:
        usd_per = await fetch_usd_per()
        await upsert_rates(db, usd_per, model)
        logger.info("fx.refresh_ok currencies=%s", sorted(usd_per))
        return True
    except Exception:  # noqa: BLE001 — best-effort background refresh
        logger.warning("fx.refresh_failed", exc_info=True)
        return False
