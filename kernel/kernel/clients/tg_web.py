"""Чтение публичных каналов через веб-превью `t.me/s/<канал>`.

Зачем вообще второй транспорт (разбор 08.08, `docs/TELEGRAM_RATE_LIMITS_ANALYSIS.md`).

Суточный лимит Telegram выдаётся **аккаунту**, и аккаунт у проекта один. Пока
единственным способом прочитать канал был MTProto, любое чтение — и свежая
лента, и догон отмотанной истории — тратило одну и ту же квоту, а её исчерпание
стоило суток простоя и накопления страйков (24 ч → 48 → 72 → 96).

Веб-превью не трогает MTProto вовсе: это обычный HTTP-запрос к странице,
которую Telegram отдаёт для предпросмотра публичного канала. Лимиты у него
свои, **по адресу, а не по аккаунту**. Асимметрия цены и есть весь смысл:
ошибка здесь стоит смены адреса, ошибка там — единственного аккаунта.

Границы, проверенные запросами 08.08:

* работает для **каналов-вещателей**; у групп веб-превью нет — `t.me/s/<группа>`
  отдаёт обычную страницу-заглушку (проверено на `@golang_jobsgo`,
  «10 763 members», превью нет);
* отдаёт текст поста, его id, время и просмотры — этого хватает для
  `inbox_items`; вложения (PDF/DOCX) через превью **не проверялись**;
* страница отдаёт последние ~20 постов, глубже — параметром `?before=<id>`.

**Ключ намеренно тот же, что у MTProto-пути**: `source="telegram"`, тот же
`channelHandle`, тот же `externalId = id сообщения`. Уникальный индекс из
миграции 0055 делает два транспорта взаимозаменяемыми и идемпотентными —
пост, собранный любым из них, второй раз не создастся. Отдельный `source`
для веба означал бы удвоение ленты.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser

import httpx
import structlog

log = structlog.get_logger()

# Разделитель блока ссылок берём из MTProto-пути, а не заводим свой:
# ниже по конвейеру парсер контактов не должен различать транспорты, а
# вторая константа рано или поздно разошлась бы с первой (AGENT_RULES §7).
_LINKS_SEPARATOR = "\n\n--- ССЫЛКИ ИЗ РАЗМЕТКИ ---\n"

_BASE = "https://t.me/s/{handle}"
_UA = "Mozilla/5.0 (compatible; hmb-market-ingest/0.1; +https://t.me)"

# Пауза между страницами. Не про вежливость: слишком частые запросы к t.me
# ловят 429, а восстановление адреса дороже, чем полсекунды ожидания.
_PAGE_DELAY_SEC = 0.7

# Теги без закрывающей пары. Нужны разбору вложенности: посчитав `<br/>`
# парным, парсер терял всё после первой строки поста.
_VOID_TAGS = frozenset({"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area"})


@dataclass
class WebPost:
    """Пост, прочитанный из веб-превью.

    Поля намеренно совпадают с тем, что нужно `upsert_inbox_item`, — чтобы
    между транспортами не заводить третий формат-переходник.
    """

    id: int
    text: str
    date: datetime
    views: str = ""


def _norm_handle(handle: str) -> str:
    """`@Канал` → `канал`. Тот же канон, что у `_normalize_handle` в бэкенде.

    Расхождение канонов уже стоило проекту 385 дублей в ротации (§L, 08.08),
    поэтому здесь тоже: снимаем собаку и регистр, и ничего больше.
    """
    return handle.strip().lstrip("@").lower()


class _MessageParser(HTMLParser):
    """Разбор страницы превью.

    Опираемся на `data-post="канал/12345"` и класс `tgme_widget_message_text`.
    Это два самых устойчивых якоря разметки: первый несёт идентификатор поста
    (без него запись нечем ключевать), второй — тело.

    Разбор терпимый по построению: незнакомые блоки пропускаются, а пост без
    текста или без id просто не попадает в выдачу. Падать на изменении вёрстки
    нельзя — это фоновый сбор, и тихая деградация здесь честнее аварии.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.posts: list[WebPost] = []
        self._cur_id: int | None = None
        self._cur_date: datetime | None = None
        self._cur_views: str = ""
        self._text_depth = 0
        self._chunks: list[str] = []
        self._links: list[str] = []
        self._in_views = False

    # ── служебное ────────────────────────────────────────────────────

    @staticmethod
    def _classes(attrs: dict[str, str]) -> set[str]:
        return set((attrs.get("class") or "").split())

    def _flush(self) -> None:
        text = "".join(self._chunks).strip()
        # Адреса ссылок — отдельным блоком, ровно как в MTProto-пути.
        #
        # Без этого веб-транспорт терял бы контакты молча. В тексте остаётся
        # слово «Откликнуться», а адрес живёт в `href` — и замер 25.07 показал
        # у каналов-бордов ровно 0% контактов именно поэтому. Переход на веб
        # при 100% покрытия повторил бы ту же потерю на всём корпусе сразу,
        # и увидеть её было бы нечем: посты-то собираются.
        #
        # Разделитель тот же, что у MTProto (`watch_channels._LINKS_SEPARATOR`):
        # ниже по конвейеру парсер контактов не должен различать транспорты.
        extra = [u for u in self._links if u and u not in text]
        if extra:
            text = text + _LINKS_SEPARATOR + "\n".join(dict.fromkeys(extra))
        if self._cur_id is not None and text:
            self.posts.append(
                WebPost(
                    id=self._cur_id,
                    text=text,
                    date=self._cur_date or datetime.now(UTC),
                    views=self._cur_views,
                ),
            )
        self._cur_id, self._cur_date, self._cur_views = None, None, ""
        self._chunks, self._links = [], []

    # ── HTMLParser ───────────────────────────────────────────────────

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        classes = self._classes(a)

        if "data-post" in a:
            # Новый пост. Предыдущий закрываем здесь, а не по закрывающему
            # тегу: вложенность у превью глубокая, и считать её — лишний
            # источник ошибок. Границей поста служит начало следующего.
            self._flush()
            m = re.search(r"/(\d+)\s*$", a["data-post"])
            if m:
                self._cur_id = int(m.group(1))

        if tag == "time" and a.get("datetime"):
            # Дата берётся из атрибута, а не из видимого «12:34»: в тексте
            # только время, и пост вчерашнего дня получил бы сегодняшнюю дату,
            # то есть уехал бы в окно свежести (тот же класс, что даты trudvsem).
            with contextlib.suppress(ValueError):
                self._cur_date = datetime.fromisoformat(
                    a["datetime"].replace("Z", "+00:00"),
                )

        if "tgme_widget_message_views" in classes:
            self._in_views = True

        if self._text_depth and tag == "a" and a.get("href"):
            # Только внутри тела поста: ссылки шапки, даты и имени канала
            # к содержанию отношения не имеют и засоряли бы raw_text.
            self._links.append(a["href"].strip())

        if self._text_depth:
            if tag in _VOID_TAGS:
                # Пустые теги глубину не меняют. Первая версия считала их
                # парными, и `<br/>` уводил счётчик в ноль — текст поста
                # обрывался на первой же строке. Поймано тестом, а не глазами.
                if tag == "br":
                    self._chunks.append("\n")
                return
            self._text_depth += 1
        elif "tgme_widget_message_text" in classes:
            self._text_depth = 1

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """`<br/>` — один тег, а не пара.

        Умолчание HTMLParser зовёт для него и `handle_starttag`, и
        `handle_endtag`; второй вызов уронил бы глубину вложенности.
        """
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_TAGS:
            return
        if self._text_depth:
            self._text_depth -= 1
        if tag == "span":
            self._in_views = False

    def handle_data(self, data: str) -> None:
        if self._text_depth:
            self._chunks.append(data)
        elif self._in_views and not self._cur_views:
            self._cur_views = data.strip()

    def close(self) -> None:  # noqa: D102
        super().close()
        self._flush()


