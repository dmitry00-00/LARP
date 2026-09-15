from __future__ import annotations

from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from hmb import config
from hmb.models import Base

_engine = None


def engine():
    global _engine
    if _engine is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        # SQLite — один писатель: длинный импорт без коммитов запирает базу для всех
        # остальных (поймано 15.09: `hmb import rulesets` упал на `database is locked`,
        # пока шёл обход календаря). Поэтому busy_timeout и коммит батчами в импортёрах.
        connect_args = {"timeout": 60} if config.DATABASE_URL.startswith("sqlite") else {}
        _engine = create_engine(config.DATABASE_URL, future=True, connect_args=connect_args)
        if config.DATABASE_URL.startswith("sqlite"):
            @event.listens_for(_engine, "connect")
            def _fk(dbapi_conn, _rec):  # noqa: ANN001
                dbapi_conn.execute("PRAGMA foreign_keys=ON")
                dbapi_conn.execute("PRAGMA journal_mode=WAL")
        # Журнал массовых правок — крючок на движке, как в recruit.
        try:
            from kernel.db.mutation_audit import install_listener as install
            install(_engine)
        except Exception:  # noqa: BLE001 — журнал не имеет права ронять приём
            pass
    return _engine


# Первая правка схемы после create_all (15.09.2026, image_url у lots). Alembic
# ещё не заведён; до него — этот реестр добавленных колонок: create_all
# новые колонки в существующую таблицу НЕ добавляет, и без этого списка
# свежая модель падает на старой базе с «no such column».
_ADDED_COLUMNS: list[tuple[str, str, str]] = [
    ("lots", "image_url", "VARCHAR(800)"),
]


def _ensure_columns(eng) -> list[str]:
    from sqlalchemy import inspect, text
    added: list[str] = []
    insp = inspect(eng)
    with eng.begin() as conn:
        for table, col, ddl in _ADDED_COLUMNS:
            if table in insp.get_table_names() and col not in {c["name"] for c in insp.get_columns(table)}:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
                added.append(f"{table}.{col}")
    return added


def init_db() -> None:
    """Пока без Alembic: create_all + реестр добавленных колонок. Долг записан в config.py."""
    Base.metadata.create_all(engine())
    _ensure_columns(engine())


@contextmanager
def session() -> Iterator[Session]:
    s = sessionmaker(bind=engine(), future=True, expire_on_commit=False)()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
