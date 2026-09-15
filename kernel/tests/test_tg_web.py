"""Разбор веб-превью `t.me/s/<канал>` — транспорт вне квоты аккаунта.

⚠️ **Фикстура написана по разметке, а не снята с живой страницы.** Из песочницы
сети нет, поэтому HTML здесь собран по структуре, которую отдаёт превью
(`data-post`, `tgme_widget_message_text`, `<time datetime>`). Тесты охраняют
поведение парсера, но **не доказывают, что разметка именно такая**. Проверка
на живой странице — одна команда на Mac:

    zsh ops/channels/web_probe.command @ru_pythonjobs

До неё транспорт считать непрогнанным (AGENT_RULES §8).

Что здесь охраняется:

1. Порядок — от старых к новым. Перевёрнутый порядок двигает offset на самый
   новый пост раньше, чем собрана середина, и она теряется молча. Ровно эта
   ошибка стоила §L восьми тысяч сообщений.
2. Дата из атрибута, а не из видимого «12:34» — иначе вчерашний пост уезжает
   в сегодняшнее окно свежести.
3. «Нет превью» ≠ «канал молчит». У групп превью нет, и слить эти два случая
   значит вычеркнуть живой источник по несуществующему признаку.
4. Разбор терпим к незнакомой вёрстке: тихая деградация честнее аварии в
   фоновом сборе.
"""

from __future__ import annotations

from kernel.clients import tg_web


def _msg(post_id: int, text: str, when: str, views: str = "1.2K") -> str:
    return f"""
    <div class="tgme_widget_message_wrap js-widget_message_wrap">
      <div class="tgme_widget_message text_not_supported_wrap js-widget_message"
           data-post="testchan/{post_id}">
        <div class="tgme_widget_message_text js-message_text">{text}</div>
        <div class="tgme_widget_message_footer compact js-message_footer">
          <span class="tgme_widget_message_views">{views}</span>
          <a class="tgme_widget_message_date" href="https://t.me/testchan/{post_id}">
            <time datetime="{when}" class="time">12:34</time>
          </a>
        </div>
      </div>
    </div>"""


def _page(*messages: str) -> str:
    return (
        "<html><body><main class='tgme_channel_history js-message_history'>"
        + "".join(messages)
        + "</main></body></html>"
    )


# ── 1. Порядок и содержимое ──────────────────────────────────────────


def test_parses_posts_oldest_first():
    html = _page(
        _msg(300, "третий", "2026-08-08T10:00:00+00:00"),
        _msg(100, "первый", "2026-08-06T10:00:00+00:00"),
        _msg(200, "второй", "2026-08-07T10:00:00+00:00"),
    )
    posts = tg_web.parse_page(html)
    assert [p.id for p in posts] == [100, 200, 300]
    assert [p.text for p in posts] == ["первый", "второй", "третий"]


def test_line_breaks_survive():
    """Перевод строки — не украшение: по нему `template_extractor` отделяет
    заголовок от тела, а `topic_gate` берёт окно темы."""
    html = _page(_msg(1, "Заголовок<br/>Тело вакансии<br>Ещё строка", "2026-08-08T10:00:00+00:00"))
    posts = tg_web.parse_page(html)
    assert posts[0].text.splitlines() == ["Заголовок", "Тело вакансии", "Ещё строка"]


def test_link_targets_are_kept_not_only_their_text():
    """Тихая потеря, которую 100%-покрытие сделало опасной.

    В тексте остаётся слово «Откликнуться», а адрес живёт в `href`. Замер
    25.07 показал у каналов-бордов ровно 0% контактов именно поэтому. При
    переходе на веб та же потеря случилась бы сразу на всём корпусе, и
    заметить её было бы нечем — посты-то собираются.
    """
    html = _page(
        _msg(
            1,
            'Нужен Python-разработчик. <a href="https://t.me/hr_person">Откликнуться</a>',
            "2026-08-08T10:00:00+00:00",
        ),
    )
    text = tg_web.parse_page(html)[0].text
    assert "Откликнуться" in text
    assert "https://t.me/hr_person" in text
    assert tg_web._LINKS_SEPARATOR in text


def test_link_already_present_in_text_is_not_duplicated():
    html = _page(
        _msg(
            1,
            'Пишите: <a href="https://t.me/hr">https://t.me/hr</a> по вакансии бэкенда',
            "2026-08-08T10:00:00+00:00",
        ),
    )
    text = tg_web.parse_page(html)[0].text
    assert text.count("https://t.me/hr") == 1
    assert tg_web._LINKS_SEPARATOR not in text


def test_links_outside_the_post_body_are_ignored():
    """Ссылки шапки, даты и имени канала к содержанию не относятся —
    в `raw_text` они были бы шумом на каждом посте."""
    html = _page(_msg(1, "Просто текст вакансии без ссылок", "2026-08-08T10:00:00+00:00"))
    text = tg_web.parse_page(html)[0].text
    assert tg_web._LINKS_SEPARATOR not in text
    assert "t.me/testchan/1" not in text


def test_links_do_not_leak_between_posts():
    html = _page(
        _msg(1, 'Первый <a href="https://example.com/a">тут</a>', "2026-08-08T10:00:00+00:00"),
        _msg(2, "Второй без ссылок вообще", "2026-08-08T11:00:00+00:00"),
    )
    posts = tg_web.parse_page(html)
    assert "example.com/a" in posts[0].text
    assert "example.com/a" not in posts[1].text


