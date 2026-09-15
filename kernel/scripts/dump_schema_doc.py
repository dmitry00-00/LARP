"""dump_schema_doc.py — `docs/SCHEMA.md` из метаданных SQLAlchemy.

Почему генератор, а не руками. В проекте 42 модели и 57 миграций. Схема,
переписанная вручную, расходится с базой на следующей же миграции, и хуже
всего то, что расхождение неотличимо от правды: документ выглядит одинаково
уверенно и когда прав, и когда врёт. До 11.08 `SCHEMA.md` описывал ЦЕЛЕВУЮ
схему ранней фазы — половины таблиц оттуда в базе нет, половины таблиц из
базы там нет.

Источник истины — `Base.metadata`, то есть те же объявления, по которым
Alembic сравнивает состояние. База для запуска не нужна.

    .venv/bin/python scripts/dump_schema_doc.py            # → docs/SCHEMA.md
    .venv/bin/python scripts/dump_schema_doc.py --stdout   # посмотреть глазами
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import Index, Table  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402

import importlib, os  # noqa: E402
_MODELS = os.environ.get("KERNEL_MODELS", "app.models")  # см. verify_sql_columns.py
importlib.import_module(_MODELS)  # регистрация всех моделей в метаданных
Base = importlib.import_module(_MODELS + ".base").Base  # noqa: E402

# Куда писать SCHEMA.md: KERNEL_DOCS_DIR (каталог docs проекта-потребителя);
# по умолчанию — docs/ рядом с kernel/ (в LARP это ~/LARP/docs). Копия из recruit
# считала путь по глубине дерева и на новом месте резолвилась в ~/docs — поймано
# проверкой переноса 15.09.2026.
_OUT = Path(os.environ.get("KERNEL_DOCS_DIR") or Path(__file__).resolve().parents[2] / "docs") / "SCHEMA.md"
_PG = postgresql.dialect()

# Группировка по смыслу, а не по алфавиту: плоский список из 60 таблиц
# нечитаем, а «где тут кандидаты» — первый вопрос к схеме. Таблица, не
# попавшая ни в одну группу, уходит в «Прочее» — это видно и чинится
# добавлением строки сюда, а не молчаливым исчезновением.
_GROUPS: list[tuple[str, tuple[str, ...]]] = [
    ("Кандидаты и опыт", ("candidate", "work_entr", "habr_")),
    ("Вакансии и требования", ("vacanc",)),
    # `one_of_*` объявлены в `models/ontology.py` — это взаимозаменяемые
    # требования («React ИЛИ Vue»), а не отдельная подсистема.
    ("Должности, роли, онтология", ("position", "role", "ontolog", "responsib",
                                    "one_of_")),
    ("Дерево инструментов", ("tool", "shadow_")),
    ("Матчинг и ранжирование", ("match_", "embedding", "response_event")),
    ("Приём данных (OpenClaw)", ("inbox_", "telegram_channel", "telegram_message",
                                 "company_source", "discovered_", "market_insight",
                                 "lead_")),
    ("Аутрич и контакты", ("outreach_",)),
    ("Воронка найма", ("pipeline", "project", "recruitment_task")),
    ("Компании", ("compan",)),
    ("Пользователи и доступ", ("user", "workspace", "refresh_token", "api_key",
                               "telegram_user", "telegram_link", "telegram_subscription",
                               "calendar", "google_")),
    ("Служебное", ("audit", "metric_snapshot", "notification", "webhook",
                   "inbound_webhook", "currency_rate")),
]


def _group_of(name: str) -> str:
    for title, prefixes in _GROUPS:
        if any(name.startswith(p) for p in prefixes):
            return title
    return "Прочее"


def _col_type(col) -> str:  # noqa: ANN001
    """Тип КАК В POSTGRES, а не как во внутреннем представлении.

    Без явного диалекта `Uuid` печатается как `CHAR(32)` (форма для SQLite,
    на котором гоняются тесты), а `JSONB` — как `JSON`. Документ о проде,
    описывающий типы тестовой базы, хуже отсутствующего: по нему пишут SQL.
    """
    try:
        return col.type.compile(dialect=_PG)
    except Exception:  # noqa: BLE001 — тип без поддержки диалекта
        return col.type.__class__.__name__


def _col_note(col) -> str:  # noqa: ANN001
    bits = []
    if col.primary_key:
        bits.append("PK")
    for fk in col.foreign_keys:
        bits.append(f"→ {fk.target_fullname}")
    if not col.nullable and not col.primary_key:
        bits.append("NOT NULL")
    if col.unique:
        bits.append("UNIQUE")
    if col.index:
        bits.append("index")
    if col.default is not None and getattr(col.default, "is_scalar", False):
        bits.append(f"default {col.default.arg!r}")
    elif col.server_default is not None:
        bits.append("server default")
    return " · ".join(bits)


def _table_md(t: Table) -> list[str]:
    out = [f"### `{t.name}`", ""]
    if t.comment:
        out += [t.comment, ""]
    out += ["| Колонка | Тип | Свойства |", "|---|---|---|"]
    for col in t.columns:
        out.append(f"| `{col.name}` | {_col_type(col)} | {_col_note(col)} |")

    # Составные и функциональные индексы — отдельно: именно в них лежат
    # правила уникальности, из-за которых данные теряются молча (0055, 0056).
    extra = [c for c in t.constraints if c.__class__.__name__ == "UniqueConstraint"]
    idxs = [i for i in t.indexes if isinstance(i, Index)]
    lines = []
    for c in extra:
        cols = ", ".join(f"`{x.name}`" for x in c.columns)
        lines.append(f"* UNIQUE ({cols})" + (f" — `{c.name}`" if c.name else ""))
    for i in idxs:
        try:
            cols = ", ".join(str(e) for e in i.expressions)
        except Exception:  # noqa: BLE001
            cols = ", ".join(c.name for c in i.columns)
        lines.append(f"* {'UNIQUE ' if i.unique else ''}index `{i.name}` ({cols})")
    if lines:
        out += ["", "**Индексы и ограничения:**", "", *lines]
    out.append("")
    return out


def build() -> str:
    tables = sorted(Base.metadata.tables.values(), key=lambda t: t.name)
    by_group: dict[str, list[Table]] = defaultdict(list)
    for t in tables:
        by_group[_group_of(t.name)].append(t)

    head = [
        "# Схема базы данных — по фактическим моделям",
        "",
        "> **Сгенерировано** `apps/backend/scripts/dump_schema_doc.py` из",
        "> `Base.metadata`. Руками не править — правка переживёт ровно до",
        "> следующего запуска. Менять надо модель, потом перегенерировать:",
        "> `cd apps/backend && .venv/bin/python scripts/dump_schema_doc.py`",
        "",
        f"Таблиц: **{len(tables)}**. Ревизия Alembic: см. "
        "`alembic/versions/` (последняя по номеру = head).",
        "",
        "Общее для почти всех таблиц: PK — `uuid`, мультитенантность через",
        "`workspace_id`, `created_at`/`updated_at` приходят из `TimestampMixin`",
        "(в файле модели их не видно — наивный grep по модели их не найдёт,",
        "см. `docs/AGENT_RULES.md` §1).",
        "",
        "---",
        "",
        "## Оглавление",
        "",
    ]
    order = [g for g, _ in _GROUPS] + ["Прочее"]
    for g in order:
        if by_group.get(g):
            anchor = g.lower().replace(" ", "-").replace(",", "").replace("(", "").replace(")", "")
            head.append(f"* [{g}](#{anchor}) — {len(by_group[g])} табл.")
    head += ["", "---", ""]

    body: list[str] = []
    for g in order:
        if not by_group.get(g):
            continue
        body += [f"## {g}", ""]
        for t in by_group[g]:
            body += _table_md(t)
        body.append("---")
        body.append("")
    return "\n".join(head + body)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(_OUT))
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()

    md = build()
    if args.stdout:
        print(md)
        return 0
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    n = len(Base.metadata.tables)
    print(f"✓ {out}  ({n} таблиц, {len(md.splitlines())} строк)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
