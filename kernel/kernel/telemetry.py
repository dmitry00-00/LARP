"""Счётчик обращений к Telegram и самокалибрующийся темп обхода.

Зачем это появилось (разбор 08.08, `docs/TELEGRAM_RATE_LIMITS_ANALYSIS.md`).

Telegram предупреждает задолго до суточного бана — короткими паузами на
20–40 секунд. Мы их получали и не видели по двум причинам сразу:

1. `flood_sleep_threshold` у Telethon по умолчанию 60 секунд, и всё, что
   короче, библиотека **отсыпает молча** (`telethon/client/users.py:121`).
   Наружу, в наш `except FloodWaitError`, выходит только то, что больше
   минуты, — то есть только катастрофа и никогда её приближение.
2. Сообщение об этом уходит в стандартный `logging` уровня INFO, а проект
   логирует через structlog и стандартный `logging` не настраивает вовсе.
   Записи отбрасывались корневым логгером.

Итог: единственным измерительным прибором был боевой аккаунт, а показание он
выдавал раз в сутки. Отсюда два кирпича этого модуля.

**Счётчик** считает то, что реально расходуется, — вызовы API по классам
запроса. Прежние бюджеты считали каналы, а канал в лимиты Telegram не входит
никак: один визит это `GetHistory` на ≤100 сообщений, зато один PDF на мегабайт
это восемь `GetFile` (части по 128 КБ, `telethon/utils.py:1347`).

**Темп** подстраивается сам. Потолок ищется снизу: пока мелких флудов нет —
бюджет растёт, первый же мелкий флуд его роняет. Так стена находится без
суточной платы за каждую попытку. Свой потолок система запоминает: число
запросов, на котором прилетел суточный бан, становится калибровкой, и дальше
она держится ниже него. Ставить это число руками нельзя — мы его не знаем.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field

import structlog

from kernel.sidefiles import read_json, today, write_json

log = structlog.get_logger()

_USAGE_FILENAME = ".watch_api_usage.json"
_PACE_FILENAME = ".watch_pace.json"

# Порог, выше которого флуд считается «суточным», а не рабочей заминкой.
# Совпадает с умолчанием Telethon неслучайно: ниже него библиотека спит сама,
# и наружу такой флуд не выходит. Меняя одно, надо менять и другое.
_HARD_FLOOD_SEC = int(os.environ.get("WATCH_HARD_FLOOD_SEC", "60"))

# Доля от замеренного потолка, ниже которой держимся. 0.7 — не расчёт, а
# запас: потолок замерен один раз и в других условиях может оказаться ниже.
_CEILING_SAFETY = float(os.environ.get("WATCH_CEILING_SAFETY", "0.7"))

# Пока потолок не замерен — этот бюджет. Число не выведено, а взято ниже
# оценки того, что привело к бану 08.08 (~480 GetHistory плюс неизвестное
# число загрузок). Оно **временное**: после первого же суточного флуда его
# заменит замер, и трогать руками эту константу не нужно.
_DEFAULT_DAILY_BUDGET = int(os.environ.get("WATCH_API_BUDGET_PER_DAY", "700"))

# Ниже этого числа калибровку не принимаем. Защита от самоудушения: один
# аномальный суточный флуд (сетевой сбой, чужой процесс на той же сессии)
# иначе навсегда опустил бы потолок до десятков запросов, и обход перестал бы
# собирать, продолжая выглядеть исправным.
_CEILING_MIN = int(os.environ.get("WATCH_CEILING_MIN", "150"))

# На сколько поднимать суточный бюджет после суток БЕЗ единого флуда.
#
# Найдено живыми данными 09.08: за 74 минуты после снятия паузы — 701
# обращение и **ни одного флуда**, ни мелкого, ни суточного. То есть стена
# выше моей догадки в 700, а узнать этого система не могла: потолок
# калибровался только ВНИЗ, при суточном флуде. Без подъёма мы бы навсегда
# заменили «бан каждые сутки» на «обход душит сам себя на произвольном числе» —
# обход останавливался бы через час и стоял двадцать три.
#
# Подъём такой же осторожный, как у темпа, и по тому же правилу: растём,
# пока не упрёмся; упёрлись — потолок замерен и подъём прекращается.
_BUDGET_PROBE_UP = float(os.environ.get("WATCH_BUDGET_PROBE_UP", "1.3"))
_BUDGET_PROBE_MAX = int(os.environ.get("WATCH_BUDGET_PROBE_MAX", "20000"))

# Какую долю суточного бюджета разрешено потратить залпом.
#
# Без этого суточный бюджет воспроизводит ту же аварию в миниатюре: обход
# разгоняется, выжигает всё за полтора часа и молчит остаток суток. Ровно так
# прошло 08.08 — 192 канала за 67 минут и потом ничего. Плюс заметка самого
# Telethon: лимит для GetHistory «около 30 секунд на 10 запросов» — это лимит
# на ЗАЛП, а не на сутки, и суточным бюджетом он не ловится вовсе.
#
# Поэтому расход идёт через ковш: капает со скоростью «бюджет за сутки»,
# наполняется не выше этой доли. Пауза копит право на работу, но не бесконечно.
_BURST_SHARE = float(os.environ.get("WATCH_BURST_SHARE", "0.1"))

# Размер части при скачивании файла. Не догадка: `telethon/utils.py:1347`
# отдаёт 128 КБ для всего, что меньше 100 МБ, а `downloads.py` шлёт по
# `upload.GetFile` на часть. Значит стоимость вложения известна ДО загрузки —
# из `document.size`, — и её можно спросить у бюджета заранее.
_DOWNLOAD_PART_BYTES = 128 * 1024


def download_cost(size_bytes: int | None) -> int:
    """Во сколько обращений обойдётся скачивание файла такого размера.

    Размер неизвестен — считаем дорого (8 частей, то есть мегабайт). Ошибка
    вправо здесь безопаснее: пропущенное вложение видно строкой в логе, а
    перерасход виден только сутками бана.
    """
    if not size_bytes or size_bytes <= 0:
        return 8
    return max(1, -(-int(size_bytes) // _DOWNLOAD_PART_BYTES))

_PACE_MIN_CHANNELS = int(os.environ.get("WATCH_PACE_MIN_CHANNELS", "5"))
_PACE_MAX_CHANNELS = int(os.environ.get("WATCH_MAX_CHANNELS_PER_RUN", "40"))

# Нижняя граница интервала — из заметки самого Telethon: флуд-лимит для
# GetHistoryRequest «около 30 секунд на 10 запросов» (client/messages.py:377),
# то есть устойчивый темп примерно один запрос в 3 секунды. Прежние 0.5 с
# между каналами давали до 2 запросов в секунду — вшестеро выше.
_PACE_MIN_INTERVAL = float(os.environ.get("WATCH_PACE_MIN_INTERVAL", "1.0"))
_PACE_MAX_INTERVAL = float(os.environ.get("WATCH_PACE_MAX_INTERVAL", "30.0"))
_PACE_START_INTERVAL = float(os.environ.get("WATCH_PACE_START_INTERVAL", "3.0"))

# Стартуем НИЗКО, а не с потолка. Оба бана — 26.07 и 08.08 — случились по
# одному сценарию: пауза истекла, и обход сразу пошёл на полной скорости.
# Восемь каналов за прогон при подъёме на 10% доходят до сорока примерно за
# семнадцать прогонов, то есть за час-полтора; цена ошибки в другую сторону —
# сутки простоя и удвоение паузы.
_PACE_START_CHANNELS = int(os.environ.get("WATCH_PACE_START_CHANNELS", "8"))

# Во сколько обращений обходится один канал. Замер 09.08: 547 `GetHistory` на
# ~180 визитов, то есть три.
#
# Живёт здесь, а не в `watch_channels`, потому что от него зависит ёмкость
# ковша: залп обязан вмещать хотя бы один полный прогон. Две копии этого
# числа разошлись бы, и ковш снова стал бы потолком объёма (AGENT_RULES §7).
_EST_REQUESTS_PER_CHANNEL = int(os.environ.get("WATCH_EST_REQUESTS_PER_CHANNEL", "3"))


def burst_capacity_for(daily_budget: float) -> float:
    """Ёмкость залпа по суточному бюджету. Одна реализация на всех.

    Вынесена из метода 27.08 после того, как `ops/check/watch_state.command`
    завёл свою копию (`max(10, budget * 0.1)`) и **потеряла слагаемое про
    полный прогон**. На живых данных это выглядело так: ковш −120 «из 14»,
    хотя настоящая ёмкость 120, и −120 — это ровно потолок долга, а не
    девятикратный перебор. Число, по которому читают аварию, врало в девять
    раз (AGENT_RULES §7: копию логики — синхронизировать, а не писать).
    """
    one_full_run = _PACE_MAX_CHANNELS * _EST_REQUESTS_PER_CHANNEL
    return max(10.0, one_full_run, daily_budget * _BURST_SHARE)


# ── Счётчик ──────────────────────────────────────────────────────────


@dataclass
class ApiMeter:
    """Расход обращений к Telegram за текущие сутки UTC.

    Считает в памяти и сбрасывает на диск порциями: на прогон приходятся
    сотни вызовов, и писать файл на каждый — менять одну проблему на другую.

    Слияние на записи — дельтой, а не перезаписью: к сессии ходит не только
    `watch` (есть ещё `check_dead`, `probe_links`), и перезапись целиком
    затирала бы чужой расход. Затёртый расход опаснее несчитанного: он
    выглядит как «квота свободна».
    """

    day: str = field(default_factory=today)
    requests: dict[str, int] = field(default_factory=dict)
    soft_floods: dict[str, int] = field(default_factory=dict)
    soft_flood_seconds: dict[str, int] = field(default_factory=dict)
    hard_floods: dict[str, int] = field(default_factory=dict)
    # Потолок переживает смену суток: это знание о лимите, а не расход.
    ceiling_at: int = 0
    ceiling_day: str = ""
    # Поднятый замером бюджет. Живёт вне суток: это знание, а не расход.
    budget_probe: int = 0
    # Ковш допустимого залпа. Тоже вне суток: полночь не повод разрешить залп.
    bucket: float = -1.0        # -1 = ещё не инициализирован
    bucket_ts: float = 0.0

    _delta: dict[str, int] = field(default_factory=dict, repr=False)
    _delta_soft: dict[str, int] = field(default_factory=dict, repr=False)
    _delta_soft_sec: dict[str, int] = field(default_factory=dict, repr=False)
    _delta_hard: dict[str, int] = field(default_factory=dict, repr=False)
    _since_flush: int = field(default=0, repr=False)

    _FLUSH_EVERY = 25

    # ── чтение/запись ────────────────────────────────────────────────

    @classmethod
    def load(cls) -> ApiMeter:
        raw = read_json(_USAGE_FILENAME)
        m = cls()
        m.ceiling_at = int(raw.get("ceiling_at") or 0)
        m.ceiling_day = str(raw.get("ceiling_day") or "")
        m.budget_probe = int(raw.get("budget_probe") or 0)
        if raw.get("day") and raw.get("day") != m.day:
            m._probe_after_clean_day(raw)
        if "bucket" in raw:
            m.bucket_ts = float(raw.get("bucket_ts") or 0.0)
            # Пол применяем и к прочитанному, а не только к новому долгу.
            # Иначе уже накопленные −527 (файл от 09.08) пережили бы правку
            # и всё равно съели бы восемнадцать часов: чинить надо и код, и
            # состояние, которое он успел испортить.
            stored = float(raw.get("bucket") or 0.0)
            m.bucket = m._floor(stored)
            if m.bucket != stored:
                # Записываем сразу, а не ждём `flush`. Прогон, упёршийся в
                # бюджет, до `flush` не доходит вовсе — он возвращает ноль
                # раньше. Без этой записи долг чинился бы только в памяти, а
                # в файле и в сводке навсегда осталось бы «−527»: число,
                # которое ничего не значит, но пугает.
                raw["bucket"] = round(m.bucket, 2)
                write_json(_USAGE_FILENAME, raw)
        if raw.get("day") == m.day:
            m.requests = {k: int(v) for k, v in (raw.get("requests") or {}).items()}
            m.soft_floods = {k: int(v) for k, v in (raw.get("soft_floods") or {}).items()}
            m.soft_flood_seconds = {
                k: int(v) for k, v in (raw.get("soft_flood_seconds") or {}).items()
            }
            m.hard_floods = {k: int(v) for k, v in (raw.get("hard_floods") or {}).items()}
        return m

    def flush(self) -> None:
        """Прибавить накопленную дельту к тому, что лежит на диске."""
        if not (self._delta or self._delta_soft or self._delta_hard):
            return
        raw = read_json(_USAGE_FILENAME)
        same_day = raw.get("day") == self.day

        def merged(key: str, delta: dict[str, int]) -> dict[str, int]:
            base = {k: int(v) for k, v in (raw.get(key) or {}).items()} if same_day else {}
            for k, v in delta.items():
                base[k] = base.get(k, 0) + v
            return base

        # Ковш тоже сливается дельтой, а не перезаписывается.
        #
        # Первая версия писала `self.bucket` целиком, и это отменяло всю
        # защиту при двух процессах: `check_dead` со своим клиентом
        # потратил бы залп, а `watch` записал бы поверх своё значение — то
        # есть вернул бы уже израсходованное право. Счётчики запросов
        # сливались правильно, а ковш нет; расхождение вида «числа сходятся,
        # защита не работает» — самое дорогое из возможных.
        spent_unflushed = sum(self._delta.values())
        self._merge_bucket(raw, spent_unflushed)

        data = {
            "day": self.day,
            "requests": merged("requests", self._delta),
            "soft_floods": merged("soft_floods", self._delta_soft),
            "soft_flood_seconds": merged("soft_flood_seconds", self._delta_soft_sec),
            "hard_floods": merged("hard_floods", self._delta_hard),
            "ceiling_at": self.ceiling_at,
            "ceiling_day": self.ceiling_day,
            "budget_probe": self.budget_probe,
            "bucket": round(self.bucket, 2),
            "bucket_ts": round(self.bucket_ts, 2),
        }
        write_json(_USAGE_FILENAME, data)
        self.requests = data["requests"]
        self.soft_floods = data["soft_floods"]
        self.soft_flood_seconds = data["soft_flood_seconds"]
        self.hard_floods = data["hard_floods"]
        self._delta, self._delta_soft = {}, {}
        self._delta_soft_sec, self._delta_hard = {}, {}
        self._since_flush = 0

    # ── учёт ─────────────────────────────────────────────────────────

    def bump(self, request_name: str, n: int = 1) -> None:
        self.requests[request_name] = self.requests.get(request_name, 0) + n
        self._delta[request_name] = self._delta.get(request_name, 0) + n
        self._refill()
        self.bucket = self._floor(self.bucket - n)
        self._since_flush += n
        if self._since_flush >= self._FLUSH_EVERY:
            self.flush()

    # ── Ковш: право на залп ──────────────────────────────────────────

    def _floor(self, value: float) -> float:
        """Ограничить ДОЛГ ковша одним залпом.

        Найдено живыми данными 09.08: за 74 минуты ковш ушёл в −527 при
        ёмкости 70. Долг переживает полночь (ковш не привязан к суткам), а
        капает он со скоростью «бюджет за сутки» — то есть −527 съел бы
        четырнадцать часов СЛЕДУЮЩЕГО дня. Плохой час не должен стоить суток.

        Долг сам по себе нужен: он и есть плата за перерасход внутри прогона
        (визит к каналу стоит ~3 обращений, и проверка на его границе не может
        быть точной). Но глубина обязана быть ограничена — восстановление со
        дна занимает ровно `_BURST_SHARE` суток, то есть около двух часов.
        """
        cap = self.burst_capacity()
        if value < -cap:
            log.warning(
                "telegram.bucket_debt_capped",
                was=round(value, 1),
                floor=round(-cap, 1),
                hint="перерасход внутри прогона — смотри watch.channels.done",
            )
            return -cap
        return value

    def burst_capacity(self) -> float:
        """Сколько обращений разрешено подряд.

        **Не меньше стоимости одного полного прогона.** Найдено живыми
        данными 10.08: при бюджете 910 ковш был 91, а прогон на 40 каналов
        стоит 40 × 3 = 120 обращений. Полный прогон стал невозможен в
        принципе, и система встала в равновесие «расход = приток» — по
        ОДНОМУ каналу за прогон:

            budget=1  budget_pace=40  n=1  api_spent_today=214

        Темп честно дорос до сорока и не мог быть использован ни разу.
        Пропускная способность упала до 303 каналов в сутки — то есть круг
        за 14 дней, ровно то, от чего уходили.

        Урок общий: два ограничителя, посчитанные независимо, обязаны быть
        согласованы. Ковш ограничивает ЗАЛП, суточный бюджет — ОБЪЁМ; но
        залп, меньший одного прогона, превращается в потолок объёма, о
        котором никто не просил.
        """
        return burst_capacity_for(self.daily_budget())

    def _probe_after_clean_day(self, raw: dict) -> None:
        """Сутки кончились — решить, поднимать ли бюджет.

        Поднимаем только когда выполнены оба условия:

        * **ни одного флуда** — ни мелкого, ни суточного. Мелкий это уже
          «стена рядом», и при нём расти нельзя;
        * **бюджет был выбран почти весь** — иначе поднимать нечего: мы и так
          не упирались, а значит не знаем, мешал ли он вообще.

        Замеренный потолок отменяет подъём совсем: если Telegram однажды
        показал предел, догадки больше не нужны.
        """
        if self.ceiling_at:
            return
        spent = sum(int(v) for v in (raw.get("requests") or {}).values())
        floods = sum(int(v) for v in (raw.get("soft_floods") or {}).values())
        floods += sum(int(v) for v in (raw.get("hard_floods") or {}).values())
        was_budget = max(_DEFAULT_DAILY_BUDGET, int(raw.get("budget_probe") or 0))
        if floods or spent < was_budget * 0.9:
            return
        raised = min(_BUDGET_PROBE_MAX, int(was_budget * _BUDGET_PROBE_UP))
        if raised > was_budget:
            self.budget_probe = raised
            log.warning(
                "telegram.budget_probed_up",
                was=was_budget,
                now=raised,
                spent_yesterday=spent,
                hint="сутки без единого флуда при выбранном бюджете — стена выше",
            )

    def _merge_bucket(self, raw: dict, spent_unflushed: int) -> None:
        """Взять ковш с диска, долить по времени, вычесть свой нескинутый расход.

        Диск — источник правды: там уже учтён расход соседнего процесса.
        Наша задача — только вычесть то, что потратили мы сами и ещё не
        записали.
        """
        now = time.time()
        cap = self.burst_capacity()
        disk_bucket = raw.get("bucket")
        disk_ts = float(raw.get("bucket_ts") or 0.0)
        if disk_bucket is None or not disk_ts:
            base = cap
        else:
            rate = self.daily_budget() / 86400.0
            base = min(cap, float(disk_bucket) + max(0.0, now - disk_ts) * rate)
        self.bucket = self._floor(min(cap, base - spent_unflushed))
        self.bucket_ts = now

    def _refill(self) -> None:
        now = time.time()
        cap = self.burst_capacity()
        if not self.bucket_ts:
            # Первый запуск: наливаем полный ковш. Пустой означал бы час
            # простоя на ровном месте после каждой установки.
            self.bucket, self.bucket_ts = cap, now
            return
        rate = self.daily_budget() / 86400.0
        self.bucket = min(cap, self.bucket + max(0.0, now - self.bucket_ts) * rate)
        self.bucket_ts = now

    def allowance(self) -> int:
        """Сколько обращений можно потратить прямо сейчас.

        Минимум из двух ограничений: суточного бюджета (защита от медленного
        перерасхода) и ковша (защита от залпа). Первое ловит «много за сутки»,
        второе — «много за минуту», и это разные аварии: 08.08 нас убило
        именно второе.
        """
        self._refill()
        return max(0, int(min(self.bucket, self.budget_left())))

    def note_flood(self, request_name: str, seconds: int) -> bool:
        """Записать флуд. Возвращает True, если он «суточный», а не заминка."""
        hard = seconds > _HARD_FLOOD_SEC
        if hard:
            self.hard_floods[request_name] = self.hard_floods.get(request_name, 0) + 1
            self._delta_hard[request_name] = self._delta_hard.get(request_name, 0) + 1
            # Калибровка потолка: на этом расходе Telegram сказал «хватит».
            # Берём минимум из наблюдений — стена могла быть и ниже.
            #
            # Нижняя граница обязательна. Один аномальный флуд (сетевой сбой,
            # чужой процесс, выданный не за то) уронил бы потолок до десятков
            # запросов в сутки — и обход тихо перестал бы собирать, продолжая
            # выглядеть работающим. Это ровно та «невидимая потеря», из-за
            # которой неделю считали ленту по 2% собранного.
            spent = self.total()
            if spent >= _CEILING_MIN and (not self.ceiling_at or spent < self.ceiling_at):
                previous = self.ceiling_at
                self.ceiling_at = spent
                self.ceiling_day = self.day
                log.warning(
                    "telegram.ceiling_calibrated",
                    was=previous or None,
                    now=spent,
                    daily_budget=int(spent * _CEILING_SAFETY),
                    request=request_name,
                )
            elif spent < _CEILING_MIN:
                log.warning(
                    "telegram.ceiling_ignored",
                    spent=spent,
                    floor=_CEILING_MIN,
                    hint="суточный флуд на подозрительно малом расходе — калибровку не приняли",
                )
        else:
            self.soft_floods[request_name] = self.soft_floods.get(request_name, 0) + 1
            self._delta_soft[request_name] = self._delta_soft.get(request_name, 0) + 1
            self.soft_flood_seconds[request_name] = (
                self.soft_flood_seconds.get(request_name, 0) + seconds
            )
            self._delta_soft_sec[request_name] = (
                self._delta_soft_sec.get(request_name, 0) + seconds
            )
        self.flush()
        return hard

    # ── показания ────────────────────────────────────────────────────

    def total(self) -> int:
        return sum(self.requests.values())

    def soft_total(self) -> int:
        return sum(self.soft_floods.values())

    def hard_total(self) -> int:
        return sum(self.hard_floods.values())

    def daily_budget(self) -> int:
        """Сколько обращений считаем допустимыми за сутки.

        Замеренный потолок бьёт умолчание: константа — это догадка, а
        `ceiling_at` — число, на котором Telegram действительно остановил.
        """
        if self.ceiling_at:
            # Замеренная стена бьёт всё: подъём прекращается, как только
            # Telegram показал, где предел.
            return max(_PACE_MIN_CHANNELS, int(self.ceiling_at * _CEILING_SAFETY))
        return max(_DEFAULT_DAILY_BUDGET, self.budget_probe)

    def budget_left(self) -> int:
        return max(0, self.daily_budget() - self.total())

    def summary(self) -> dict:
        return {
            "day": self.day,
            "requests_total": self.total(),
            "budget": self.daily_budget(),
            "budget_left": self.budget_left(),
            "allowance_now": self.allowance(),
            "burst_capacity": int(self.burst_capacity()),
            "soft_floods": self.soft_total(),
            "hard_floods": self.hard_total(),
            "ceiling_at": self.ceiling_at or None,
            "by_request": dict(sorted(self.requests.items(), key=lambda kv: -kv[1])[:6]),
        }


# Один счётчик на процесс: прогон короткий, а передавать его через пять
# уровней вызовов ради чистоты — дороже, чем модульная переменная.
_meter: ApiMeter | None = None


def meter() -> ApiMeter:
    global _meter
    if _meter is None:
        _meter = ApiMeter.load()
    return _meter


def reset_meter() -> None:
    """Забыть счётчик, чтобы он перечитался.

    Нужно в двух местах, и оба настоящие: в тестах между случаями и в начале
    прогона, когда выбран аккаунт. Счётчик привязан к файлу, а файл — к
    аккаунту; не сбросив его, второй аккаунт списывал бы расход с первого.
    """
    global _meter
    _meter = None


# ── Приёмник предупреждений Telethon ─────────────────────────────────


class _FloodCaptureHandler(logging.Handler):
    """Ловит «Sleeping for Ns on X flood wait» и делает из него число.

    Читаем `record.args`, а не разобранный текст: Telethon формирует запись
    как ``log.info(*_fmt_flood(...))``, то есть аргументы приходят
    неотформатированными — `(early, seconds, timedelta, ИмяЗапроса)`
    (`telethon/client/users.py:18`). Парсить готовую строку значило бы
    зависеть от формулировки; аргументы стабильнее.

    Если формат всё же изменится — молча ничего не сломаем: обработчик
    защищён и в худшем случае просто не запишет флуд.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            args = record.args
            if not (isinstance(args, tuple) and len(args) == 4):
                return
            if "flood wait" not in str(record.msg):
                return
            early, seconds, _td, request_name = args
            seconds = int(seconds)
            name = str(request_name)
            hard = meter().note_flood(name, seconds)
            log.warning(
                "telegram.flood",
                request=name,
                seconds=seconds,
                hard=hard,
                early=bool(early),
                spent_today=meter().total(),
                hint="мелкий флуд — предупреждение, не авария",
            )
        except Exception:  # noqa: BLE001 — телеметрия не должна ронять обход
            pass


