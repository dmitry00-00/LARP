"""Несколько аккаунтов Telegram: шардирование каналов и раздельное состояние.

Зачем (09.08). Суточный лимит выдаётся **аккаунту**, и до сих пор аккаунт был
один — то есть единственной точкой отказа и единственным измерительным
прибором. Второй аккаунт удваивает квоту, но только если каналы поделены:
два аккаунта, ходящие по одному списку, платят за одни и те же имена дважды
и вдвое быстрее упираются в стену.

## Почему шард взвешенный, а не пополам

Главный актив аккаунта — не он сам, а **кэш сущностей** в файле сессии.
Разрешённый однажды канал в следующий раз не стоит ни одного резолва; у
текущего аккаунта так закэшировано 3 969 имён из 4 144 активных (96%).

У нового аккаунта кэш пустой. Отдать ему половину списка значит потребовать
две тысячи `ResolveUsername` с холодного старта — ровно то, что описано в
комментарии к `_MAX_CHANNELS_PER_RUN` и что случилось 25.07, когда сессию
пересоздали. Для свежего аккаунта цена такой ошибки выше, чем FloodWait:
новые аккаунты за это удаляют.

Поэтому доля задаётся весом и растёт по мере прогрева. Вес — это единственная
ручка, которую надо трогать: `TG_WEIGHT_B=5` сегодня, `50` через месяц.

## Почему шард детерминированный

Владелец канала считается от его имени, а не от порядка в списке. Список
меняется (прополка, новые каналы), и шардирование «первая половина / вторая»
перетасовывало бы владельцев при каждом изменении — каждый переезд канала
стоит нового резолва на новом аккаунте и обнуляет прогретое.

## Чего это НЕ решает

Оба аккаунта выходят с одного адреса и устройства. Telegram их связывает:
если новый сгорит на агрессивном обходе, риск для старого вырастет. Второй
аккаунт — это больше квоты, а не индульгенция; ограничители из `telemetry`
применяются к каждому отдельно и остаются главной защитой.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

import structlog

from kernel.config import settings

log = structlog.get_logger()

# Имя аккаунта по умолчанию. Совпадает с тем, что было до появления этого
# модуля: одиночная конфигурация продолжает работать без единой правки в .env,
# и файлы состояния у неё остаются без суффикса — иначе обновление кода
# «потеряло» бы накопленные offsetы и счётчики.
DEFAULT_ACCOUNT = "a"


@dataclass(frozen=True)
class Account:
    """Один аккаунт: своя сессия, свой шард, свои бюджеты."""

    name: str
    session_path: Path
    weight: int
    new_per_day: int

    @property
    def is_default(self) -> bool:
        return self.name == DEFAULT_ACCOUNT

    def side_suffix(self) -> str:
        """Суффикс служебных файлов. У аккаунта по умолчанию его нет."""
        return "" if self.is_default else f".{self.name}"


def _env(name: str, account: str, default: str | None = None) -> str | None:
    return os.environ.get(f"{name}_{account.upper()}", default)


def load_accounts() -> list[Account]:
    """Аккаунты из окружения.

    Без `TG_ACCOUNTS` — ровно один аккаунт с нынешними настройками. Это не
    вежливость к старой конфигурации, а страховка: молчаливое включение
    второго аккаунта означало бы обход с сессии, которой ещё нет.
    """
    names = [n.strip().lower() for n in os.environ.get("TG_ACCOUNTS", "").split(",") if n.strip()]
    if not names:
        return [
            Account(
                name=DEFAULT_ACCOUNT,
                session_path=Path(settings().tg_session_path).expanduser().resolve(),
                weight=1,
                new_per_day=int(os.environ.get("WATCH_NEW_CHANNELS_PER_DAY", "60")),
            ),
        ]

    out: list[Account] = []
    for n in names:
        raw_path = _env("TG_SESSION_PATH", n)
        if raw_path:
            path = Path(raw_path).expanduser().resolve()
        elif n == DEFAULT_ACCOUNT:
            path = Path(settings().tg_session_path).expanduser().resolve()
        else:
            # Сессия рядом с основной, но с суффиксом: держать их в одном
            # каталоге удобно (там же все файлы состояния), а суффикс не даёт
            # двум аккаунтам писать в один файл — это стоило бы обоих сразу.
            base = Path(settings().tg_session_path).expanduser().resolve()
            path = base.with_name(f"{base.stem}.{n}{base.suffix}")
        # Бюджет резолвов зависит от того, прогрет ли аккаунт. У существующего
        # («a») кэш покрывает 96% каналов, и его прежние 60 в день менять не за
        # что. У любого нового кэш пустой, а резолв — единственная операция, за
        # которую свежий аккаунт наказывают не паузой, а удалением. Поэтому
        # умолчания разные, и это не мелочь: одно число здесь решает, переживёт
        # ли второй аккаунт первую неделю.
        default_new = "60" if n == DEFAULT_ACCOUNT else "15"
        out.append(
            Account(
                name=n,
                session_path=path,
                weight=max(0, int(_env("TG_WEIGHT", n, "1") or 1)),
                new_per_day=int(_env("WATCH_NEW_CHANNELS_PER_DAY", n, default_new) or default_new),
            ),
        )
    return out


def get_account(name: str | None = None) -> Account:
    """Аккаунт по имени; без имени — первый из списка."""
    accounts = load_accounts()
    if name is None:
        return accounts[0]
    wanted = name.strip().lower()
    for a in accounts:
        if a.name == wanted:
            return a
    raise SystemExit(
        f"Аккаунт '{wanted}' не описан. Есть: {', '.join(a.name for a in accounts)}. "
        f"Список задаётся переменной TG_ACCOUNTS в .env.ingest.",
    )


def _bucket_of(handle: str, total_weight: int) -> int:
    """Устойчивое число 0..total_weight-1 из имени канала.

    Именно md5, а не встроенный `hash()`: тот солится на каждый запуск
    процесса (PYTHONHASHSEED), и владелец канала менялся бы от прогона к
    прогону. Каждый такой переезд стоит нового резолва на новом аккаунте —
    то есть ровно того, что мы экономим.
    """
    digest = hashlib.md5(handle.strip().lstrip("@").lower().encode()).digest()  # noqa: S324
    return int.from_bytes(digest[:4], "big") % max(1, total_weight)


def owner_of(handle: str, accounts: list[Account]) -> Account:
    """Кому принадлежит канал."""
    live = [a for a in accounts if a.weight > 0] or accounts
    total = sum(a.weight for a in live) or len(live)
    pos = _bucket_of(handle, total)
    acc = 0
    for a in live:
        acc += a.weight
        if pos < acc:
            return a
    return live[-1]


def shard(channels: list[dict], account: Account, accounts: list[Account]) -> list[dict]:
    """Каналы, принадлежащие этому аккаунту.

    Один аккаунт — список целиком, без вычислений: это самый частый случай,
    и лишний проход по пяти тысячам словарей ради тождества ни к чему.
    """
    if len(accounts) <= 1:
        return channels
    return [c for c in channels if owner_of(c.get("handle", ""), accounts).name == account.name]
