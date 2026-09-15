"""Счётчик обращений к Telegram, приёмник флудов и самокалибрующийся темп.

Что здесь охраняется — не «функция возвращает число», а четыре свойства, из-за
отсутствия которых 08.08 был потерян день:

1. **Считается то, что расходуется.** Прежние бюджеты считали каналы, а канал
   ни в один лимит Telegram не входит. Платим за вызовы API.
2. **Мелкий флуд виден.** Telethon спит на нём молча; если приёмник перестанет
   разбирать запись, мы снова будем узнавать о стене только ударом.
3. **Чужой расход не затирается.** К сессии ходит не один процесс, и запись
   «целиком» показала бы свободную квоту там, где её нет.
4. **Вверх осторожно, вниз резко.** Лишний запрос стоит суток простоя,
   пропущенный канал — задержки в сборе.
"""

from __future__ import annotations

import json
import logging
import time

import pytest

from kernel import sidefiles, telemetry


@pytest.fixture(autouse=True)
def _isolated_state(tmp_path, monkeypatch):
    """Файлы состояния — во временный каталог, счётчик — с нуля на каждый тест."""
    monkeypatch.setattr(sidefiles, "side_file", lambda name: tmp_path / name)
    monkeypatch.setattr(telemetry, "read_json", sidefiles.read_json)
    monkeypatch.setattr(telemetry, "write_json", sidefiles.write_json)
    telemetry.reset_meter()
    yield
    telemetry.reset_meter()


# ── 1. Считается то, что расходуется ─────────────────────────────────


def test_counts_by_request_class():
    m = telemetry.ApiMeter()
    m.bump("GetHistoryRequest")
    m.bump("GetHistoryRequest")
    m.bump("GetFileRequest", 8)
    assert m.requests == {"GetHistoryRequest": 2, "GetFileRequest": 8}
    assert m.total() == 10


def test_download_costs_more_than_history():
    """Смысловой тест, а не арифметический.

    PDF на мегабайт качается частями по 128 КБ — это восемь `GetFile` против
    одного `GetHistory` на весь визит к каналу. Ровно эта асимметрия и объясняет,
    почему отмотка §L выжгла квоту: она не добавила запросов истории (50 ≤ 100,
    по-прежнему один вызов), она добавила вложений.
    """
    m = telemetry.ApiMeter()
    m.bump("GetHistoryRequest")           # один визит к каналу
    for _ in range(8):                     # один PDF на 1 МБ
        m.bump("GetFileRequest")
    assert m.requests["GetFileRequest"] == 8 * m.requests["GetHistoryRequest"]


# ── 2. Мелкий флуд виден ─────────────────────────────────────────────


def _flood_record(seconds: int, request: str, early: bool = False) -> logging.LogRecord:
    """Запись ровно в той форме, в какой её создаёт Telethon.

    `log.info(*_fmt_flood(...))` — то есть аргументы приходят НЕотформатированными
    (`telethon/client/users.py:18`). Приёмник читает их, а не разобранный текст:
    формулировка может измениться, состав аргументов — вряд ли.
    """
    import datetime as _dt
    return logging.LogRecord(
        name="telethon.client.users",
        level=logging.INFO,
        pathname="users.py",
        lineno=121,
        msg="Sleeping%s for %ds (%s) on %s flood wait",
        args=(" early" if early else "", seconds, _dt.timedelta(seconds=seconds), request),
        exc_info=None,
    )


def test_soft_flood_is_captured_not_lost():
    handler = telemetry._FloodCaptureHandler()
    handler.emit(_flood_record(23, "GetHistoryRequest"))
    m = telemetry.meter()
    assert m.soft_floods == {"GetHistoryRequest": 1}
    assert m.soft_flood_seconds == {"GetHistoryRequest": 23}
    assert m.hard_total() == 0


def test_hard_flood_is_separated_from_soft():
    """Граница 60 секунд не произвольная: ниже неё Telethon спит сам, и наружу
    такой флуд не выходит. Мелкий — предупреждение, крупный — авария."""
    handler = telemetry._FloodCaptureHandler()
    handler.emit(_flood_record(59, "GetHistoryRequest"))
    handler.emit(_flood_record(82311, "GetFileRequest"))
    m = telemetry.meter()
    assert m.soft_total() == 1
    assert m.hard_total() == 1