_logging_installed = False


def install_telethon_logging() -> None:
    """Включить приёмник. Поведение обхода не меняется — только видимость.

    Уровень INFO ставим **точечно** на `telethon.client.users`, а не на весь
    `telethon`: остальные его логгеры на INFO пишут о каждом переподключении
    и утопили бы сигнал в шуме. Ровно тот логгер, где живут флуды, — и всё.
    """
    global _logging_installed
    if _logging_installed:
        return
    tl = logging.getLogger("telethon.client.users")
    tl.setLevel(logging.INFO)
    tl.addHandler(_FloodCaptureHandler(level=logging.INFO))
    # propagate оставляем: пусть строка дойдёт и до общего лога, если его
    # когда-нибудь настроят. Дублирования нет — корневой логгер INFO не берёт.
    _logging_installed = True


# ── Обёртка счётчика вокруг единственной воронки запросов ────────────


def _instrument_sender(sender, m: ApiMeter) -> None:  # noqa: ANN001 — MTProtoSender
    """Считать КАЖДУЮ отправку, включая повторы Telethon.

    Почему не на уровне `_call`, как было сначала. `_call` — это одна попытка
    с точки зрения вызывающего, но внутри него живёт цикл
    `for attempt in retry_range(self._request_retries)`: после мелкого флуда
    или серверной ошибки запрос уходит в сеть **снова**, не выходя наружу.
    Счётчик на `_call` эти повторы не видел — то есть занижал расход, и
    занижал в самую опасную сторону: мы думали, что потратили меньше, и
    тратили больше.

    `sender.send` — последняя точка перед сетью, мимо неё не проходит ничто.
    Обёртка синхронная: `send` возвращает `Future`, а не корутину
    (`network/mtprotosender.py:154`), и делать её async значило бы сломать
    вызывающий код.
    """
    if getattr(sender, "_openclaw_counted", False):
        return

    original_send = sender.send

    def counting_send(request, ordered=False):  # noqa: ANN001
        for r in request if isinstance(request, list) else [request]:
            m.bump(type(r).__name__)
        return original_send(request, ordered=ordered)

    sender.send = counting_send
    sender._openclaw_counted = True


