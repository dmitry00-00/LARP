"""salary.py — canonical salary-string parser (Task 14).

One place for the rules every salary extractor should share, so the
template extractor, the LLM post-parse, and the regex importers stop
disagreeing:

  * «от N»      → lower bound        (N, None)
  * «до N»      → upper bound        (None, N)
  * «N–M»       → both               (N, M)
  * lone number → lower-bound heuristic (N, None)

Plus currency detection (₽/$/€/₸/£ and words), к/тыс ×1000 multipliers,
pay basis (gross/net) and period (month/year/hour). Amounts are returned
raw in their native currency — conversion to the RUB/USD base columns is
``app.services.fx``'s job.

Pure and dependency-free (no app/openclaw imports) so it unit-tests in
isolation and can be vendored by the backend importers if needed.
"""
from __future__ import annotations

import re
from typing import NamedTuple


class SalaryParse(NamedTuple):
    low: int | None
    high: int | None
    currency: str | None
    period: str | None  # 'month' | 'year' | 'hour' | None
    basis: str | None  # 'gross' | 'net' | None


# Currency — first match wins; order by specificity isn't needed (disjoint).
_CURRENCY: list[tuple[str, re.Pattern]] = [
    ("RUB", re.compile(r"₽|руб(?:л(?:ей|я|ях|ь))?|\brub\b|\brur\b", re.I)),
    ("USD", re.compile(r"\$|\busd\b|доллар", re.I)),
    ("EUR", re.compile(r"€|\beur\b|евро", re.I)),
    ("KZT", re.compile(r"₸|\bkzt\b|тенге", re.I)),
    ("GBP", re.compile(r"£|\bgbp\b|фунт", re.I)),
]

_NET = re.compile(r"на\s+руки|чист(?:ыми|ая)|\bnet\b|после\s+налог|after\s+tax", re.I)
_GROSS = re.compile(r"\bgross\b|до\s+вычет|до\s+налог|гросс|грязными|before\s+tax", re.I)

_PERIOD: list[tuple[str, re.Pattern]] = [
    ("hour", re.compile(r"/\s*(?:ч(?:ас)?|h(?:our|r)?)\b|в\s+час|per\s+hour", re.I)),
    ("year", re.compile(r"/\s*(?:год|year|yr)|в\s+год|per\s+year|годов(?:ых|ой)|annual|p\.?a\.?", re.I)),
    ("month", re.compile(r"/\s*(?:мес(?:яц)?|months?|mo)\b|в\s+месяц|per\s+month", re.I)),
]

_NUM = r"\d[\d\s.,]*"

# То же число, но с ЛЕВОЙ границей — для позиций, где число начинает
# фрагмент (голое число, нижний край диапазона).
#
# Без границы `\d` цепляется к середине идентификатора, и замер 07.08
# (`free_path_gate`) показал, что именно так рождаются фальшивые вилки:
#
#     «Financial Controller Middle (HS-46725)»  → 46 725 ₽
#     «Senior Embedded C Developer IRC294418»   → 294 418 ₽
#     «...писать в тг 79333993725»              → 79 333 993 725 ₽
#
# Первое опаснее прочих: сорок шесть тысяч рублей проходят и порог ≥1000,
# и фильтр правдоподобности 40k–1.5M у `/worth`, то есть попадают в
# зарплатный бенчмарк как настоящие. Мусорная цифра там хуже отсутствующей.
#
# `(?<![\w-])` отсекает и приклеенное к буквам (`IRC294418`), и висящее на
# дефисе (`HS-46725`). К ВЕРХНЕМУ краю диапазона не применяется: там дефис
# — законный разделитель («150-200к»).
_NUM_L = r"(?<![\w-])\d[\d\s.,]*"
_MULT = r"(?:тыс(?:яч)?\.?|к|k)"

_RANGE = re.compile(
    rf"(?P<lo>{_NUM_L})\s*(?P<lo_mult>{_MULT})?\s*(?:[-–—]|до|to)\s*"
    rf"(?P<hi>{_NUM})\s*(?P<hi_mult>{_MULT})?",
    re.I,
)
_UPTO = re.compile(rf"(?:до|up\s*to|under|не\s+более)\s*(?P<v>{_NUM})\s*(?P<mult>{_MULT})?", re.I)
_FROM = re.compile(rf"(?:от|from)\s*(?P<v>{_NUM})\s*(?P<mult>{_MULT})?", re.I)
# Голое число — единственный случай без словесного маркера слева, поэтому
# только здесь граница обязательна: «IRC294418» не должно стать зарплатой.
_BARE = re.compile(rf"(?P<v>{_NUM_L})\s*(?P<mult>{_MULT})?", re.I)