def test_capture_survives_format_change():
    """Если Telethon поменяет форму записи — молчим, а не роняем обход."""
    handler = telemetry._FloodCaptureHandler()
    broken = logging.LogRecord(
        name="telethon.client.users", level=logging.INFO, pathname="x", lineno=1,
        msg="something else entirely", args=("a",), exc_info=None,
    )
    handler.emit(broken)                     # не должно бросить
    assert telemetry.meter().soft_total() == 0


def test_install_is_idempotent(monkeypatch):
    """Демон запускает новый процесс каждый цикл, но в одном процессе клиент
    может создаваться дважды — второй обработчик дублировал бы каждый флуд."""
    monkeypatch.setattr(telemetry, "_logging_installed", False)
    lg = logging.getLogger("telethon.client.users")
    before = len(lg.handlers)
    telemetry.install_telethon_logging()
    telemetry.install_telethon_logging()
    added = len(lg.handlers) - before
    assert added == 1
    lg.handlers = lg.handlers[:before]


# ── 3. Чужой расход не затирается ────────────────────────────────────


def test_flush_merges_instead_of_overwriting(tmp_path):
    """К сессии ходит не только watch. Перезапись целиком показала бы
    свободную квоту там, где её уже нет, — а это худший вид ошибки:
    защита выключается ровно тогда, когда нужна."""
    sidefiles.write_json(
        telemetry._USAGE_FILENAME,
        {"day": sidefiles.today(), "requests": {"ResolveUsernameRequest": 5}},
    )
    m = telemetry.ApiMeter.load()
    m.bump("GetHistoryRequest", 3)
    m.flush()
    on_disk = json.loads((tmp_path / telemetry._USAGE_FILENAME).read_text())
    assert on_disk["requests"]["ResolveUsernameRequest"] == 5   # чужое цело
    assert on_disk["requests"]["GetHistoryRequest"] == 3


def test_new_day_resets_spend_but_keeps_ceiling():
    """Потолок — знание о лимите, а не расход: он обязан пережить полночь.
    Иначе каждое утро система заново искала бы стену ударом."""
    sidefiles.write_json(
        telemetry._USAGE_FILENAME,
        {
            "day": "1999-01-01",
            "requests": {"GetHistoryRequest": 900},
            "ceiling_at": 1242,
            "ceiling_day": "1999-01-01",
        },
    )
    m = telemetry.ApiMeter.load()
    assert m.total() == 0            # расход обнулился
    assert m.ceiling_at == 1242      # потолок остался


# ── Потолок калибруется замером, а не догадкой ───────────────────────


def test_ceiling_is_learned_from_the_hard_flood():
    m = telemetry.ApiMeter()
    m.bump("GetHistoryRequest", 1000)
    m.note_flood("GetFileRequest", 82311)
    assert m.ceiling_at == 1000
    assert m.daily_budget() == int(1000 * telemetry._CEILING_SAFETY)


def test_ceiling_ratchets_down_across_days():
    """Стена могла быть и ниже замеренного: берём минимум наблюдений.

    Сравнивать можно только сопоставимое — суточный расход с суточным. Внутри
    одних суток второй флуд всегда приходится на больший накопленный расход и
    новой информации о стене не несёт.
    """
    m = telemetry.ApiMeter()
    m.bump("X", 1000)
    m.note_flood("X", 82311)

    raw = json.loads(
        (sidefiles.side_file(telemetry._USAGE_FILENAME)).read_text(),
    )
    raw["day"] = "1999-01-01"                    # наступили новые сутки
    sidefiles.write_json(telemetry._USAGE_FILENAME, raw)

    m2 = telemetry.ApiMeter.load()
    assert m2.total() == 0
    m2.bump("X", 600)
    m2.note_flood("X", 82311)
    assert telemetry.ApiMeter.load().ceiling_at == 600


def test_ceiling_ignores_absurdly_low_calibration():
    """Защита от самоудушения.

    Один аномальный флуд на пустом расходе иначе опустил бы потолок до
    десятков запросов в сутки — и обход перестал бы собирать, продолжая
    выглядеть исправным. Невидимая потеря дороже видимой (AGENT_RULES §5).
    """
    m = telemetry.ApiMeter()
    m.bump("X", 10)
    m.note_flood("X", 82311)
    assert m.ceiling_at == 0                     # калибровку не приняли
    assert m.daily_budget() == telemetry._DEFAULT_DAILY_BUDGET


def test_budget_left_never_negative():
    m = telemetry.ApiMeter()
    m.bump("X", telemetry._DEFAULT_DAILY_BUDGET + 100)
    assert m.budget_left() == 0


