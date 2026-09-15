"""Ссылки, спрятанные в разметке Telegram.

Находка 25.07: у каналов-бордов (`@aldaba_rd`, `@robotaua_now_*`) замер
показал 0% контактов при постах на 400 символов. Причина — не парсер: в
`msg.message` нет ни целей гиперссылок, ни inline-кнопок, а именно там у
автопостинга лежит «Откликнуться». Эти тесты держат фикс.

Стабы намеренно простые: `extract_hidden_urls` читает атрибуты через
getattr, поэтому телетоновские типы (и секреты Telegram) для проверки не
нужны.
"""
from types import SimpleNamespace

from kernel.clients.telegram import extract_hidden_urls


def _msg(text="", entities=None, buttons=None):
    markup = None
    if buttons is not None:
        markup = SimpleNamespace(
            rows=[SimpleNamespace(buttons=[SimpleNamespace(url=u) for u in buttons])]
        )
    return SimpleNamespace(message=text, entities=entities, reply_markup=markup)


def test_hyperlink_target_extracted():
    # В тексте видно «Откликнуться», адрес — в сущности.
    msg = _msg(
        "Senior Python. Откликнуться",
        entities=[SimpleNamespace(url="https://t.me/hr_anna")],
    )
    assert extract_hidden_urls(msg) == ["https://t.me/hr_anna"]


def test_inline_button_url_extracted():
    # Кнопки в тексте нет вообще — это и был потерянный контакт.
    msg = _msg("Вакансія: Java розробник", buttons=["https://aldaba.rd/apply/123"])
    assert extract_hidden_urls(msg) == ["https://aldaba.rd/apply/123"]


def test_url_already_in_text_not_duplicated():
    msg = _msg(
        "Резюме на https://t.me/hr_anna",
        entities=[SimpleNamespace(url="https://t.me/hr_anna")],
    )
    assert extract_hidden_urls(msg) == []


def test_entities_without_url_ignored():
    # Жирный шрифт, хэштег, обычное @упоминание — у них нет .url, и они
    # уже есть в тексте.
    msg = _msg("#вакансия @hr_anna", entities=[SimpleNamespace(offset=0, length=9)])
    assert extract_hidden_urls(msg) == []


def test_duplicates_collapsed_and_order_kept():
    msg = _msg(
        "Откликнуться или написать",
        entities=[
            SimpleNamespace(url="https://t.me/first"),
            SimpleNamespace(url="https://t.me/second"),
            SimpleNamespace(url="https://t.me/first"),
        ],
        buttons=["https://t.me/second", "https://forms.gle/abc"],
    )
    assert extract_hidden_urls(msg) == [
        "https://t.me/first",
        "https://t.me/second",
        "https://forms.gle/abc",
    ]


def test_message_without_markup_is_safe():
    assert extract_hidden_urls(SimpleNamespace(message="просто текст")) == []
    assert extract_hidden_urls(_msg("текст", entities=None, buttons=None)) == []
