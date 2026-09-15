"""Unit tests for kernel.skills.salary.parse_salary — the canonical
salary-string rules shared by the template extractor, LLM post-parse and
importers."""

import pytest

from kernel.skills.salary import parse_salary


def _lhc(text):
    p = parse_salary(text)
    return (p.low, p.high, p.currency)


def test_from_is_lower_bound():
    assert _lhc("от 150 000 ₽") == (150000, None, "RUB")


def test_upto_is_upper_bound():
    assert _lhc("до 200к") == (None, 200000, None)


def test_range_shares_multiplier():
    assert _lhc("от 100 до 200 тыс ₽") == (100000, 200000, "RUB")


def test_range_dash():
    assert _lhc("150 000 - 200 000 руб") == (150000, 200000, "RUB")


def test_single_value_is_lower_bound():
    assert _lhc("зарплата 250к") == (250000, None, None)


def test_currency_symbols():
    assert _lhc("$3000")[2] == "USD"
    assert _lhc("200000 ₸")[2] == "KZT"
    assert _lhc("3000 €")[2] == "EUR"


def test_range_with_currency_and_period():
    p = parse_salary("$3000-4000/month")
    assert (p.low, p.high, p.currency, p.period) == (3000, 4000, "USD", "month")


def test_hourly_rate():
    p = parse_salary("ставка $40/час")
    assert (p.low, p.high, p.currency, p.period) == (40, None, "USD", "hour")


def test_basis_net_and_gross():
    assert parse_salary("на руки 180000").basis == "net"
    assert parse_salary("120000 gross").basis == "gross"


def test_precision_guard_rejects_non_pay():
    assert _lhc("от 5 лет опыта") == (None, None, None)
    assert _lhc("5 человек в команде") == (None, None, None)


def test_empty_and_none():
    assert _lhc("") == (None, None, None)
    assert _lhc(None) == (None, None, None)


# ── Календарный год — не зарплата (найдено 01.08) ────────────────────


@pytest.mark.parametrize("text", [
    "Релиз в 2026 году",
    "Проект стартовал в 2019 году",
    "Опыт с 2020 года",
    "Работаем с 1998 года",
    "Компания основана в 2011",
])
def test_calendar_year_is_not_a_salary(text: str) -> None:
    """Порога «≥1000» не хватало: 2026 его проходит и уезжает в зарплату.

    Найдено прогоном парсера на контрольных фразах при замере §3
    (вакансии без вилки). Такие значения потом оседали в «мусорных вилках»
    — ниже 40k ₽, — и выглядели как проблема рынка, а не парсера.
    """
    r = parse_salary(text)
    assert r.low is None and r.high is None


@pytest.mark.parametrize("text", [
    "600 000 ₽ в год",          # валюта есть — не задето
    "Годовой доход 2 500 000",  # вне диапазона лет
    "$120 000 per year",
    "от 2000 до 4000 USD",      # пара, где не все числа похожи на год
    "$2000 в месяц",
])
def test_real_salaries_survive_the_year_guard(text: str) -> None:
    r = parse_salary(text)
    assert r.low is not None or r.high is not None


# ── Свободный текст против поля «Зарплата: …» (найдено 01.08) ────────


@pytest.mark.parametrize("post", [
    # Валюта в одном предложении, число — в другом. Без free_text парсер
    # склеивал их и выдавал «3 ₽», «17 ₽». Эти вилки доезжали до базы:
    # замер §3 нашёл 1 412 значений ниже 40 000 ₽ у одного только RUB.
    "Backend PHP разработчик\nОпыт от 3 лет, команда 12 человек.\nОплата в рублях, ежемесячно.",
    "C++ Senior Developer\nОпыт 17 лет суммарно у команды.\nЗарплата обсуждается, ₽",
    "Фронтендер-стажер\nГрафик 3–6 часов в день.\nОплата в рублях",
    "Python developer\nРелиз через 5–10 недель, годовой контракт",
])
def test_free_text_does_not_invent_salaries(post: str) -> None:
    r = parse_salary(post, free_text=True)
    assert r.low is None and r.high is None


@pytest.mark.parametrize("post", [
    "Senior Python\nЗарплата 250 000 ₽ на руки\nУдалёнка",
    "DevOps\nВилка 200–350к рублей\nМосква",
    "Frontend\nОплата $3000 в месяц",
    "Аналитик\nдо 400 000 руб",
    "QA\n1500 руб/час, проектно",
])
def test_free_text_keeps_real_salaries(post: str) -> None:
    r = parse_salary(post, free_text=True)
    assert r.low is not None or r.high is not None


def test_field_mode_unchanged() -> None:
    """Поле «Зарплата: …» разбирается как раньше — порог там не нужен."""
    assert parse_salary("$3000").low == 3000
    assert parse_salary("от 250 000 руб").low == 250_000
    # А голое «3» отсекается и в поле — это прежний предохранитель.
    assert parse_salary("3").low is None
