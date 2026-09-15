"""Кто и когда переписал много строк — на уровне движка, а не скрипта.

## Зачем

Дважды за месяц массовая правка прошла без следа: 15.08 (46 354 вакансии) и
29.08 (47 460). Первую опознали по mtime случайно уцелевшего файла, вторую —
никак. Общее у них одно: правку сделал НЕ тот код, в который можно было бы
заранее вставить строчку журнала, потому что заранее неизвестно, какой это
будет код.

Поэтому крючок стоит на движке. Он не знает и не должен знать, какой скрипт
сегодня придумают: он видит любой UPDATE/DELETE/INSERT, прошедший через
`app.core.db.engine`.

## Чего он НЕ ловит — читать обязательно

Крючок видит `cursor.rowcount` ОДНОГО оператора. Отсюда две дыры:

1. **Не через этот движок.** `psql`, миграции Alembic на своём подключении,
   правки из pgAdmin, `openclaw` со своим engine. Для них следа не будет.
2. **Прямой SQL мимо ORM в другом процессе.** См. п.1.

Поштучные ORM-циклы (`backfill_salary_base` меняет строки по одной, rowcount=1)
крючок ловит НЕ мгновенной записью, а накоплением: счётчик по таблице растёт,
и при выходе процесса пишется одна итоговая строка. Поэтому в самих скриптах
явный `record()` всё равно полезен — он знает смысл правки, а крючок только
её размер.

Обещать «теперь всё записывается» нельзя. Записывается всё, что прошло через
этот движок (AGENT_RULES §14).

## Стоимость

На горячем пути — одно сравнение int и одно сложение. Разбор оператора и запись
в файл происходят только при rowcount >= MIN_ROWS, а такое в обычном запросе не
случается никогда.
"""

from __future__ import annotations

import atexit
import re
import sys
import threading
from collections import defaultdict
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine

# Журнал лежит в ops/lib: он намеренно не пакет и не импортирует ничего из
# `app` — его подключают по файловому пути скрипты из разных venv.
_OPS_LIB = Path(__file__).resolve().parents[2] / "ops" / "lib"
if str(_OPS_LIB) not in sys.path:
    sys.path.insert(0, str(_OPS_LIB))

try:
    from mutation_journal import MIN_ROWS
    from mutation_journal import record as _record
except Exception as _exc:  # noqa: BLE001
    print(f"⚠ журнал массовых правок не подключился ({type(_exc).__name__}: {_exc}) — "
          f"массовые правки НЕ будут записываться", file=sys.stderr)
    MIN_ROWS = 500

    def _record(**kw) -> None:  # type: ignore[misc]
        return None

_VERB = re.compile(r"^\s*(?:/\*.*?\*/\s*)?(update|delete|insert)\b", re.I | re.S)
_TABLE = re.compile(
    r"^\s*(?:/\*.*?\*/\s*)?(?:update\s+(?:only\s+)?|delete\s+from\s+|insert\s+into\s+)"
    r"[\"']?([a-z_][a-z0-9_.]*)[\"']?",
    re.I | re.S,
)

_lock = threading.Lock()
# Ключ — (таблица, глагол). Массовый INSERT (импорт 66k trudvsem) и массовый
# UPDATE — разные события; сложенные в одно число они лгут оба.
_totals: dict[tuple[str, str], int] = defaultdict(int)
_reported: dict[tuple[str, str], int] = defaultdict(int)  # из них записано мгновенно
_installed: set[int] = set()   # id(движка), а не один глобальный флаг
_flushed = False

# Кадр стека считаем «нашим», только если он ВНУТРИ репозитория и НЕ в venv.
# Проверка по подстроке "/app/" ловила бы site-packages на некоторых путях.
_REPO = str(Path(__file__).resolve().parents[2])
# Свои кадры пропускаем по ТОЧНОМУ пути файла, не по подстроке. Подстрока
# "mutation_audit" вычёркивала и tests/test_mutation_audit.py, и вычеркнула бы
# любой app/services/mutation_audit_*.py — то есть ровно того вызывающего,
# которого крючок должен назвать. Поймано прогоном на Маке 29.08.
_SELF = str(Path(__file__).resolve())


