"""Telegram MTProto wrapper. Mockable: when ``OPENCLAW_MOCK_TELEGRAM`` is
true the client returns an empty message list so the rest of the
pipeline can run end-to-end against a stubbed Telegram.
"""

import io
import os
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import structlog

from kernel import sidefiles, telemetry
from kernel.config import settings

log = structlog.get_logger()

# MIME types we know how to extract text from
_SUPPORTED_MIMES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/msword",  # .doc (best-effort via python-docx)
}

# Расширение файла для сохранения — из MIME, потому что имя из Telegram
# приходит как `document_2025_08.pdf` или вовсе без него, и полагаться на него
# нельзя: тот же PDF от разных клиентов приходит с разными подсказками.
_MIME_EXT = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "application/msword": "doc",
}

# Корень внешнего HDD для байтов вложений. Пустая строка = писать не куда,
# работаем как прежде (только текст). Задаётся `ATTACHMENT_ROOT`.
# В `.env` писать АБСОЛЮТНЫЙ путь: `~` и `$HOME` шеллом не раскрываются
# (AGENT_RULES §9 — уже наступали ровно на это).
_ATTACHMENT_ROOT = os.environ.get("ATTACHMENT_ROOT", "").strip()

# Регекс безопасного имени папки: канал в качестве компоненты пути. Символы
# вне `[a-z0-9_-]` вырезаем, регистр — нижний. Без экранирования Telegram-ник
# теоретически может содержать спецсимволы: коллизия с `..` или `/` открыла
# бы запись в чужой каталог.
_SAFE_HANDLE = re.compile(r"[^a-z0-9_-]+")


def _safe_channel_dir(handle: str) -> str:
    """`@RU_PythonJobs` → `ru_pythonjobs`. Возвращает `_` для пустых имён,
    чтобы файл всё равно оказался где-то, а не потерялся."""
    cleaned = _SAFE_HANDLE.sub("", (handle or "").lstrip("@").lower())
    return cleaned or "_"


def _save_attachment(
    doc_bytes: bytes, handle: str, msg_id: int, mime: str,
) -> str | None:
    """Записать байты вложения на HDD, вернуть абсолютный путь.

    Пустой корень или ошибка записи → None, работа продолжается: байты уже
    прочитаны и текст извлечён; отсутствие файла на диске — не повод терять
    пост (AGENT_RULES §5). Ошибку пишем строкой в лог — иначе провал был бы
    невидим и «отставание HDD» лечили бы гаданием.
    """
    if not _ATTACHMENT_ROOT:
        return None
    ext = _MIME_EXT.get(mime, "bin")
    try:
        target = Path(_ATTACHMENT_ROOT) / _safe_channel_dir(handle) / f"{msg_id}.{ext}"
        target.parent.mkdir(parents=True, exist_ok=True)
        # `wb` перезаписывает: если файл уже был (повторный обход), это
        # обновление, а не дубль. Дубли отслеживаются идемпотентностью
        # `inbox_items`, а не файловой системой.
        target.write_bytes(doc_bytes)
        return str(target)
    except OSError as exc:
        log.warning(
            "attachment.save_failed",
            handle=handle, msg_id=msg_id, root=_ATTACHMENT_ROOT, err=str(exc),
        )
        return None


@dataclass
class TelegramMessage:
    id: int
    text: str
    date: datetime
    raw_html: str | None = None
    document_bytes: bytes | None = field(default=None, repr=False)
    document_mime: str | None = None
    # Путь к сохранённому файлу вложения на HDD, если запись удалась.
    # Прокидывается до `upsert_inbox_item` → `inbox_items.attachment_path`.
    attachment_path: str | None = None
    # URL'ы, которых НЕТ в тексте: цели гиперссылок и inline-кнопок.
    # См. extract_hidden_urls — без них у каналов-бордов контакт теряется.
    hidden_urls: list[str] = field(default_factory=list)


