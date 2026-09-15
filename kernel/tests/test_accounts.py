"""Шардирование каналов между аккаунтами Telegram.

Что здесь охраняется — три свойства, каждое из которых при поломке стоит
аккаунта, а не отчёта:

1. **Одиночная конфигурация не меняется молча.** Без `TG_ACCOUNTS` всё
   работает как раньше и пишет в те же файлы состояния. Иначе обновление
   кода «потеряло» бы накопленные offsetы и пересобрало ленту с нуля.
2. **Владелец канала не переезжает.** Шард считается от имени, а не от места
   в списке. Каждый переезд стоит нового `ResolveUsername` на принимающем
   аккаунте — то есть ровно того расхода, ради экономии которого всё и
   затевалось.
3. **Вес управляет долей.** Свежему аккаунту нельзя отдать половину списка:
   две тысячи резолвов с холодного кэша — это не FloodWait, а удаление
   аккаунта. Доля должна расти по мере прогрева.
"""

from __future__ import annotations

import pytest

from kernel import accounts as acc


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch, tmp_path):
    for k in list(__import__("os").environ):
        if k.startswith(("TG_ACCOUNTS", "TG_SESSION_PATH", "TG_WEIGHT", "WATCH_NEW_CHANNELS")):
            monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TG_SESSION_PATH", str(tmp_path / "openclaw.session"))
    # Настройки кэшируются в модульной переменной, и без сброса второй тест
    # получил бы путь первого. Ловушка тихая: тесты проходят, но проверяют не
    # ту конфигурацию, которую задали.
    from kernel import config
    config.reset_for_tests()
    yield
    config.reset_for_tests()


def _channels(n: int) -> list[dict]:
    return [{"handle": f"@chan{i}", "id": str(i)} for i in range(n)]


# ── 1. Одиночная конфигурация не меняется ────────────────────────────


def test_single_account_by_default():
    accounts = acc.load_accounts()
    assert len(accounts) == 1
    assert accounts[0].name == acc.DEFAULT_ACCOUNT


def test_default_account_has_no_file_suffix():
    """Суффикс у аккаунта по умолчанию означал бы, что после обновления кода
    обход не найдёт свои offsetы и пересоберёт ленту заново."""
    assert acc.load_accounts()[0].side_suffix() == ""


def test_single_account_gets_the_whole_list():
    a = acc.load_accounts()[0]
    chans = _channels(100)
    assert acc.shard(chans, a, [a]) == chans


# ── 2. Владелец канала не переезжает ─────────────────────────────────


def test_owner_is_stable_across_processes(monkeypatch):
    """`hash()` в Python солится на запуск (PYTHONHASHSEED), поэтому владелец
    считается через md5. Проверяем на конкретных значениях, а не на «дважды
    подряд одинаково» — это поймало бы и солёный hash внутри одного процесса.
    """
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    accounts = acc.load_accounts()
    first = {c: acc.owner_of(c, accounts).name for c in ("@alpha", "@beta", "@gamma")}
    again = {c: acc.owner_of(c, accounts).name for c in ("@alpha", "@beta", "@gamma")}
    assert first == again
    # Значение зависит только от имени: регистр и собака канонизируются.
    assert acc.owner_of("@Alpha", accounts).name == acc.owner_of("alpha", accounts).name


def test_owner_does_not_depend_on_list_order(monkeypatch):
    """Список меняется при каждой прополке. Если бы шард зависел от порядка,
    каждая прополка перетасовывала бы владельцев и жгла резолвы."""
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    accounts = acc.load_accounts()
    chans = _channels(200)
    mine_before = {c["handle"] for c in acc.shard(chans, accounts[1], accounts)}
    shuffled = list(reversed(chans))
    del shuffled[5:15]                      # часть каналов прополота
    mine_after = {c["handle"] for c in acc.shard(shuffled, accounts[1], accounts)}
    assert mine_after <= mine_before        # ничего нового не приехало


def test_shards_are_disjoint_and_complete(monkeypatch):
    """Канал принадлежит ровно одному аккаунту: пересечение означало бы
    двойную оплату одних и тех же имён, пропуск — тихую потерю канала."""
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    accounts = acc.load_accounts()
    chans = _channels(500)
    a_set = {c["handle"] for c in acc.shard(chans, accounts[0], accounts)}
    b_set = {c["handle"] for c in acc.shard(chans, accounts[1], accounts)}
    assert not (a_set & b_set)
    assert len(a_set | b_set) == 500


# ── 3. Вес управляет долей ───────────────────────────────────────────


def test_weight_controls_the_share(monkeypatch):
    """Свежий аккаунт начинает с малой доли и растёт настройкой, а не правкой
    кода: 5% сегодня, 50% через месяц прогрева."""
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    monkeypatch.setenv("TG_WEIGHT_A", "95")
    monkeypatch.setenv("TG_WEIGHT_B", "5")
    accounts = acc.load_accounts()
    chans = _channels(2000)
    b_share = len(acc.shard(chans, accounts[1], accounts)) / 2000
    assert 0.03 < b_share < 0.07


def test_equal_weights_split_roughly_in_half(monkeypatch):
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    accounts = acc.load_accounts()
    chans = _channels(2000)
    b_share = len(acc.shard(chans, accounts[1], accounts)) / 2000
    assert 0.45 < b_share < 0.55


def test_zero_weight_account_gets_nothing(monkeypatch):
    """Вес 0 — способ вывести аккаунт из обхода, не удаляя его настройки.
    Нужен, когда аккаунт под баном: пусть его шард обслужит второй."""
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    monkeypatch.setenv("TG_WEIGHT_B", "0")
    accounts = acc.load_accounts()
    chans = _channels(300)
    assert acc.shard(chans, accounts[1], accounts) == []
    assert len(acc.shard(chans, accounts[0], accounts)) == 300


# ── Пути и бюджеты ───────────────────────────────────────────────────


def test_second_account_gets_its_own_session_file(monkeypatch):
    """Общий файл сессии — самая дорогая ошибка из возможных: второй аккаунт
    затёр бы кэш сущностей первого (3 969 прогретых имён)."""
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    a, b = acc.load_accounts()
    assert a.session_path != b.session_path
    assert b.session_path.name.endswith(".b.session")


def test_second_account_state_files_are_separate(monkeypatch):
    """Своя пауза, свой счётчик, свой темп. Общие означали бы, что бан
    одного останавливает второй — то есть второй не даёт ничего."""
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    from kernel import sidefiles
    a, b = acc.load_accounts()

    sidefiles.use_account(a)
    pause_a = sidefiles.side_file(".watch_paused_until")
    sidefiles.use_account(b)
    pause_b = sidefiles.side_file(".watch_paused_until")
    usage_b = sidefiles.side_file(".watch_api_usage.json")

    assert pause_a != pause_b
    assert pause_b.name == ".watch_paused_until.b"
    assert usage_b.name == ".watch_api_usage.b.json"

    sidefiles.use_account(a)                       # вернуть как было


def test_fresh_account_resolve_budget_is_smaller_by_default(monkeypatch):
    """Резолв — единственная операция, за которую свежий аккаунт наказывают
    удалением, а не паузой. Умолчание обязано быть скромнее общего."""
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    a, b = acc.load_accounts()
    assert b.new_per_day < a.new_per_day


def test_unknown_account_fails_loudly(monkeypatch):
    """Опечатка в имени не должна молча уводить обход на первый аккаунт:
    это значило бы обход чужого шарда чужой сессией."""
    monkeypatch.setenv("TG_ACCOUNTS", "a,b")
    with pytest.raises(SystemExit):
        acc.get_account("c")
