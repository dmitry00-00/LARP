"""Замок на двери: клиент Telegram не открывается под баном и без бюджета.

Написано по итогам перепроверки 09.08, которая нашла пять дыр в собственной
защите. Эта — самая широкая: клиент открывают **пять** скиллов
(`watch_channels`, `check_dead_channels`, `probe_links`, `discover_channels`,
`discover_keyword_search`), паузу спрашивали **двое**, бюджет — **никто**.

То есть `discover` ходил в Telegram под активным FloodWait и продлевал его, а
`check_dead` резолвил каждый канал **временной сессией** — без кэша, самой
дорогой ценой из возможных, и без единого ограничителя.

Проверка перенесена в `__aenter__`: забыть её в новом скилле теперь нельзя,
соединение просто не откроется. Тесты стерегут именно это свойство, а не
конкретный текст ошибки.
"""

from __future__ import annotations

import time

import pytest

from kernel import sidefiles, telemetry
from kernel.clients.telegram import TelegramClient


@pytest.fixture(autouse=True)
def _isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(sidefiles, "side_file", lambda name: tmp_path / name)
    monkeypatch.setattr(telemetry, "read_json", sidefiles.read_json)
    monkeypatch.setattr(telemetry, "write_json", sidefiles.write_json)
    telemetry.reset_meter()
    yield
    telemetry.reset_meter()


def _pause_for(seconds: int) -> None:
    sidefiles.side_file(sidefiles.PAUSE_FILENAME).write_text(
        str(int(time.time()) + seconds),
    )


# ── Пауза ────────────────────────────────────────────────────────────


def test_client_refuses_to_open_under_flood_pause():
    """Обращение под активным баном продлевает бан. Это не осторожность,
    а наблюдение: 26.07 «осталось» шло 1424 → 1425 минут."""
    _pause_for(3600)
    with pytest.raises(RuntimeError, match="паузе"):
        TelegramClient()._check_limits()


def test_expired_pause_does_not_block():
    _pause_for(-10)
    TelegramClient()._check_limits()          # не должно бросить


def test_missing_pause_file_does_not_block():
    TelegramClient()._check_limits()


def test_broken_pause_file_does_not_block():
    """Битая метка не должна означать вечный бан: ошибка влево тут дороже —
    обход встал бы навсегда, и никакой отчёт этого не показал бы."""
    sidefiles.side_file(sidefiles.PAUSE_FILENAME).write_text("не число")
    TelegramClient()._check_limits()


# ── Бюджет ───────────────────────────────────────────────────────────


def test_client_refuses_to_open_without_budget():
    m = telemetry.meter()
    m.bump("X", telemetry._DEFAULT_DAILY_BUDGET + 10)
    with pytest.raises(RuntimeError, match="бюджет"):
        TelegramClient()._check_limits()


def test_client_refuses_when_burst_is_spent():
    """Ковш пуст при живом суточном бюджете — тоже «нельзя». Именно залп
    убил аккаунт 08.08: 192 канала за 67 минут при свободной суточной квоте."""
    m = telemetry.meter()
    m.bump("X", int(m.burst_capacity()))
    assert m.budget_left() > 0
    with pytest.raises(RuntimeError):
        TelegramClient()._check_limits()


# ── Оговорка для авторизации ─────────────────────────────────────────


def test_ignore_limits_is_available_for_authorisation():
    """`setup-tg` должен работать под баном: авторизация — это не обход."""
    _pause_for(3600)
    TelegramClient(ignore_limits=True)._check_limits()


def test_ignore_limits_is_off_by_default():
    """Умолчание обязано быть строгим: скилл, забывший про лимиты, должен
    упереться в стену, а не проскочить."""
    assert TelegramClient()._ignore_limits is False


# ── Свойство, ради которого замок перенесён на дверь ─────────────────


def test_every_skill_opening_a_client_is_covered(monkeypatch):
    """Скилл не обязан помнить про лимиты — их спрашивает сам клиент.

    Проверяем не список скиллов (он меняется), а то, что произвольный код,
    открывающий клиент, до сети не доходит.
    """
    _pause_for(3600)
    opened = {"n": 0}

    class _FakeSkill:
        async def run(self):
            async with TelegramClient():      # ни одной собственной проверки
                opened["n"] += 1

    import asyncio
    with pytest.raises(RuntimeError):
        asyncio.run(_FakeSkill().run())
    assert opened["n"] == 0


# ── Не перенесено (15.09.2026) ────────────────────────────────────────
# В recruit дальше идут два теста про «дыру, которую __aenter__ не закрывает»:
# скилл, прошедший дверь с остатком квоты, обязан спрашивать бюджет и ВНУТРИ
# прогона (27–28.08 check_dead_channels дважды выбрал суточную квоту). Они
# тестируют сам скилл check_dead_channels, которого в ядре нет. Урок остаётся:
# каждый скилл обхода в HMB-Market обязан звать telemetry.meter().allowance()
# в цикле, а не только на входе, и покрыть это тестом при появлении скилла.
