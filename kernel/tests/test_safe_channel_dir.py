"""`_safe_channel_dir` — ник в имя каталога на HDD: без `@`, нижний регистр,
только ASCII, без `..`/`/`. Без этого коллизия с `..` или `/` открыла бы запись
в чужой каталог.

Тест жил в apps/backend/tests/test_inbox_attachment_path.py и падал там
ModuleNotFoundError: у бэкенда отдельный venv, openclaw в него не ставится
(AGENT_RULES §7). Функция — openclaw'а, значит её место здесь, где openclaw
импортируется. telethon для импорта не нужен: он тянется лениво, не на уровне
модуля.
"""

from kernel.clients.telegram import _safe_channel_dir


def test_safe_channel_dir_normalizes_handle() -> None:
    assert _safe_channel_dir("@RU_PythonJobs") == "ru_pythonjobs"
    assert _safe_channel_dir("../etc/passwd") == "etcpasswd"
    assert _safe_channel_dir("") == "_"
    assert _safe_channel_dir("плохой ник") == "_", (
        "кириллицу тоже режем: путь на HDD — ASCII, иначе разные ФС дают "
        "разное поведение"
    )