def _to_int(num: str | None, mult: str | None) -> int | None:
    if not num:
        return None
    s = re.sub(r"[\s,]", "", num).rstrip(".")
    try:
        val = float(s)
    except ValueError:
        return None
    if mult and mult.lower().rstrip(".") in ("тыс", "тысяч", "к", "k"):
        val *= 1000
    return int(round(val))


def _first(text: str, table: list[tuple[str, re.Pattern]]) -> str | None:
    for name, pat in table:
        if pat.search(text):
            return name
    return None


# Слова, рядом с которыми число действительно похоже на оплату. Нужны только
# для ГОЛОГО числа в свободном тексте: у «от N», «до N» и «N–M» есть свой
# лексический якорь, а у голого — ничего.
_PAY_WORD = re.compile(
    r"зарплат|зарплатн|з\.?/?п\b|зп\b|оклад|вилк|доход|ставк|получа|платим|"
    r"оплат|salary|payment|compensation|rate\b|бюджет",
    re.I,
)
# Окно поиска вокруг числа. 40 символов — примерно фраза: «Оклад 120000»,
# «120 000 на руки». Шире брать нельзя: ровно на этом ломался прежний
# общетекстовый детект валюты, когда «оплата в рублях» из другого абзаца
# узаконивала «от 3 лет» (см. докстринг parse_salary).
_PAY_WINDOW = 40


def _has_pay_context(text: str, start: int, end: int) -> bool:
    """Есть ли рядом с числом признак оплаты: зарплатное слово или валюта.

    Множитель («к», «тыс») сюда НЕ входит, хотя соблазн велик: `_MULT` — это
    `(?:тыс|к|k)` без границ слова, и поиск его по окну находит букву «к» в
    любом слове. На проверке 07.08 «в Ябко, тел 3332407» так и прошло:
    множитель «нашёлся» в названии компании. Прилегание множителя к числу
    проверяет сам регекс (`{_NUM}\\s*{_MULT}?`), и результат приходит сюда
    отдельным аргументом у вызывающей стороны.
    """
    frag = text[max(0, start - _PAY_WINDOW) : end + _PAY_WINDOW]
    if _PAY_WORD.search(frag):
        return True
    return bool(_first(frag, _CURRENCY) or _first(frag, _PERIOD))


def _extract_bounds(text: str, *, free_text: bool = False) -> tuple[int | None, int | None]:
    """Apply the от/до/range/bare precedence and return raw (low, high)."""
    m = _RANGE.search(text)
    if m:
        # "150-200к" → the magnitude unit on either end applies to both.
        lo_mult = m.group("lo_mult") or m.group("hi_mult")
        hi_mult = m.group("hi_mult") or m.group("lo_mult")
        return _to_int(m.group("lo"), lo_mult), _to_int(m.group("hi"), hi_mult)
    m = _UPTO.search(text)
    if m:
        return None, _to_int(m.group("v"), m.group("mult"))
    m = _FROM.search(text)
    if m:
        return _to_int(m.group("v"), m.group("mult")), None
    m = _BARE.search(text)
    if m:
        # Голое число в целом посте — самый слабый сигнал из четырёх, и
        # единственный без словесного якоря. Замер 07.08: так в зарплату
        # попали телефон и номер вакансии. Требуем признак оплаты В ОКНЕ
        # вокруг числа, а не где-то в тексте.
        # Множитель вплотную к числу («120к») — сам по себе признак оплаты.
        adjacent_mult = bool(m.group("mult"))
        if (
            free_text
            and not adjacent_mult
            and not _has_pay_context(text, m.start("v"), m.end("v"))
        ):
            return None, None
        return _to_int(m.group("v"), m.group("mult")), None
    return None, None