# ── Бюджет ищет стену и снизу тоже ───────────────────────────────────


def _yesterday(requests: int, soft: int = 0, hard: int = 0, probe: int = 0) -> None:
    sidefiles.write_json(
        telemetry._USAGE_FILENAME,
        {
            "day": "1999-01-01",
            "requests": {"GetHistoryRequest": requests},
            "soft_floods": {"GetHistoryRequest": soft} if soft else {},
            "hard_floods": {"GetHistoryRequest": hard} if hard else {},
            "budget_probe": probe,
        },
    )


def test_budget_rises_after_a_day_without_a_single_flood():
    """Найдено живыми данными 09.08: 701 обращение за 74 минуты и НИ ОДНОГО
    флуда. Стена выше догадки, а система умела калибровать только вниз —
    то есть навсегда осталась бы на произвольном числе, останавливая обход
    через час. Это тот же принцип «искать стену снизу», но для суток."""
    _yesterday(requests=telemetry._DEFAULT_DAILY_BUDGET)
    m = telemetry.ApiMeter.load()
    assert m.daily_budget() > telemetry._DEFAULT_DAILY_BUDGET


def test_budget_does_not_rise_if_there_was_any_soft_flood():
    """Мелкий флуд — это уже «стена рядом». Расти при нём нельзя."""
    _yesterday(requests=telemetry._DEFAULT_DAILY_BUDGET, soft=1)
    assert telemetry.ApiMeter.load().daily_budget() == telemetry._DEFAULT_DAILY_BUDGET


def test_budget_does_not_rise_if_it_was_not_spent():
    """Не упирались — значит бюджет не мешал, и поднимать нечего."""
    _yesterday(requests=10)
    assert telemetry.ApiMeter.load().daily_budget() == telemetry._DEFAULT_DAILY_BUDGET


def test_measured_ceiling_stops_the_probe():
    """Замеренная стена бьёт догадку: подъём прекращается навсегда."""
    sidefiles.write_json(
        telemetry._USAGE_FILENAME,
        {
            "day": "1999-01-01",
            "requests": {"X": 5000},
            "ceiling_at": 1200,
            "budget_probe": 3000,
        },
    )
    m = telemetry.ApiMeter.load()
    assert m.daily_budget() == int(1200 * telemetry._CEILING_SAFETY)


def test_probe_climbs_over_several_clean_days():
    """За неделю чистых суток бюджет должен уйти далеко от стартовой догадки,
    иначе «21 день на круг» так и останется."""
    budget = telemetry._DEFAULT_DAILY_BUDGET
    for _ in range(7):
        _yesterday(requests=budget, probe=budget)
        budget = telemetry.ApiMeter.load().daily_budget()
    assert budget > telemetry._DEFAULT_DAILY_BUDGET * 4


def test_probe_has_a_hard_ceiling():
    _yesterday(requests=10**9, probe=telemetry._BUDGET_PROBE_MAX)
    assert telemetry.ApiMeter.load().daily_budget() <= telemetry._BUDGET_PROBE_MAX


# ── Ковш: защита от залпа, а не только от суточного перерасхода ──────


def test_burst_is_capped_even_when_daily_budget_is_free():
    """Суточный бюджет свободен, а залп запрещён.

    Ровно эта авария случилась 08.08: суточной квоты хватало, но 192 канала
    за 67 минут — это залп, и Telegram лимитирует именно его (заметка
    Telethon: «около 30 секунд на 10 запросов»).
    """
    m = telemetry.ApiMeter()
    cap = int(m.burst_capacity())
    m.bump("GetHistoryRequest", cap)
    assert m.budget_left() > 0          # на сутки ещё полно
    assert m.allowance() == 0           # а прямо сейчас — нельзя


def test_bucket_refills_over_time(monkeypatch):
    """Ковш капает со скоростью «бюджет за сутки»: за час набегает 1/24."""
    m = telemetry.ApiMeter()
    m.bump("X", int(m.burst_capacity()))
    assert m.allowance() == 0

    real = time.time
    monkeypatch.setattr(telemetry.time, "time", lambda: real() + 3600)
    expected = m.daily_budget() / 24
    assert m.allowance() == pytest.approx(expected, rel=0.05)