def test_nested_markup_inside_text_is_kept():
    html = _page(
        _msg(
            1,
            'Нужен <b>Python</b> разработчик, <a href="https://t.me/hr">откликнуться</a>',
            "2026-08-08T10:00:00+00:00",
        ),
    )
    text = tg_web.parse_page(html)[0].text
    assert "Python" in text
    assert "откликнуться" in text


# ── 2. Дата из атрибута ──────────────────────────────────────────────


def test_date_comes_from_attribute_not_visible_time():
    """Видно «12:34», а пост позавчерашний. Взяли бы видимое — получили бы
    сегодняшнюю дату и испортили окна свежести (класс ошибки — даты trudvsem)."""
    html = _page(_msg(1, "текст", "2026-08-06T09:15:00+00:00"))
    post = tg_web.parse_page(html)[0]
    assert post.date.year == 2026
    assert post.date.month == 8
    assert post.date.day == 6
    assert post.date.hour == 9


def test_broken_date_does_not_drop_the_post():
    html = _page(_msg(1, "текст", "не дата"))
    posts = tg_web.parse_page(html)
    assert len(posts) == 1          # пост важнее его метки времени


# ── 3. «Нет превью» — отдельный случай ───────────────────────────────


def test_group_page_is_recognised_as_no_preview():
    """`t.me/s/<группа>` отдаёт визитку без ленты — проверено на
    `@golang_jobsgo` (10 763 members). Это не «канал молчит»."""
    group_page = (
        "<html><body><div class='tgme_page_wrap'>"
        "<div class='tgme_page_title'>Golang Jobs</div>"
        "<div class='tgme_page_extra'>10 763 members</div>"
        "</div></body></html>"
    )
    assert tg_web.looks_like_channel_preview(group_page) is False
    assert tg_web.parse_page(group_page) == []


def test_channel_page_is_recognised_as_preview():
    assert tg_web.looks_like_channel_preview(_page(_msg(1, "т", "2026-08-08T10:00:00+00:00")))


# ── 4. Терпимость к вёрстке ──────────────────────────────────────────


def test_post_without_id_is_skipped_not_crashing():
    html = (
        "<html><body>"
        "<div class='tgme_widget_message'>"
        "<div class='tgme_widget_message_text'>текст без data-post</div>"
        "</div></body></html>"
    )
    assert tg_web.parse_page(html) == []


def test_empty_post_is_skipped():
    """Пост из одного вложения приходит без текста. Пустую запись в инбокс
    класть нельзя — она выглядела бы собранной."""
    html = _page(_msg(7, "", "2026-08-08T10:00:00+00:00"))
    assert tg_web.parse_page(html) == []


def test_garbage_input_returns_nothing():
    for junk in ("", "<html>", "не html вовсе", "<div data-post='x/notanumber'></div>"):
        assert tg_web.parse_page(junk) == []


# ── Канон имени — тот же, что у бэкенда ──────────────────────────────


def test_handle_normalisation_matches_backend_canon():
    """Расхождение канонов уже стоило 385 дублей в ротации (§L). Собака и
    регистр снимаются, остальное не трогается."""
    assert tg_web._norm_handle("@Ru_PythonJobs") == "ru_pythonjobs"
    assert tg_web._norm_handle("  ru_pythonjobs  ") == "ru_pythonjobs"
    assert tg_web._norm_handle("ru_pythonjobs") == "ru_pythonjobs"


# ── Пагинация останавливается ────────────────────────────────────────


class _FakeClient:
    """Три страницы истории, от новых к старым — как их отдаёт t.me."""

    def __init__(self) -> None:
        self.calls: list[int | None] = []
        self.pages = {
            None: _page(*[_msg(i, f"пост {i}", "2026-08-08T10:00:00+00:00") for i in (30, 29, 28)]),
            28: _page(*[_msg(i, f"пост {i}", "2026-08-07T10:00:00+00:00") for i in (27, 26, 25)]),
            25: _page(*[_msg(i, f"пост {i}", "2026-08-06T10:00:00+00:00") for i in (24, 23, 22)]),
        }

    async def get(self, url, params=None):  # noqa: ANN001
        before = int(params["before"]) if params and "before" in params else None
        self.calls.append(before)

        class R:
            status_code = 200
            text = self.pages.get(before, "<html></html>")
        return R()

    async def aclose(self) -> None:
        return None


async def _collect(min_id: int, max_pages: int = 10):
    fake = _FakeClient()
    client = tg_web.TgWebClient(client=fake)
    posts = await client.fetch_since("testchan", min_id=min_id, max_pages=max_pages)
    return posts, fake


def test_pagination_stops_at_known_offset():
    """Дошли до известного — дальше не листаем. Иначе каждый прогон
    перечитывал бы канал целиком."""
    import asyncio
    posts, fake = asyncio.run(_collect(min_id=26))
    assert [p.id for p in posts] == [27, 28, 29, 30]
    assert len(fake.calls) == 2                    # первая страница + одна назад


def test_pagination_respects_page_cap():
    """Потолок страниц обязателен: у `@bolsadetrabajoparaguay` 5 321 сообщение,
    без ограничения один канал занял бы весь прогон."""
    import asyncio
    posts, fake = asyncio.run(_collect(min_id=0, max_pages=2))
    assert len(fake.calls) == 2
    assert len(posts) == 6


def test_no_duplicates_across_pages():
    import asyncio
    posts, _ = asyncio.run(_collect(min_id=0))
    assert len(posts) == len({p.id for p in posts})