def parse_salary(text: str | None, *, free_text: bool = False) -> SalaryParse:
    """Разобрать строку с зарплатой.

    ``free_text=True`` — когда на вход идёт НЕ поле «Зарплата: …», а целый
    пост. Это принципиально другой режим доверия, и без него получается вот
    что (найдено 01.08 на живых данных):

        Backend PHP разработчик
        Опыт от 3 лет, команда 12 человек.
        Оплата в рублях, ежемесячно.

    → `low=3, currency=RUB`. Обычный предохранитель («голое число — зарплата
    только если ≥1000») не срабатывает, потому что валюта в тексте ЕСТЬ —
    просто в другом предложении, за сорок символов от числа.

    Так в базу и попадают вилки «3 ₽»: замер §3 нашёл 1 412 значений ниже
    40 000 ₽ у RUB. В свободном тексте порог применяется ВСЕГДА, независимо
    от валюты и периода: настоящая зарплата меньше тысячи не бывает ни в
    одной валюте, а годы опыта и размер команды — почти всегда.
    """
    if not text or not str(text).strip():
        return SalaryParse(None, None, None, None, None)
    text = str(text)
    currency = _first(text, _CURRENCY)
    period = _first(text, _PERIOD)
    basis = "net" if _NET.search(text) else ("gross" if _GROSS.search(text) else None)

    low, high = _extract_bounds(text, free_text=free_text)

    # Precision guard: a bare number is only a salary when the fragment
    # actually looks like pay — a currency/period/multiplier is present, or
    # the amount is too big to be a year count / team size (≥ 1000). This
    # stops "от 5 лет" or "5 человек" being read as a salary.
    # Второй предохранитель, того же рода: КАЛЕНДАРНЫЙ ГОД.
    #
    # Порога «≥1000» не хватает: «Релиз в 2026 году», «Опыт с 2020 года»,
    # «Работаем с 1998 года» дают числа больше тысячи и проезжают в зарплату.
    # Найдено 01.08 прогоном парсера на контрольных фразах, до всякой базы.
    #
    # (Первая версия правки объясняла это тем, что «год» совпадает с
    #  `_PERIOD` и отключает проверку. Это неверно: `в\s+год` не совпадает с
    #  «в 2026 году», period там None. Дело именно в пороге.)
    #
    # Условие узкое: только когда нет НИ валюты, НИ периода, и ВСЕ найденные
    # числа похожи на календарный год. Настоящая зарплата в этом диапазоне
    # либо идёт с валютой («$2000»), либо в паре с числом вне его
    # («от 2000 до 4000») — оба случая не задеты.
    # Третий предохранитель того же рода: ДЛИННОЕ ЧИСЛО.
    #
    # Телефон в тексте поста — не редкость («писать в тг 79333993725»), и
    # порогом снизу его не поймать: он больше тысячи и на год не похож.
    # Десять и более цифр не бывают месячным окладом ни в одной валюте:
    # даже в сумах и рупиях это миллионы долларов. Граница слева (`_NUM_L`)
    # ловит приклеенное к буквам, а это — отдельно стоящее.
    vals = [v for v in (low, high) if v is not None]
    if vals:
        # too_small / too_long — УНИВЕРСАЛЬНЫЕ истины, применяются всегда,
        # даже когда в тексте есть валюта. Прежде они были заперты в ветке
        # `free_text or not (currency or period)`, и структурное поле «2 ₽»
        # (валюта есть, не free_text) проезжало порог: замер 14.08 —
        # медиана Data Science / ML = 2 ₽ (§4, круглое/абсурдное число =
        # артефакт парсера, не рынок). Настоящая МЕСЯЧНАЯ/годовая зарплата
        # меньше тысячи не бывает ни в одной валюте.
        #
        # Исключение — ПОЧАСОВАЯ ставка: $20/час законно ниже тысячи, поэтому
        # порог снизу снимается только для period='hour'.
        too_small = max(vals) < 1000 and period != "hour"
        # ≥1e9 — телефон/идентификатор, не оклад ни в одной валюте.
        too_long = any(v >= 1_000_000_000 for v in vals)
        # Календарный год маскируется под зарплату лишь когда нет НИ валюты,
        # НИ периода: «$2020» или «2000 в год» законны, «Опыт с 2020 года» —
        # нет. free_text расширяет проверку: в целом посте год у числа
        # встречается чаще зарплаты.
        looks_like_year = (
            (free_text or not (currency or period))
            and all(1990 <= v <= 2100 for v in vals)
        )
        if too_small or too_long or looks_like_year:
            low = high = None

    return SalaryParse(low, high, currency, period, basis)
