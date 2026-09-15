"""Файлы состояния рядом с сессией Telethon.

Почему рядом с сессией, а не в `data/`: их читает не только Python, но и
`ops/pipeline/openclaw_loop.sh` (метка паузы) и человек глазами при разборе
аварии. Один каталог на всё состояние обхода — чтобы «где посмотреть» не
приходилось вспоминать.

Раньше эти четыре функции жили внутри `watch_channels.py`. Вынесены сюда,
когда состояние понадобилось второму модулю (`telemetry.py`): копия помощника
рано или поздно разошлась бы с оригиналом, а расхождение проявилось бы не
ошибкой, а тем, что два модуля читают разные файлы (AGENT_RULES §7).
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import structlog

from kernel.config import settings

log = structlog.get_logger()


# ── Разделение состояния между аккаунтами ────────────────────────────
#
# У каждого аккаунта своя пауза, свой счётчик, свой темп и свои смещения.
# Общие файлы означали бы, что бан одного останавливает другого, а расход
# одного списывается со второго — то есть второй аккаунт не добавлял бы
# ничего, кроме иллюзии.
#
# У аккаунта по умолчанию суффикса нет: иначе обновление кода «потеряло» бы
# накопленные offsetы и пересобрало ленту с нуля.
_suffix = ""
_base_dir: Path | None = None


def use_account(account) -> None:  # noqa: ANN001 — accounts.Account, импорт был бы круговым
    """Переключить служебные файлы на этот аккаунт. Зовётся один раз за прогон."""
    global _suffix, _base_dir
    _suffix = account.side_suffix()
    _base_dir = Path(account.session_path).expanduser().resolve().parent


def side_file(name: str) -> Path:
    """Служебный файл рядом с файлом сессии Telethon."""
    directory = _base_dir or Path(settings().tg_session_path).expanduser().resolve().parent
    if not _suffix:
        return directory / name
    stem, dot, ext = name.rpartition(".")
    # `.watch_pace.json` → `.watch_pace.b.json`, а `.watch_rotation_offset`
    # (без расширения) → `.watch_rotation_offset.b`.
    return directory / (f"{stem}{_suffix}{dot}{ext}" if stem else f"{name}{_suffix}")


def today() -> str:
    """Сутки в UTC.

    Именно UTC, а не локальное время: FloodWait от Telegram привязан к его
    суткам, и счётчик, который переворачивается в московскую полночь, показывал
    бы расход не за то окно, за которое нас лимитируют.
    """
    return time.strftime("%Y-%m-%d", time.gmtime())


def read_int(name: str, default: int = 0) -> int:
    try:
        return int(side_file(name).read_text().strip())
    except Exception:
        return default


def write_int(name: str, value: int) -> None:
    try:
        side_file(name).write_text(str(int(value)))
    except Exception as exc:  # noqa: BLE001
        log.warning("sidefile.write_failed", file=name, err=str(exc))


# ── Пауза сбора ──────────────────────────────────────────────────────
#
# Живёт здесь, а не в `watch_channels`, потому что читать её должен и клиент
# Telegram — иначе получается круговой импорт. Перепроверка 09.08 нашла, что
# из пяти скиллов, открывающих клиент, паузу спрашивали только два: `discover`
# и `discover_keyword_search` шли в Telegram под активным баном.
PAUSE_FILENAME = ".watch_paused_until"
PAUSE_MARGIN_SEC = 60  # запас поверх запрошенного Telegram ожидания


def pause_remaining_sec() -> int:
    """Сколько секунд ещё длится пауза (0 — паузы нет / метка протухла|битая)."""
    try:
        return max(0, int(side_file(PAUSE_FILENAME).read_text().strip()) - int(time.time()))
    except Exception:
        return 0


def set_pause(seconds: int) -> None:
    """Отложить сбор на ``seconds`` (best-effort: не смогли записать — не падаем)."""
    try:
        side_file(PAUSE_FILENAME).write_text(str(int(time.time()) + max(0, seconds)))
    except Exception as exc:  # noqa: BLE001
        log.warning("watch.pause_write_failed", err=str(exc))


def read_json(name: str, default: dict | None = None) -> dict:
    try:
        data = json.loads(side_file(name).read_text())
        return data if isinstance(data, dict) else dict(default or {})
    except Exception:
        return dict(default or {})


def write_json(name: str, data: dict) -> None:
    """Запись через временный файл.

    Прямая запись рвёт файл, если процесс убьют посередине, — а убивают тут
    регулярно (`pkill -f openclaw_loop.sh` в инструкции по локу сессии).
    Битый JSON счётчика читался бы как «расход ноль», то есть отключал бы
    защиту ровно в тот момент, когда она нужнее всего.
    """
    try:
        path = side_file(name)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False))
        tmp.replace(path)
    except Exception as exc:  # noqa: BLE001
        log.warning("sidefile.write_failed", file=name, err=str(exc))
