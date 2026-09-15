"""mutation_journal — кто и когда менял данные массово.

## Зачем

29.08 владелец не смог вспомнить, что обновило 47 460 вакансий за день. И это
был ВТОРОЙ такой случай: 15.08 — 1 создана / 46 354 изменено, разбор занял
полсессии и закончился реконструкцией по mtime файла
(`ops/setup/apply_session_2026_08_14.command`), потому что в git за те пять
недель не было ни одного коммита. Причину нашли, но только потому, что
скрипт случайно уцелел на диске.

Массовая правка сама по себе нормальна. Ненормально, что она не оставляет
следа: `updated_at` у четверти таблицы переписывается, и любой замер вида
«до и после» после этого врёт, а понять, чем именно, нельзя.

## Что это

Append-only журнал в `analysis/mutations/YYYY-MM.jsonl`. Одна строка на одну
массовую запись: что за скрипт, с какими аргументами, какая таблица, сколько
строк, когда. Файл, а не таблица в БД: журнал должен пережить и восстановление
из бэкапа, и потерю базы — он про то, ЧТО с базой делали.

## Как пользоваться

    import sys; sys.path.insert(0, "/Users/dmitrij/recruit/ops/lib")
    from mutation_journal import record, journal

    # либо явно, когда число строк уже известно:
    record(table="vacancies", rows=50222, note="salary base --recompute")

    # либо контекстом — тогда запись останется даже при падении:
    with journal(table="vacancies", note="salary base --recompute") as j:
        ...
        j.rows = updated

Модуль на голой стандартной библиотеке и НИЧЕГО не импортирует из проекта:
его подключают по файловому пути скрипты из разных venv (у openclaw свой, с
бэкендом не общий).

## Порог

По умолчанию пишутся только правки от `MIN_ROWS` строк. Журнал существует
ради массовых событий; одиночные правки утопили бы его в шуме. Порог можно
снять явным `min_rows=0`.
"""

from __future__ import annotations

import json
import os
import socket
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

# datetime.UTC появился только в 3.11. Модуль подключают по файловому пути
# скрипты из разных venv (у openclaw свой), и системный python бывает 3.10 —
# журнал не имеет права падать на импорте.
UTC = timezone.utc

ROOT = Path(__file__).resolve().parents[2]
JOURNAL_DIR = ROOT / "analysis" / "mutations"
MIN_ROWS = 500


def _script_name() -> str:
    """Имя запустившего скрипта — или честное «не знаю».

    В ops/ python почти всегда запускается heredoc'ом (`python3 - <<PY`), и
    тогда argv[0] это "-", а не путь. Такой фолбэк молча записал бы в журнал
    прочерк вместо имени, поэтому heredoc-вызовы обязаны передавать `script=`
    явно, а здесь остаётся видимая заглушка.
    """
    raw = sys.argv[0] if sys.argv else ""
    if raw in ("", "-", "-c"):
        return "(stdin: передайте script=)"
    return Path(raw).name


def _entry(table: str, rows: int, note: str, script: str | None, extra: dict | None) -> dict:
    return {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "script": script or _script_name(),
        "argv": sys.argv[1:],
        "table": table,
        "rows": rows,
        "note": note,
        "host": socket.gethostname(),
        "user": os.environ.get("USER", ""),
        **(extra or {}),
    }


def record(
    *, table: str, rows: int, note: str = "", script: str | None = None,
    min_rows: int = MIN_ROWS, extra: dict | None = None,
) -> None:
    """Записать одну массовую правку. Никогда не роняет вызывающего.

    Журнал — вспомогательный: если писать не удалось, скрипт обязан
    продолжить работу. Молчать при этом нельзя — иначе журнал «работает»
    ровно до дня, когда понадобится (AGENT_RULES §14).
    """
    if rows < min_rows:
        return
    try:
        JOURNAL_DIR.mkdir(parents=True, exist_ok=True)
        path = JOURNAL_DIR / f"{datetime.now(UTC):%Y-%m}.jsonl"
        line = json.dumps(_entry(table, rows, note, script, extra), ensure_ascii=False)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        count = "строк неизвестно" if (extra or {}).get("rows_unknown") else f"{rows} строк"
        print(f"  ▸ журнал правок: {count} в `{table}` → {path.name}")
    except Exception as exc:  # noqa: BLE001
        print(f"  ⚠ НЕ СМОГ записать журнал правок ({type(exc).__name__}: {exc}).")
        print(f"    Правка сделана, следа не осталось. Записать руками: {table}, {rows} строк.")


class _Journal:
    def __init__(self) -> None:
        self.rows = 0


@contextmanager
def journal(*, table: str, note: str = "", script: str | None = None, min_rows: int = MIN_ROWS):
    """Контекст: запись останется даже если тело упало на полпути.

    Упавший массовый прогон опаснее успешного — он оставляет базу в
    промежуточном состоянии, и именно его потом невозможно опознать.
    """
    j = _Journal()
    started = time.time()
    failure: str | None = None
    try:
        yield j
    except BaseException as exc:
        failure = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        extra = {"seconds": round(time.time() - started, 1)}
        if failure is None:
            record(
                table=table, rows=j.rows, note=note, script=script,
                min_rows=min_rows, extra=extra,
            )
        else:
            # Порог здесь не применяем. Упавший прогон обычно не успевает
            # выставить j.rows, и по порогу запись бы молча исчезла — то есть
            # ровно то событие, ради которого журнал заведён, следа бы не
            # оставило. Число строк тут не «0», а «неизвестно».
            extra["failed"] = failure
            if not j.rows:
                extra["rows_unknown"] = True
            record(
                table=table, rows=j.rows, note=note or "(прогон упал)",
                script=script, min_rows=0, extra=extra,
            )