def _log_skipped_attachment(handle: str, msg, reason: str) -> None:  # noqa: ANN001
    """Пропущенная загрузка — отдельной строкой, а не молча.

    Молчаливый пропуск здесь опаснее лишней строки: текст поста сохранится,
    и запись будет выглядеть полноценной, хотя резюме лежало в файле. Без
    этой строки потеря была бы невидима — тот же класс, что «счётчик считал
    несозданные записи» (§L, 07.08).

    Причина обязательна и различима: «старо» — это норма при догоне, а
    «бюджет» — признак, что вложений в ленте больше, чем квоты, и решать это
    надо весом или вторым транспортом, а не молчанием.
    """
    log.info(
        "watch.attachment_skipped",
        handle=handle,
        msg_id=getattr(msg, "id", None),
        date=str(getattr(msg, "date", "")),
        size=getattr(getattr(msg, "document", None), "size", None),
        reason=reason,
    )


def extract_hidden_urls(msg) -> list[str]:  # noqa: ANN001 — telethon Message или стаб
    """URL'ы сообщения, которых нет в ``msg.message``.

    Зачем. `msg.message` — это ПЛОСКИЙ текст. Всё, что в Telegram живёт
    разметкой, в нём отсутствует:

    * гиперссылка (`MessageEntityTextUrl`) — в тексте остаётся слово
      «Откликнуться», а адрес лежит в сущности;
    * inline-кнопка (`KeyboardButtonUrl`) — в тексте её нет вообще.

    Именно поэтому замер 25.07 показал у каналов-бордов (`@aldaba_rd`,
    `@robotaua_now_*`) **0% контактов** при постах на 400 символов: это
    автопостинг, где «Відправити резюме» — кнопка, а не текст. Парсер
    контактов честно не находил ничего, потому что в базе ничего и не было.

    Читаем через ``getattr``, а не через импорт telethon-типов: в mock-режиме
    и в тестах сюда приходят простые стабы, и хардовый импорт сделал бы
    функцию непроверяемой без секретов Telegram.
    """
    urls: list[str] = []
    text = getattr(msg, "message", "") or ""

    def add(u: str | None) -> None:
        if not u or not isinstance(u, str):
            return
        u = u.strip()
        # Уже есть в тексте — не дублируем: парсеру всё равно, а человеку,
        # который откроет raw_text, лишний хвост мешает.
        if u and u not in text and u not in urls:
            urls.append(u)

    for e in getattr(msg, "entities", None) or []:
        add(getattr(e, "url", None))

    markup = getattr(msg, "reply_markup", None)
    for row in getattr(markup, "rows", None) or []:
        for btn in getattr(row, "buttons", None) or []:
            add(getattr(btn, "url", None))
    return urls


