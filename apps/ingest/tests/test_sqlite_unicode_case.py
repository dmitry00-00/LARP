"""Регистр не-ASCII в SQLite: lower/upper/LIKE и коллация.

Регрессия, ради которой тест написан (замер 16.09.2026 на живой базе):
`where lower(title) like '%робот%'` вернул 2 лота из 3 — «Робот-коробка» не
совпал, потому что SQLite складывает регистр только для ASCII. Ошибка
невидима: запрос не падает, он молча отвечает меньшим числом.

Первый тест намеренно пришпиливает исходное поведение движка: если однажды
SQLite соберут с ICU и `lower()` начнёт понимать кириллицу сам, тест упадёт,
и `hmb/sqlite_text.py` можно будет выбросить, а не таскать вечно.
"""
import sqlite3

import pytest
from hmb import sqlite_text
from sqlalchemy import create_engine, text

# Три реальных заголовка с allrpg `/exchange/19..21/` — тот самый замер.
ROBOTS = ["Трехметровый робот-паук", "Робот-коробка", "Разваливающийся робот (дроид)"]


@pytest.fixture()
def raw():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_sqlite_folds_only_ascii_without_us(raw):
    """Свидетельство проблемы. Падение = движок починили, модуль лишний."""
    assert raw.execute("select lower('ROBOT-Box')").fetchone()[0] == "robot-box"
    assert raw.execute("select lower('РОБОТ-Коробка')").fetchone()[0] == "РОБОТ-Коробка"
    assert raw.execute("select 'Робот' like '%робот%'").fetchone()[0] == 0


def test_install_fixes_lower_and_upper(raw):
    sqlite_text.install(raw)
    assert raw.execute("select lower('РОБОТ-Коробка')").fetchone()[0] == "робот-коробка"
    assert raw.execute("select upper('робот')").fetchone()[0] == "РОБОТ"
    assert raw.execute("select lower('Schwert mit Ärmel')").fetchone()[0] == "schwert mit ärmel"
    # Нетекстовые значения SQLite отдаёт как есть — поведение сохранено.
    assert raw.execute("select lower(42)").fetchone()[0] == 42
    assert raw.execute("select lower(NULL)").fetchone()[0] is None


def test_like_is_case_insensitive_for_cyrillic(raw):
    sqlite_text.install(raw)
    assert raw.execute("select 'Робот' like '%робот%'").fetchone()[0] == 1
    assert raw.execute("select 'РОБОТ-Коробка' like '%робот%'").fetchone()[0] == 1
    assert raw.execute("select 'Меч' like '%шлем%'").fetchone()[0] == 0


def test_like_handles_german_shop_titles(raw):
    """Пять источников из одиннадцати — немецкие витрины."""
    sqlite_text.install(raw)
    assert raw.execute("select 'Ärmel aus Leder' like 'ärmel%'").fetchone()[0] == 1
    assert raw.execute("select 'GROSSES SCHWERT' like '%schwert%'").fetchone()[0] == 1


def test_underscore_still_means_exactly_one_char(raw):
    """Почему re.IGNORECASE, а не casefold(): casefold('ß') == 'ss' сдвинул бы длину."""
    sqlite_text.install(raw)
    assert raw.execute("select 'Straße' like 'Stra_e'").fetchone()[0] == 1
    assert raw.execute("select 'Strasse' like 'Stra_e'").fetchone()[0] == 0


def test_like_escape_and_null(raw):
    sqlite_text.install(raw)
    assert raw.execute(r"select '50%' like '50\%' escape '\'").fetchone()[0] == 1
    assert raw.execute(r"select '5012' like '50\%' escape '\'").fetchone()[0] == 0
    assert raw.execute("select NULL like '%x%'").fetchone()[0] is None
    assert raw.execute("select 'x' like NULL").fetchone()[0] is None


def test_nocase_ru_collation(raw):
    sqlite_text.install(raw)
    assert raw.execute("select 'Робот' = 'робот' collate NOCASE_RU").fetchone()[0] == 1
    rows = raw.execute(
        "select v from (select 'бригантина' v union all select 'Авентайл')"
        " order by v collate NOCASE_RU"
    ).fetchall()
    assert [r[0] for r in rows] == ["Авентайл", "бригантина"]


def test_attach_covers_sqlalchemy_engine():
    """Движок собирают и мимо `db` — тесты и разовые скрипты."""
    eng = create_engine("sqlite://")
    sqlite_text.attach(eng)
    with eng.connect() as c:
        assert c.execute(text("select lower('Робот')")).scalar() == "робот"


def test_engine_finds_all_three_robots(tmp_path, monkeypatch):
    """Сама регрессия, через боевой путь `db.engine()`: было 2 из 3, стало 3 из 3."""
    from hmb import config
    from hmb import db as dbm

    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{tmp_path / 'probe.sqlite'}")
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(dbm, "_engine", None)

    eng = dbm.engine()
    with eng.begin() as c:
        c.execute(text("create table lots (title text)"))
        for t in ROBOTS:
            c.execute(text("insert into lots values (:t)"), {"t": t})
    with eng.connect() as c:
        assert c.execute(text("select count(*) from lots where lower(title) like '%робот%'")).scalar() == 3
        assert c.execute(text("select count(*) from lots where title like '%робот%'")).scalar() == 3
    eng.dispose()
    monkeypatch.setattr(dbm, "_engine", None)


def test_sqlite_connect_is_readonly(tmp_path, monkeypatch):
    """Замер не имеет права записать в прод-базу — даже опечаткой."""
    from hmb import config
    from hmb import db as dbm

    path = tmp_path / "probe.sqlite"
    sqlite3.connect(path).executescript("create table lots (title text); insert into lots values ('Робот-коробка');")
    monkeypatch.setattr(config, "DATABASE_URL", f"sqlite:///{path}")

    conn = dbm.sqlite_connect(readonly=True)
    try:
        assert conn.execute("select count(*) from lots where lower(title) like '%робот%'").fetchone()[0] == 1
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("delete from lots")
    finally:
        conn.close()