def test_bucket_does_not_accumulate_unlimited(monkeypatch):
    """Сутки паузы не дают права на суточный залп.

    Иначе снятие FloodWait разрешало бы ровно тот разгон, который к нему и
    привёл, — и мы вернулись бы к тому же сценарию с другой стороны.
    """
    m = telemetry.ApiMeter()
    m.bump("X", 1)
    real = time.time
    monkeypatch.setattr(telemetry.time, "time", lambda: real() + 86400 * 3)
    assert m.allowance() <= int(m.burst_capacity())


def test_daily_budget_still_caps_a_slow_overspend(monkeypatch):
    """Ковш не отменяет суточный предел: медленный перерасход тоже ловится."""
    m = telemetry.ApiMeter()
    m.bump("X", telemetry._DEFAULT_DAILY_BUDGET)
    real = time.time
    monkeypatch.setattr(telemetry.time, "time", lambda: real() + 86400)
    assert m.budget_left() == 0
    assert m.allowance() == 0


def test_negative_bucket_is_debt_not_an_uninitialised_marker():
    """Корневая ошибка 09.08, найденная живыми данными.

    Признаком «ковш ещё не заводили» служило `bucket < 0`, и `_refill`
    наливал по нему полный ковш. Но отрицательное значение — это ещё и
    ЗАКОННЫЙ долг за перерасход. Совпадение двух смыслов в одном признаке
    означало, что после каждого перерасхода ковш молча наполнялся заново, то
    есть ограничитель залпа не ограничивал ничего.

    Считается ровно: 13 прогонов × ~54 обращения = 702 против 701 в файле.
    Признак наличия ≠ признак работоспособности (AGENT_RULES §3).
    """
    m = telemetry.ApiMeter()
    cap = m.burst_capacity()
    m.bump("X", int(cap) + 20)                 # ушли в долг
    assert m.bucket < 0

    m._refill()                                 # раньше здесь наливался полный ковш
    assert m.bucket < 0, "долг обязан пережить refill, иначе он ничего не значит"
    assert m.allowance() == 0


def test_bucket_debt_is_capped_at_one_burst():
    """Найдено живыми данными 09.08: ковш ушёл в −527 при ёмкости 70.

    Долг переживает полночь, а капает со скоростью «бюджет за сутки» — то есть
    −527 съел бы четырнадцать часов СЛЕДУЮЩЕГО дня. Плохой час не должен
    стоить суток: восстановление со дна — около двух часов, не четырнадцати.
    """
    m = telemetry.ApiMeter()
    cap = m.burst_capacity()
    m.bump("X", int(cap) * 10)
    assert m.bucket >= -cap


def test_debt_recovers_in_hours_not_days(monkeypatch):
    """Тратим больше ковша, но заметно меньше суточного бюджета.

    Это не придирка к цифрам: два лимита разные, и если смешать их в тесте,
    он «пройдёт» на нуле, пришедшем не оттуда. Первая версия теста потратила
    ровно суточный бюджет и проверяла его, думая, что проверяет ковш.
    """
    m = telemetry.ApiMeter()
    spend = int(m.burst_capacity()) * 3            # 210 из 700 — суточный цел
    m.bump("X", spend)
    assert m.budget_left() > 0
    assert m.allowance() == 0                       # стоп пришёл от ковша

    real = time.time
    # Пять часов, а не три: ковш подрос до размера полного прогона (120),
    # и дно теперь глубже — восстановление 120/0.0081 ≈ 4.1 часа. Число
    # пересчитано под новую ёмкость, а не подогнано под тест.
    monkeypatch.setattr(telemetry.time, "time", lambda: real() + 5 * 3600)
    assert m.allowance() > 0                        # через пять часов снова можно


def test_existing_deep_debt_is_healed_on_load():
    """Чинить надо не только код, но и состояние, которое он успел испортить.

    В живом файле 09.08 лежит −527 при ёмкости 70 — накоплено до правки. Если
    пол применять только к новому долгу, старый переживёт исправление и всё
    равно съест восемнадцать часов следующего дня.
    """
    sidefiles.write_json(
        telemetry._USAGE_FILENAME,
        {"day": sidefiles.today(), "requests": {"X": 701},
         "bucket": -527.28, "bucket_ts": time.time()},
    )
    m = telemetry.ApiMeter.load()
    assert m.bucket == pytest.approx(-m.burst_capacity(), abs=0.01)

    # И лечение обязано попасть НА ДИСК, а не только в память: прогон,
    # упёршийся в бюджет, до `flush` не доходит — он возвращает ноль раньше.
    on_disk = json.loads((sidefiles.side_file(telemetry._USAGE_FILENAME)).read_text())
    assert on_disk["bucket"] == pytest.approx(-m.burst_capacity(), abs=0.01)


