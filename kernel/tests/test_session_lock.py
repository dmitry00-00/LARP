"""Один процесс на файл сессии Telegram.

Авария 31.07: в логе openclaw — `database is locked` внутри
`_save_states_and_entities`, то есть падала запись **кэша сущностей**.
Кэш — единственное, что спасает от FloodWait (закэшированный канал не
стоит резолва), поэтому каждый прогон резолвил заново и снова получал
сутки бана. «Лок сессии» и «вечный FloodWait» оказались одной аварией,
а не двумя.

WAL тут не помогает: он разводит читателей и писателя, но двух писателей
не мирит. `busy_timeout` тоже не спасает — это свойство соединения, а
соединение Telethon открывает сам.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile

import pytest

from kernel.clients.telegram import TelegramClient


def _hold_lock_in_subprocess(lock_path: str) -> subprocess.Popen:
    """Держим flock из ДРУГОГО процесса: flock внутри одного процесса
    переиспользуется и конфликта бы не дал — тест бы прошёл вхолостую."""
    code = (
        "import fcntl,sys,time\n"
        f"fh=open({lock_path!r},'a+')\n"
        "fcntl.flock(fh.fileno(), fcntl.LOCK_EX)\n"
        "fh.seek(0); fh.truncate(); fh.write('99999'); fh.flush()\n"
        "sys.stdout.write('locked\\n'); sys.stdout.flush()\n"
        "time.sleep(30)\n"
    )
    p = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True,
    )
    assert p.stdout is not None
    assert p.stdout.readline().strip() == "locked"
    return p


def test_second_process_is_refused_with_useful_message():
    with tempfile.TemporaryDirectory() as tmp:
        session = os.path.join(tmp, "openclaw.session")
        open(session, "a").close()
        holder = _hold_lock_in_subprocess(f"{session}.lock")
        try:
            client = TelegramClient()
            with pytest.raises(RuntimeError) as exc:
                client._lock_session(session)
            msg = str(exc.value)
            # Не просто «занято»: сообщение обязано объяснить ПОЧЕМУ
            # параллельный обход вреден, иначе его обойдут флагом.
            assert "99999" in msg                    # кто держит
            assert "лимит резолвов" in msg.lower()   # почему нельзя
            assert "pkill" in msg                    # что делать
        finally:
            holder.kill()
            holder.wait(timeout=5)


def test_lock_released_lets_next_process_in():
    """Лок не должен переживать процесс — иначе kill -9 навсегда
    заблокировал бы сбор, и чинить пришлось бы руками."""
    with tempfile.TemporaryDirectory() as tmp:
        session = os.path.join(tmp, "openclaw.session")
        open(session, "a").close()

        holder = _hold_lock_in_subprocess(f"{session}.lock")
        holder.kill()
        holder.wait(timeout=5)

        client = TelegramClient()
        client._lock_session(session)          # не должно бросить
        assert client._lock_fh is not None
        client._lock_fh.close()


def test_lock_file_holds_pid():
    with tempfile.TemporaryDirectory() as tmp:
        session = os.path.join(tmp, "openclaw.session")
        open(session, "a").close()
        client = TelegramClient()
        client._lock_session(session)
        try:
            with open(f"{session}.lock") as fh:
                assert fh.read().strip() == str(os.getpid())
        finally:
            client._lock_fh.close()


def test_exclusive_false_skips_lock():
    """`check_dead_channels` работает с временной КОПИЕЙ сессии — ему лок
    основной не нужен и мешал бы."""
    client = TelegramClient(exclusive=False)
    assert client._exclusive is False
    assert client._lock_fh is None


def test_lock_is_a_separate_file_not_the_session():
    """flock вешаем на отдельный файл: на самом файле БД он мешал бы
    SQLite и мог бы выглядеть как повреждение сессии."""
    with tempfile.TemporaryDirectory() as tmp:
        session = os.path.join(tmp, "openclaw.session")
        open(session, "a").close()
        client = TelegramClient()
        client._lock_session(session)
        try:
            assert os.path.exists(f"{session}.lock")
            # сама сессия по-прежнему открывается на запись
            with open(session, "a") as fh:
                fh.write("")
            fcntl_ok = True
        finally:
            client._lock_fh.close()
        assert fcntl_ok
