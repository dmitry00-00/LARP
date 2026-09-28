"""Регистр и сравнение текста в SQLite: кириллица, умляуты, диакритика.

**Почему этот файл существует.** Встроенные `lower()` / `upper()` в SQLite
складывают регистр **только для ASCII** — это свойство движка, а не настройка:

    sqlite> select lower('РОБОТ-Коробка');   ->  РОБОТ-Коробка
    sqlite> select lower('ROBOT-Box');       ->  robot-box

То же у оператора `LIKE`: он регистронезависим для латиницы и
регистро**зависим** для всего остального.

**Цена, замеренная 16.09.2026 на живой `data/hmb.sqlite`.** Запрос
`where lower(title) like '%робот%'` вернул 2 лота из 3: «Робот-коробка»
(allrpg `/exchange/20/`) не совпал, потому что начинается с заглавной «Р».
Титулов, начинающихся с кириллической заглавной, в базе 8 053 из 22 138
(36.4 %). Та же дыра открыта для немецких витрин — `Schwert` / `schwert`,
`Ärmel` / `ärmel`, — а это пять источников из одиннадцати.

Опасна здесь не величина ошибки, а её невидимость: запрос не падает, он
молча отвечает меньшим числом. AGENT_RULES §5 — ошибка влево дороже ошибки
вправо, и §14 — у измерения обязан быть отличим исход «нечем ответить».

**Что делает модуль.** Подменяет на каждом соединении `lower`, `upper` и
`like` питоновскими реализациями, знающими Unicode, и заводит коллацию
`NOCASE_RU` для `ORDER BY` и `=`. После этого наивный запрос выше становится
верным сам собой: чинить нужно было не конкретный замер, а инструмент, иначе
следующий замер повторит ошибку молча.

**Плата.** Подменённый `like` отключает оптимизацию LIKE через индекс. На
22k строк это незаметно. Переезд на Postgres (`HMB_DATABASE_URL`) снимает
вопрос целиком — там `lower()` и так Unicode-корректен, и модуль на
Postgres не подключается (см. `db.engine()`).
"""
from __future__ import annotations

import re
from functools import lru_cache

__all__ = ["attach", "install"]


def _lower(x):
    # Нетекстовые значения SQLite отдаёт из lower() как есть — повторяем.
    return x.lower() if isinstance(x, str) else x


def _upper(x):
    return x.upper() if isinstance(x, str) else x


@lru_cache(maxsize=512)
def _pattern(pat: str, escape: str | None) -> re.Pattern[str]:
    out: list[str] = []
    i = 0
    while i < len(pat):
        ch = pat[i]
        if escape and ch == escape and i + 1 < len(pat):
            out.append(re.escape(pat[i + 1]))
            i += 2
            continue
        out.append(".*" if ch == "%" else "." if ch == "_" else re.escape(ch))
        i += 1
    # re.IGNORECASE, а НЕ casefold(): casefold меняет длину строки ('ß' -> 'ss')
    # и сломал бы семантику «ровно один символ» у '_'. Для немецких витрин это
    # не теория — 'ß' встречается в названиях товаров.
    return re.compile(r"\A" + "".join(out) + r"\Z", re.DOTALL | re.IGNORECASE)


def _like(pat, value, escape=None):
    # SQLite вызывает like(Y, X) для выражения «X LIKE Y» — порядок обратный.
    if pat is None or value is None:
        return None
    return 1 if _pattern(str(pat), escape).match(str(value)) else 0


def _nocase_ru(a: str, b: str) -> int:
    a, b = a.casefold(), b.casefold()
    return (a > b) - (a < b)


def install(conn) -> None:
    """Повесить Unicode-осведомлённые lower/upper/like и коллацию NOCASE_RU.

    `conn` — сырое DBAPI-соединение sqlite3. Вызывается на каждом коннекте:
    функции и коллации живут в пределах соединения, не в файле базы.
    """
    conn.create_function("lower", 1, _lower, deterministic=True)
    conn.create_function("upper", 1, _upper, deterministic=True)
    conn.create_function("like", 2, _like, deterministic=True)
    conn.create_function("like", 3, _like, deterministic=True)
    conn.create_collation("NOCASE_RU", _nocase_ru)


def attach(engine) -> None:
    """Повесить `install` на каждый коннект SQLAlchemy-движка к SQLite.

    Отдельная функция, а не строчка внутри `db.engine()`, потому что движок к
    той же базе собирают и мимо `db` — тесты (`create_engine("sqlite://")`) и
    разовые скрипты. Там крючок `db` не сработает, а регистр нужен тот же.
    """
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _install(dbapi_conn, _rec):  # noqa: ANN001
        install(dbapi_conn)