def instrument_client(client) -> None:  # noqa: ANN001 — telethon.TelegramClient
    """Считать каждое обращение к Telegram.

    Врезка в двух местах, и обе нужны:

    * `sender.send` — считает реальные отправки, включая повторы внутри
      `_call`. Отправитель берём из аргумента `_call`, а не из клиента:
      загрузки файлов ходят через **экспортированный** отправитель другого
      датацентра (`client/downloads.py:60`), и счётчик на `client._sender`
      пропустил бы самую дорогую статью расхода целиком.
    * сам `_call` — ловит FloodWait, который вышел наружу (суточный), чтобы
      записать его вместе с расходом, на котором он случился.

    Обёртка на экземпляре, а не на классе: два клиента в одном процессе
    (основной и `check_dead` со своей сессией) не должны считать друг за друга.
    """
    if getattr(client, "_openclaw_instrumented", False):
        return
    original = client._call
    m = meter()

    async def counting_call(sender, request, *args, **kwargs):  # noqa: ANN001
        _instrument_sender(sender, m)
        try:
            return await original(sender, request, *args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            seconds = getattr(exc, "seconds", None)
            if seconds is not None and "Flood" in type(exc).__name__:
                first = request[0] if isinstance(request, list) and request else request
                m.note_flood(type(first).__name__, int(seconds))
            raise

    client._call = counting_call
    client._openclaw_instrumented = True


# ── Самокалибрующийся темп ───────────────────────────────────────────


@dataclass
class Pace:
    """Сколько каналов за прогон и с какой паузой между обращениями.

    Правило одно: **вверх осторожно, вниз резко**. Пропущенный канал стоит
    задержки в сборе, лишний запрос — суток простоя и, при накоплении
    страйков, до 96 часов. Асимметрия цены задаёт асимметрию шагов
    (AGENT_RULES §5, здесь она в другую сторону, чем обычно).
    """

    channels_per_run: int = _PACE_START_CHANNELS
    interval_sec: float = _PACE_START_INTERVAL

    @classmethod
    def load(cls) -> Pace:
        raw = read_json(_PACE_FILENAME)
        p = cls()
        try:
            if raw.get("channels_per_run"):
                p.channels_per_run = int(raw["channels_per_run"])
            if raw.get("interval_sec"):
                p.interval_sec = float(raw["interval_sec"])
        except Exception:  # noqa: BLE001
            return cls()
        return p.clamped()

    def clamped(self) -> Pace:
        self.channels_per_run = max(
            _PACE_MIN_CHANNELS, min(_PACE_MAX_CHANNELS, self.channels_per_run),
        )
        self.interval_sec = max(
            _PACE_MIN_INTERVAL, min(_PACE_MAX_INTERVAL, self.interval_sec),
        )
        return self

    def save(self) -> None:
        write_json(
            _PACE_FILENAME,
            {"channels_per_run": self.channels_per_run, "interval_sec": self.interval_sec},
        )

    def after_run(self, *, soft_floods: int, hard_flood: bool) -> Pace:
        """Новый темп по исходу прогона."""
        if hard_flood:
            self.channels_per_run = int(self.channels_per_run * 0.5)
            self.interval_sec *= 2.0
        elif soft_floods:
            # Мелкий флуд — это и есть найденная стена. Отходим от неё, не
            # дожидаясь суточной: именно ради этого сигнал и включён.
            self.channels_per_run = int(self.channels_per_run * 0.8)
            self.interval_sec *= 1.5
        else:
            self.channels_per_run = max(
                self.channels_per_run + 1, int(self.channels_per_run * 1.1),
            )
            self.interval_sec *= 0.9
        return self.clamped()