def parse_page(html: str) -> list[WebPost]:
    """Посты со страницы превью, от старых к новым.

    Порядок именно такой, потому что дальше их складывают в `inbox_items` и
    двигают offset: перевёрнутый порядок означал бы, что offset уезжает на
    самый новый пост раньше, чем собраны предыдущие, — и середина теряется
    молча. Ровно эта ошибка стоила §L восьми тысяч сообщений.
    """
    p = _MessageParser()
    p.feed(html)
    p.close()
    return sorted(p.posts, key=lambda x: x.id)


def looks_like_channel_preview(html: str) -> bool:
    """Есть ли на странице лента постов.

    У групп превью нет: `t.me/s/<группа>` отдаёт обычную страницу-визитку
    (проверено на `@golang_jobsgo`). Отличать надо явно — иначе «0 постов»
    у группы читалось бы как «канал молчит», и мы бы вычеркнули живой
    источник по несуществующему признаку (AGENT_RULES §3).
    """
    return "tgme_widget_message" in html


class TgWebClient:
    """HTTP-чтение превью. Своя сессия, никакого MTProto."""

    def __init__(self, *, client: httpx.AsyncClient | None = None) -> None:
        self._own = client is None
        self._client = client or httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": _UA, "Accept-Language": "ru,en;q=0.8"},
        )

    async def __aenter__(self) -> TgWebClient:
        return self

    async def __aexit__(self, *exc) -> None:
        if self._own:
            await self._client.aclose()

    async def fetch_page(self, handle: str, before: int | None = None) -> tuple[str, int]:
        """HTML страницы и код ответа. Исключения наружу не выпускаем."""
        url = _BASE.format(handle=_norm_handle(handle))
        params = {"before": str(before)} if before else None
        try:
            r = await self._client.get(url, params=params)
            return r.text, r.status_code
        except Exception as exc:  # noqa: BLE001
            log.warning("tgweb.fetch_failed", handle=handle, err=str(exc))
            return "", 0

    async def fetch_since(
        self,
        handle: str,
        *,
        min_id: int = 0,
        max_pages: int = 10,
    ) -> list[WebPost]:
        """Посты новее ``min_id``, от старых к новым.

        Идём страницами назад, пока не упрёмся в ``min_id`` или в потолок
        ``max_pages``. Потолок обязателен: у `@bolsadetrabajoparaguay` 5 321
        сообщение, и без ограничения один канал занял бы весь прогон.

        Возвращает пустой список и для мёртвого имени, и для группы — но в
        логе это **разные** строки. Слить их значило бы получить «канал
        молчит» там, где на самом деле «не тот тип канала».
        """
        collected: dict[int, WebPost] = {}
        before: int | None = None
        for page_no in range(max_pages):
            html, code = await self.fetch_page(handle, before=before)
            if code != 200 or not html:
                log.warning("tgweb.page_bad", handle=handle, code=code, page=page_no)
                break
            if not looks_like_channel_preview(html):
                log.info(
                    "tgweb.no_preview", handle=handle,
                    hint="скорее всего группа, а не канал-вещатель — превью нет",
                )
                break
            posts = parse_page(html)
            if not posts:
                break
            fresh = [p for p in posts if p.id > min_id]
            for p in fresh:
                collected[p.id] = p
            oldest = posts[0].id
            # Дошли до известного или дальше некуда — останавливаемся.
            if oldest <= min_id or len(fresh) < len(posts):
                break
            before = oldest
            await asyncio.sleep(_PAGE_DELAY_SEC)
        return [collected[k] for k in sorted(collected)]