def test_debt_survives_a_restart_but_not_forever():
    """Долг обязан пережить перезапуск процесса — иначе перерасход обнулялся
    бы простым рестартом, и ограничитель не значил бы ничего."""
    m = telemetry.ApiMeter.load()
    m.bump("X", int(m.burst_capacity()) * 5)
    m.flush()
    again = telemetry.ApiMeter.load()
    assert again.bucket < 0
    assert again.bucket >= -again.burst_capacity()


def test_bucket_holds_at_least_one_full_run():
    """Авария 10.08, найденная по живому логу.

    При бюджете 910 ковш был 91, а прогон на 40 каналов стоит 40 × 3 = 120.
    Полный прогон стал невозможен в принципе, и система встала в равновесие
    «расход = приток» — по ОДНОМУ каналу за прогон:

        budget=1  budget_pace=40  n=1  api_spent_today=214

    Темп честно дорос до сорока и не мог быть использован ни разу.
    Пропускная способность упала до 303 каналов в сутки — круг за 14 дней,
    ровно то, от чего уходили.

    Урок: два ограничителя, посчитанные независимо, обязаны быть согласованы.
    Ковш ограничивает ЗАЛП, бюджет — ОБЪЁМ; залп меньше одного прогона
    превращается в потолок объёма, о котором никто не просил.
    """
    m = telemetry.ApiMeter()
    one_run = telemetry._PACE_MAX_CHANNELS * telemetry._EST_REQUESTS_PER_CHANNEL
    assert m.burst_capacity() >= one_run


def test_bucket_grows_with_the_budget_too():
    """Согласование не должно ломать прежнее правило: при большом бюджете
    ковш определяется долей, а не минимумом."""
    m = telemetry.ApiMeter()
    m.budget_probe = 20000
    assert m.burst_capacity() == 20000 * telemetry._BURST_SHARE


def test_a_full_paced_run_is_affordable_from_a_full_bucket():
    """Сквозная проверка того же свойства в единицах каналов."""
    m = telemetry.ApiMeter()
    affordable = int(m.allowance()) // telemetry._EST_REQUESTS_PER_CHANNEL
    assert affordable >= telemetry._PACE_MAX_CHANNELS


def test_fresh_install_gets_a_full_bucket():
    """Пустой ковш на старте означал бы час простоя после каждой установки."""
    m = telemetry.ApiMeter()
    assert m.allowance() == int(m.burst_capacity())


def test_bucket_spend_of_another_process_is_not_erased():
    """Дыра, найденная перепроверкой 09.08.

    Первая версия писала ковш целиком, а не дельтой. При двух процессах
    (`watch` и `check_dead` ходят к Telegram оба) второй затирал бы расход
    первого — то есть возвращал уже израсходованное право на залп. Счётчики
    запросов при этом сливались правильно, и снаружи всё выглядело исправным.
    """
    a = telemetry.ApiMeter.load()
    b = telemetry.ApiMeter.load()          # второй процесс, тот же файл

    a.bump("GetHistoryRequest", 30)
    a.flush()
    b.bump("GetFileRequest", 30)
    b.flush()

    fresh = telemetry.ApiMeter.load()
    cap = fresh.burst_capacity()
    # Ковш должен помнить ОБА расхода, а не только последний.
    assert fresh.bucket <= cap - 60 + 1
    assert fresh.total() == 60


# ── Стоимость вложения известна ДО загрузки ──────────────────────────


def test_download_cost_is_computed_from_size_not_guessed():
    """Часть — 128 КБ (`telethon/utils.py:1347`), по `upload.GetFile` на часть.
    Значит цену вложения можно спросить у бюджета заранее."""
    assert telemetry.download_cost(1024 * 1024) == 8        # 1 МБ
    assert telemetry.download_cost(128 * 1024) == 1
    assert telemetry.download_cost(129 * 1024) == 2         # округление вверх
    assert telemetry.download_cost(0) == 8                  # размер неизвестен
    assert telemetry.download_cost(None) == 8