def _caller() -> str:
    """Ближайший кадр стека из кода проекта — он и называет виновника.

    Снимается только когда крючок уже решил писать, то есть редко.
    """
    try:
        f = sys._getframe(1)
        while f is not None:
            name = f.f_code.co_filename
            if (name != _SELF
                    and name.startswith(_REPO)
                    and "site-packages" not in name
                    and "/.venv/" not in name):
                rel = name[len(_REPO):].lstrip("/")
                return f"{rel}:{f.f_lineno} {f.f_code.co_name}"
            f = f.f_back
    except Exception:  # noqa: BLE001
        pass
    raw = Path(sys.argv[0]).name
    return raw if raw not in ("", "-", "-c") else "(кадр не опознан)"


def _flush() -> None:
    """Итог по процессу: накопленное поштучно, за вычетом мгновенных записей.

    Идемпотентен: atexit и явный вызов из теста не должны дать две строки
    об одном и том же событии — задвоённый журнал хуже пустого, потому что
    в него верят.
    """
    global _flushed
    with _lock:
        if _flushed:
            return
        _flushed = True
        pending = {k: n - _reported[k] for k, n in _totals.items()}
    for (table, verb), rows in pending.items():
        if rows >= MIN_ROWS:
            _record(
                table=table, rows=rows,
                note=f"накоплено за процесс: {verb} по одной строке",
                script=Path(sys.argv[0]).name or "(процесс)",
                extra={"kind": "rollup", "verb": verb},
            )


def install_listener(engine=None) -> None:
    """Повесить крючок. Без аргумента — на КЛАСС Engine, то есть на все движки.

    Ловить движки поимённо оказалось нельзя. В системе их как минимум три и
    создаются они в разных местах:
      • app/core/db.py            — бэкенд,
      • openclaw/clients/direct.py — прямой путь скрапера,
      • app/cli/scheduler.py       — по своему движку на каждую фоновую задачу.
    Список неполон по определению: следующий `create_async_engine` напишут
    завтра и про журнал не вспомнят — ровно так и появляется правка без следа.

    Поэтому слушаем класс `Engine`: событие ловится у любого движка процесса,
    включая созданные позже. Alembic попадает под крючок вместе со всеми, и
    это к лучшему — миграция с массовым UPDATE тоже должна оставлять след.
    """
    target = getattr(engine, "sync_engine", engine) if engine is not None else Engine

    # Крючок на классе уже покрывает КАЖДЫЙ движок процесса. Если он стоит,
    # установка на отдельный движок добавила бы ВТОРОГО слушателя на те же
    # события — каждый оператор посчитался бы дважды, и журнал завышал бы
    # размер правки вдвое. Тихо и правдоподобно: ровно тот сорт ошибки, из-за
    # которого числам перестают верить. Поймано тестами 29.08.
    if id(Engine) in _installed:
        return
    key = id(target)
    if key in _installed:
        return
    _installed.add(key)

    @event.listens_for(target, "after_cursor_execute")
    def _after(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        try:
            rows = cursor.rowcount
            if not rows or rows < 0:
                return
            mv = _VERB.match(statement)
            if not mv:
                return
            verb = mv.group(1).upper()
            m = _TABLE.match(statement)
            table = m.group(1) if m else "?"
            key = (table, verb)
            with _lock:
                _totals[key] += rows
                big = rows >= MIN_ROWS
                if big:
                    _reported[key] += rows
            if big:
                _record(
                    table=table, rows=rows,
                    note=f"один оператор: {verb}",
                    script=Path(sys.argv[0]).name or "(процесс)",
                    extra={
                        "kind": "statement",
                        "verb": verb,
                        "caller": _caller(),
                        "sql": " ".join(statement.split())[:400],
                        "executemany": bool(executemany),
                    },
                )
        except Exception:  # noqa: BLE001, S110
            # Аудит не имеет права уронить запрос. Молчим здесь намеренно:
            # об отказе самой ЗАПИСИ громко сообщает mutation_journal.record.
            pass

    atexit.register(_flush)