class TelegramClient:
    """Lazy wrapper around telethon. Construction is cheap; ``connect``
    is what actually talks to Telegram, so unit tests can instantiate
    this without secrets.

    Pass ``session_path`` to override the default session file — useful
    when a secondary process needs to connect without locking the main
    session (e.g. check_dead_channels running while the stream is up).
    """

    def __init__(
        self,
        *,
        session_path: str | None = None,
        exclusive: bool = True,
        ignore_limits: bool = False,
    ) -> None:
        cfg = settings()
        self._mock = cfg.openclaw_mock_telegram
        self._client = None
        self._session_path = session_path  # None → use cfg default
        self._exclusive = exclusive
        # ``ignore_limits`` — только для авторизации и ручной диагностики.
        # Всё остальное обязано спрашивать разрешения: см. _check_limits.
        self._ignore_limits = ignore_limits
        self._lock_fh = None

    def _check_limits(self) -> None:
        """Не открывать соединение под баном или без бюджета.

        Замок стоит на двери, а не в каждой комнате. Перепроверка 09.08
        показала почему: клиент открывают пять скиллов, паузу спрашивали
        двое, бюджет — никто. `discover` и `discover_keyword_search` ходили
        в Telegram под активным FloodWait, а `check_dead` резолвит каждый
        канал **временной сессией** — то есть без кэша, самой дорогой ценой
        из возможных. Забыть проверку в новом скилле теперь нельзя: соединение
        просто не откроется.

        `watch_channels` до этой стены не доходит — он спрашивает бюджет сам
        и выходит с нулём, чтобы не превращать штатное «на сегодня хватит» в
        аварию в логе.
        """
        if self._ignore_limits:
            return
        remaining = sidefiles.pause_remaining_sec()
        if remaining > 0:
            raise RuntimeError(
                f"Telegram на паузе ещё {remaining // 60} мин (FloodWait). "
                f"Соединение не открыто намеренно: обращение под активным баном "
                f"продлевает его. Разбор очереди в Telegram не ходит — "
                f"ops/pipeline/ingest_once.command --no-watch",
            )
        if telemetry.meter().allowance() <= 0:
            s = telemetry.meter().summary()
            raise RuntimeError(
                f"Суточный бюджет обращений к Telegram исчерпан "
                f"({s['requests_total']} из {s['budget']}). "
                f"Состояние: ops/check/watch_state.command",
            )

    def _lock_session(self, session_file: str) -> None:
        """Один процесс на файл сессии — иначе теряется кэш сущностей.

        Почему отказ, а не ожидание: конкуренты здесь — не короткие
        транзакции, а долгие обходы каналов. Второму процессу правильнее
        сразу сказать «занято», чем висеть неизвестно сколько, тем более
        что **лимит резолвов у Telegram общий на аккаунт** — параллельная
        работа не ускоряет, а только делит одну квоту и приближает бан.

        Лок — отдельный файл рядом с сессией (не сама сессия): flock на
        БД-файле мешал бы SQLite. Освобождается автоматически при смерти
        процесса, поэтому забытый лок после kill -9 невозможен.
        """
        import fcntl
        import os

        lock_path = f"{session_file}.lock"
        fh = open(lock_path, "a+")  # noqa: SIM115 — держим до __aexit__
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.seek(0)
            holder = (fh.read() or "").strip() or "неизвестен"
            fh.close()
            raise RuntimeError(
                f"Сессию Telegram уже держит другой процесс (pid {holder}). "
                f"Лимит резолвов общий на аккаунт — параллельный обход только "
                f"приближает FloodWait. Дождись его завершения или останови: "
                f"pkill -f openclaw_loop.sh",
            ) from None
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        self._lock_fh = fh

    async def __aenter__(self) -> "TelegramClient":
        if self._mock:
            return self
        self._check_limits()
        from telethon import TelegramClient as _TC

        cfg = settings()
        if cfg.tg_api_id is None or not cfg.tg_api_hash:
            raise RuntimeError("TG_API_ID / TG_API_HASH not configured")
        session = self._session_path or str(cfg.tg_session_path)

        # WAL: много читателей + один писатель одновременно. Этого мало —
        # WAL разводит чтение и запись, но ДВА писателя всё равно
        # конфликтуют, а второй по умолчанию сдаётся мгновенно.
        #
        # Чем это обошлось (лог 31.07): `database is locked` вылетал в
        # `_save_states_and_entities` на дисконнекте — то есть падала
        # запись КЭША СУЩНОСТЕЙ. А кэш — единственное, что спасает от
        # FloodWait: закэшированный канал не стоит ни одного резолва.
        # Каждый прогон резолвил заново и снова нарывался на бан. Лок
        # сессии и «вечный FloodWait» оказались одной аварией.
        #
        # Настроить это ПРАГМОЙ нельзя: `journal_mode` — персистентное
        # свойство файла (ставим один раз, живёт дальше), а `busy_timeout` —
        # свойство СОЕДИНЕНИЯ, и на соединение, которое Telethon откроет
        # сам, наша установка не распространяется. Поэтому единственное
        # честное средство — не пускать второго писателя: см. `_lock_session`.
        import sqlite3 as _sqlite3
        _session_file = f"{session}.session" if not session.endswith(".session") else session
        try:
            _conn = _sqlite3.connect(_session_file)
            _conn.execute("PRAGMA journal_mode=WAL")
            _conn.close()
        except Exception:  # noqa: BLE001
            pass  # best-effort — don't break startup if file doesn't exist yet

        if self._exclusive:
            self._lock_session(_session_file)

        self._client = _TC(
            session,
            cfg.tg_api_id,
            cfg.tg_api_hash,
            # 02.09: краулер тянет историю (iter_messages=GetHistory), стрим апдейтов
            # ему не нужен. Иначе telethon крутит GetState/GetDifference/GetUsers (~38/прогон),
            # а после разрыва связи устраивает catch-up-шторм: 02.09 так сгорело 42 279
            # GetUsers = весь суточный бюджет, приём встал. Пул-краулеру апдейты не нужны.
            receive_updates=False,
        )
        # Телеметрия ставится ДО connect: сам `connect` уже делает запросы
        # (`InvokeWithLayer`, `GetState`), и без этого первые обращения прогона
        # не попадали бы в счёт. Ни одно из двух действий не меняет поведения
        # обхода — только делает видимым то, что Telegram и так сообщает.
        # Подробности — docs/TELEGRAM_RATE_LIMITS_ANALYSIS.md.
        telemetry.install_telethon_logging()
        telemetry.instrument_client(self._client)
        await self._client.connect()
        if not await self._client.is_user_authorized():
            raise RuntimeError(
                "Telegram session is not authorized — run `openclaw setup-tg` first.",
            )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        # Счёт сбрасываем на диск до всего остального: если дальше упадёт
        # disconnect, расход прогона всё равно должен быть записан. Иначе
        # авария обнуляла бы именно те показания, ради которых счётчик и есть.
        import contextlib
        with contextlib.suppress(Exception):
            telemetry.meter().flush()
        if self._client is not None:
            await self._client.disconnect()
        # Лок снимаем ПОСЛЕ disconnect: именно на дисконнекте Telethon
        # сохраняет кэш сущностей (`_save_states_and_entities`), и это
        # последняя запись, которую нельзя дать перебить.
        if self._lock_fh is not None:
            import contextlib
            with contextlib.suppress(Exception):
                self._lock_fh.close()   # close снимает flock
            self._lock_fh = None

    async def iter_raw(
        self,
        handle: str,
        *,
        limit: int,
    ):
        """Yield raw Telethon ``Message`` objects (for discover_channels only).

        Unlike ``iter_messages``, this gives callers access to low-level
        attributes such as ``msg.forward``, ``msg.peer_id``, etc. that are
        not surfaced by the ``TelegramMessage`` dataclass.

        Returns an empty async-generator in mock mode.
        """
        if self._mock or self._client is None:
            return
        async for msg in self._client.iter_messages(handle, limit=limit, reverse=False):
            yield msg

    async def get_entity_username(self, peer) -> str | None:
        """Resolve a Telethon peer/id to a public @username, or None."""
        if self._mock or self._client is None:
            return None
        try:
            entity = await self._client.get_entity(peer)
            return getattr(entity, "username", None) or None
        except Exception:  # noqa: BLE001
            return None

    async def search_channels(
        self,
        query: str,
        *,
        limit: int = 50,
        min_participants: int = 0,
    ) -> list[dict]:
        """Search Telegram for channels matching *query*.

        Uses ``contacts.SearchRequest`` — matches channel titles, usernames,
        and descriptions.  Returns broadcast channels only (not groups/users).

        Each result dict:
        ``{"handle": str, "title": str, "participants": int | None}``

        Returns an empty list in mock mode.
        """
        if self._mock or self._client is None:
            return []
        from telethon.tl.functions.contacts import SearchRequest  # type: ignore[import]
        from telethon.tl.types import Channel  # type: ignore[import]

        try:
            result = await self._client(SearchRequest(q=query, limit=limit))
        except Exception:  # noqa: BLE001
            return []

        channels: list[dict] = []
        for chat in getattr(result, "chats", []):
            # Only broadcast channels — skip megagroups and regular groups
            if not isinstance(chat, Channel):
                continue
            if getattr(chat, "megagroup", False):
                continue
            username = getattr(chat, "username", None)
            if not username:
                continue
            participants = getattr(chat, "participants_count", None)
            if min_participants and participants and participants < min_participants:
                continue
            channels.append({
                "handle": username.lower(),
                "title": getattr(chat, "title", "") or "",
                "participants": participants,
            })
        return channels

    async def iter_messages(
        self,
        *,
        handle: str,
        min_id: int,
        limit: int,
        attachments_after: datetime | None = None,
    ) -> AsyncIterator[TelegramMessage]:
        """Сообщения канала начиная с ``min_id``.

        ``attachments_after`` — не качать вложения из постов старше этой даты.
        Зачем отдельная ручка, а не просто «качать всегда»: скачивание файла
        стоит **части по 128 КБ**, то есть PDF на мегабайт это восемь
        `upload.GetFile` против одного `messages.GetHistory` на весь визит
        (`telethon/utils.py:1347`). При догоне отмотанной истории это
        умножается на всю глубину. А ценность вложения падает со временем
        быстрее всего в этой ленте: резюме двухлетней давности не отзовётся.

        ``None`` — прежнее поведение, качать всё.
        """
        if self._mock or self._client is None:
            if False:  # pragma: no cover — keep typed as AsyncIterator
                yield TelegramMessage(0, "", datetime.now(UTC))
            return

        async for msg in self._client.iter_messages(
            handle,
            min_id=min_id,
            limit=limit,
            reverse=True,
        ):
            text = (msg.message or "").strip()

            # Check for supported document attachment (PDF, DOCX)
            doc_bytes: bytes | None = None
            doc_mime: str | None = None
            saved_path: str | None = None
            if msg.document:
                mime = getattr(msg.document, "mime_type", "") or ""
                too_old = bool(
                    attachments_after
                    and msg.date
                    and msg.date < attachments_after
                )
                # Бюджет спрашиваем ЗДЕСЬ, а не только между каналами.
                # Проверка «на входе в канал» бесполезна против этой статьи:
                # один визит к каналу резюме отдаёт до сотни постов, и каждое
                # вложение стоит своих частей — 161 обращение там, где ковш
                # разрешал 70, а на канале сплошных PDF и все 800. Стоимость
                # известна заранее из `document.size`, так что это не оценка.
                cost = telemetry.download_cost(getattr(msg.document, "size", None))
                over_budget = (
                    mime in _SUPPORTED_MIMES
                    and not too_old
                    and telemetry.meter().allowance() < cost
                )
                if mime in _SUPPORTED_MIMES and not too_old and not over_budget:
                    buf = io.BytesIO()
                    await self._client.download_media(msg, buf)
                    doc_bytes = buf.getvalue()
                    doc_mime = mime
                    # Сохраняем байты на HDD ДО извлечения текста: если
                    # парсер PDF споткнётся, файл всё равно останется под
                    # рукой (AGENT_RULES §5 — ошибка «влево» стоит записи).
                    saved_path = _save_attachment(
                        doc_bytes, handle, int(msg.id), mime,
                    )
                elif mime in _SUPPORTED_MIMES and too_old:
                    _log_skipped_attachment(handle, msg, "старше окна вложений")
                elif over_budget:
                    _log_skipped_attachment(
                        handle, msg, f"бюджет обращений: нужно {cost}, доступно "
                        f"{telemetry.meter().allowance()}",
                    )

            # Skip messages with no text AND no supported document
            if not text and doc_bytes is None:
                continue

            yield TelegramMessage(
                id=int(msg.id),
                text=text,
                date=msg.date or datetime.now(UTC),
                document_bytes=doc_bytes,
                document_mime=doc_mime,
                attachment_path=saved_path,
                hidden_urls=extract_hidden_urls(msg),
            )