def test_one_channel_visit_cannot_outspend_the_bucket():
    """Главная дыра, найденная перепроверкой 09.08.

    Бюджет спрашивался МЕЖДУ каналами, а тратился ВНУТРИ: один визит к каналу
    резюме — сотня постов, каждое вложение по восемь обращений. Получалось
    161 обращение там, где ковш разрешал 70, а на канале сплошных PDF — 800.
    Теперь цена вложения проверяется перед каждой загрузкой.
    """
    m = telemetry.meter()
    m.bump("GetHistoryRequest")                    # визит к каналу

    downloaded = 0
    for _ in range(100):                           # пачка из ста постов с PDF
        cost = telemetry.download_cost(1024 * 1024)
        if m.allowance() < cost:
            break                                  # ровно то, что делает клиент
        m.bump("GetFileRequest", cost)
        downloaded += 1

    assert m.total() <= m.burst_capacity() + 8     # перебор не больше одной части
    assert downloaded < 100                        # гейт сработал, а не пропустил


# ── 4. Вверх осторожно, вниз резко ───────────────────────────────────


def test_pace_grows_when_clean():
    p = telemetry.Pace(channels_per_run=10, interval_sec=3.0)
    p = p.after_run(soft_floods=0, hard_flood=False)
    assert p.channels_per_run > 10
    assert p.interval_sec < 3.0


def test_pace_backs_off_on_soft_flood():
    """Мелкий флуд и есть найденная стена — отходим, не дожидаясь суточной.
    Ради этого сигнал и включён."""
    p = telemetry.Pace(channels_per_run=20, interval_sec=3.0)
    p = p.after_run(soft_floods=1, hard_flood=False)
    assert p.channels_per_run < 20
    assert p.interval_sec > 3.0


def test_pace_backs_off_harder_on_hard_flood():
    soft = telemetry.Pace(channels_per_run=20, interval_sec=3.0).after_run(
        soft_floods=1, hard_flood=False,
    )
    hard = telemetry.Pace(channels_per_run=20, interval_sec=3.0).after_run(
        soft_floods=0, hard_flood=True,
    )
    assert hard.channels_per_run < soft.channels_per_run
    assert hard.interval_sec > soft.interval_sec


def test_pace_never_leaves_bounds():
    p = telemetry.Pace(channels_per_run=5, interval_sec=30.0)
    for _ in range(50):
        p = p.after_run(soft_floods=1, hard_flood=True)
    assert p.channels_per_run >= telemetry._PACE_MIN_CHANNELS
    assert p.interval_sec <= telemetry._PACE_MAX_INTERVAL

    p = telemetry.Pace(channels_per_run=40, interval_sec=1.0)
    for _ in range(50):
        p = p.after_run(soft_floods=0, hard_flood=False)
    assert p.channels_per_run <= telemetry._PACE_MAX_CHANNELS
    assert p.interval_sec >= telemetry._PACE_MIN_INTERVAL


def test_pace_climbs_out_of_the_floor():
    """Свойство, ради которого всё затевалось: после отката темп обязан
    подниматься сам. Иначе один флуд навсегда оставил бы обход на дне."""
    # 40 шагов, а не «на глазок»: интервал падает на 10% за прогон, и от 30 с
    # до пола нужно log(1/30)/log(0.9) ≈ 33 прогона. Меньше — тест проверял бы
    # не подъём, а собственную арифметику.
    p = telemetry.Pace(channels_per_run=5, interval_sec=30.0)
    for _ in range(40):
        p = p.after_run(soft_floods=0, hard_flood=False)
    assert p.channels_per_run == telemetry._PACE_MAX_CHANNELS
    assert p.interval_sec == pytest.approx(telemetry._PACE_MIN_INTERVAL, abs=0.01)


def test_first_run_after_pause_starts_low_not_at_ceiling():
    """Главное свойство всей затеи.

    Оба бана — 26.07 и 08.08 — случились по одному сценарию: пауза истекла,
    и обход сразу пошёл на полной скорости. 08.08 это продержалось 67 минут.
    Пустой файл темпа (а после аварии он именно такой) обязан означать
    «начинай с малого», а не «гони как раньше».
    """
    p = telemetry.Pace.load()
    assert p.channels_per_run == telemetry._PACE_START_CHANNELS
    assert p.channels_per_run < telemetry._PACE_MAX_CHANNELS
    assert p.interval_sec >= telemetry._PACE_START_INTERVAL


def test_pace_survives_broken_file():
    """Битый файл темпа не должен означать «гони на полной»."""
    sidefiles.side_file(telemetry._PACE_FILENAME).write_text("{не json")
    p = telemetry.Pace.load()
    assert telemetry._PACE_MIN_CHANNELS <= p.channels_per_run <= telemetry._PACE_MAX_CHANNELS
