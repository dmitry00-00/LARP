"""verify_sql_columns.py — сверить сырой SQL в скриптах с реальной схемой.

Зачем. Скрипты в ``scripts/`` и ``ops/`` ходят в базу через ``text()``, а
такой SQL никто не проверяет до запуска: ни тайпчекер, ни линтер, ни тесты.
Ошибка в имени колонки всплывает на проде, посреди долгого прогона, и
выглядит как сбой данных.

За одну сессию 19.07 это случилось трижды: ``api_keys.key_prefix`` (нет
такой колонки — есть ``name``), ``inbox_items.created_at`` (есть, приходит
из миксина — я зря «чинил»), ``candidates.grade`` (нет — грейд на
``work_entries``). Каждый раз цена была один потерянный прогон.

Скрипт извлекает из SQL пары «таблица → колонка» и сверяет их с метаданными
SQLAlchemy. Проверка статическая: подключение к базе не нужно.

    .venv/bin/python scripts/verify_sql_columns.py                # все скрипты
    .venv/bin/python scripts/verify_sql_columns.py business_metrics.py

## Правка 01.08 — страж молча не смотрел на треть SQL

Три дыры, каждая давала не ложную тревогу, а **тишину**, — то есть выглядела
как «всё чисто». Подробности у соответствующих регексов, коротко:

1. Литерал с префиксом `f` не распознавался (`r?` вместо полного набора
   префиксов). 37 блоков из 105 — вся диагностика с интерполяцией `{fresh}`.
2. Хуже: на этих блоках `.*?` с DOTALL не останавливался, а доезжал до кавычки
   через полфайла, склеивая два запроса и код между ними в один «блок».
   Алиасы одного запроса подмешивались к колонкам другого.
3. `\\s*` перед алиасом матчил перевод строки, поэтому `FROM d` + `JOIN t o`
   читалось как «таблица d, алиас JOIN», и таблица за CTE выпадала целиком.

После правки покрытие: **281 → 342** различных сверенных пар
«таблица·колонка», ни одна не потеряна, новых несоответствий не появилось.

## Чего страж по-прежнему НЕ видит

Только **квалифицированные** ссылки вида `alias.column`. Голая колонка в
одно­табличном запросе не проверяется — а именно так написан живой баг в
`ops/check/check_db.command`:

    SELECT workspace_id FROM api_keys WHERE key_prefix='ock_9HvbMw'

Колонки `key_prefix` в `api_keys` нет (есть `name` и `key_hash`) — тот самый
случай из 19.07, ради которого страж и появился. Он его не ловит.
"""
from __future__ import annotations

import re
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
# Пакет моделей проекта задаётся переменной KERNEL_MODELS (по умолчанию `app.models`):
# ядро не знает, как называется бэкенд, который его подключил.
_MODELS = os.environ.get("KERNEL_MODELS", "app.models")

import importlib  # noqa: E402
importlib.import_module(_MODELS)  # регистрирует все таблицы в метаданных
Base = importlib.import_module(_MODELS + ".base").Base  # noqa: E402

_SCRIPTS = Path(__file__).resolve().parent
# ops/ проекта-потребителя (KERNEL_OPS_DIR); по умолчанию — kernel/ops. Копия из
# recruit считала путь по глубине дерева и на новом месте резолвилась в ~/ops
# (поймано проверкой переноса 15.09.2026).
_OPS = Path(os.environ.get("KERNEL_OPS_DIR") or _SCRIPTS.parent / "ops")

# alias.column
_QUALIFIED_RE = re.compile(r"\b([a-z][a-z0-9_]*)\.([a-z_][a-z0-9_]*)\b")

# Слова, которые синтаксически выглядят как алиас, но им не являются.
_NOT_ALIASES = {
    "on", "where", "group", "order", "limit", "having", "as", "using",
    "left", "right", "inner", "outer", "cross", "join", "select", "with",
    "union", "and", "or", "not", "distinct", "interval",
}

# FROM/JOIN <table> [AS] [alias]
#
# Ключевые слова исключаются ЛУКАХЕДОМ, а не постфактум. Разница не
# косметическая: `findall` не даёт совпадениям перекрываться, поэтому если
# группа алиаса СЪЕСТ слово JOIN, то и таблица за ним пропадёт из проверки
# целиком. На таком SQL
#
#     FROM d
#     JOIN inbox_items o
#       ON o.id = d.x
#
# прежний вариант (`\s*(?:AS\s+)?([a-z]\w*)?`) видел ровно одну пару —
# «таблица d, алиас JOIN», — и все `o.*` уходили без сверки: CTE `d` в схеме
# нет, так что ветка «не таблица» молча пропускала весь блок. Лукахед
# обрывает совпадение сразу после `d`, и следующий поиск находит
# `inbox_items o`.
#
# Список ключевых слов — тот же `_NOT_ALIASES`, чтобы не завести вторую копию,
# которая разойдётся с первой (AGENT_RULES §7). Отсюда же требование, чтобы
# он был объявлен ВЫШЕ.
_TABLE_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+([a-z_][a-z0-9_]*)"
    r"(?:\s+(?:AS\s+)?(?!(?:" + "|".join(sorted(_NOT_ALIASES)) + r")\b)([a-z][a-z0-9_]*))?",
    re.IGNORECASE,
)


def _tables() -> dict[str, set[str]]:
    return {
        name: {c.name for c in tab.columns}
        for name, tab in Base.metadata.tables.items()
    }


# Префикс строкового литерала. `r?` пропускал `text(f"""…` — а именно в таком
# виде написан весь SQL с интерполяцией окна (`{fresh}`, `{days}`), то есть
# почти все диагностические скрипты. Замер 01.08: 37 из 105 блоков были
# f-строками, и это ещё не вся цена — см. комментарий к `_TRIPLE_RE`.
_PREFIX = r"(?:[rRbBuUfF]{0,2})"

# ⚠ Мимо f-строк парсер не просто проходил — он ЛОМАЛСЯ об них. `.*?` с DOTALL
# начинал матч от предыдущего валидного `text("""`, а закрывающие кавычки искал
# уже за f-блоком: получался «блок», склеенный из двух запросов и кода между
# ними. Алиасы одного запроса подмешивались к колонкам другого, так что
# возможны были и пропуски, и ложные срабатывания.
_TRIPLE_RE = re.compile(r'text\(\s*' + _PREFIX + r'"""(.*?)"""', re.DOTALL)

# Однострочные литералы. Два отличия от прежнего варианта:
#
# 1. `[^"\n]*` вместо `.*?` с DOTALL — литерал в кавычках не может содержать
#    перевод строки, зато `.*?` с DOTALL мог доехать до кавычки через полфайла
#    и склеить два несвязанных запроса в один «блок».
# 2. Ловится ЦЕПОЧКА соседних литералов, а не один. Так написан SQL, разбитый
#    по строкам — например в `check_db.command`:
#
#        text("SELECT p.name, COUNT(v.id) FROM vacancies v "
#             "JOIN positions p ON p.id = v.position_id")
#
#    Python склеивает такие литералы сам, и проверять надо результат склейки:
#    у первого куска есть `FROM vacancies v`, у второго — `v.position_id`, и
#    порознь ни один не проверяется. Прежняя версия доставала их случайно,
#    тем самым спанящим `.*?`; здесь это делается намеренно.
_INLINE_RUN_RE = re.compile(r'text\(\s*((?:' + _PREFIX + r'"[^"\n]*"\s*)+)\)')
_ONE_LITERAL_RE = re.compile(r'"([^"\n]*)"')


# SQL, вынесенный в константу модуля, а в `text()` попадающий переменной:
#
#     _SQL = """SELECT … FROM candidates c …"""
#     ...
#     await db.execute(text(_SQL.format(...)), params)
#
# Так пишут, когда запрос надо собрать из кусков или переиспользовать. До
# 11.08 страж такой файл проверял НУЛЁМ блоков и печатал «✓ все колонки
# существуют» — то есть молчание об отсутствии ошибок и молчание о том, что
# он ничего не смотрел, выглядели одинаково (AGENT_RULES §3: признак наличия
# ≠ признак работоспособности).
#
# Ловим не «переменную с именем `_SQL`», а «тройной литерал, похожий на
# запрос»: имя константы — соглашение, которое каждый пишет по-своему, а
# `SELECT … FROM` — свойство самой строки.
_CONST_RE = re.compile(r'=\s*' + _PREFIX + r'"""(.*?)"""', re.DOTALL)
_LOOKS_SQL_RE = re.compile(r'\bSELECT\b.*?\bFROM\b', re.DOTALL | re.IGNORECASE)


def _sql_blocks(src: str) -> list[str]:
    """Содержимое каждого text(\"\"\"...\"\"\"), text(\"...\") и SQL-константы."""
    inline = [
        # Склейка без разделителя — ровно как это делает сам Python.
        "".join(_ONE_LITERAL_RE.findall(run))
        for run in _INLINE_RUN_RE.findall(src)
    ]
    triple = _TRIPLE_RE.findall(src)
    # Из констант берём только те, что действительно похожи на запрос:
    # докстринги и обычные многострочные тексты иначе пошли бы в разбор и
    # дали бы ложные срабатывания на словах вида «FROM» в прозе.
    consts = [b for b in _CONST_RE.findall(src) if _LOOKS_SQL_RE.search(b)]
    # Константа может попасть и в `triple` (если её же обернули в `text()`),
    # поэтому дубли убираем — иначе одна ошибка печаталась бы дважды.
    seen = set(triple) | set(inline)
    return triple + inline + [c for c in consts if c not in seen]


# Комментарии внутри SQL — это проза, а не запрос. В проекте принято
# объяснять в них ПРОШЛЫЕ ошибки («первая версия писала `c.grade`»), и
# страж честно находил там несуществующую колонку — то есть ругался ровно
# на предупреждение о самом себе. Второй случай мягче, но противнее:
# `-- как «инструментов нет» (list(r.tools or []))` в комментарии внутри
# запроса давал жалобу на алиас результата, которого в SQL нет вовсе.
_SQL_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)


def _strip_sql_comments(sql: str) -> str:
    return _SQL_COMMENT_RE.sub(" ", sql)


def check_file(path: Path, schema: dict[str, set[str]]) -> list[str]:
    problems: list[str] = []
    src = path.read_text(encoding="utf-8")

    for sql in map(_strip_sql_comments, _sql_blocks(src)):
        # alias → таблица, плюс сами имена таблиц как «алиасы себя»
        alias_map: dict[str, str] = {}
        for table, alias in _TABLE_RE.findall(sql):
            t = table.lower()
            if t not in schema:
                # CTE и подзапросы — не таблицы; их пропускаем молча,
                # иначе шум забьёт настоящие находки.
                continue
            alias_map[t] = t
            if alias and alias.lower() not in _NOT_ALIASES:
                alias_map[alias.lower()] = t

        for alias, column in _QUALIFIED_RE.findall(sql):
            table = alias_map.get(alias.lower())
            if table is None:
                continue
            if column.lower() not in schema[table]:
                near = sorted(
                    c for c in schema[table]
                    if c.startswith(column[:4]) or column.startswith(c[:4])
                )
                hint = f"  похожие: {', '.join(near)}" if near else ""
                problems.append(
                    f"{path.name}: {table}.{column} — такой колонки нет.{hint}"
                )
    return problems


def main() -> int:
    schema = _tables()
    targets = sys.argv[1:]

    files: list[Path] = []
    missing: list[str] = []
    if targets:
        # ⚠ ЗДЕСЬ БЫЛ ТИХИЙ ЗЕЛЁНЫЙ (найдено 06.09).
        # Аргумент резолвился ТОЛЬКО как `_SCRIPTS / t`, а несуществующий путь
        # молча выпадал на фильтре `f.exists()` ниже. Итог: вызов с любым
        # неверным путём печатал «✓ Все колонки в SQL существуют. Проверено
        # файлов: 0» и возвращал 0 — сторож отвечал «да» на вопрос, которого
        # не проверял. Ровно третий исход из AGENT_RULES §14, свёрнутый в
        # «успех». Теперь путь ищется в трёх местах, а ненайденное называется
        # вслух и роняет прогон.
        _ROOT = _OPS.parent
        for t in targets:
            cand = [_SCRIPTS / t, _ROOT / t, Path(t)]
            hit = next((c for c in cand if c.exists()), None)
            if hit is None:
                missing.append(t)
            else:
                files.append(hit)
    else:
        files = sorted(_SCRIPTS.glob("*.py"))
        files += sorted(_OPS.rglob("*.command"))
    files = [f for f in files if f.exists() and f.name != Path(__file__).name]

    if missing:
        print(f"✗ НЕ НАЙДЕНО файлов: {len(missing)}")
        for m in missing:
            print(f"    {m}")
        print("  Путь ищется от apps/backend/scripts/, от корня репозитория")
        print("  и как есть. Ничего не проверено — это НЕ «всё хорошо».")
        return 2

    if targets and not files:
        # Файл нашёлся, но до проверки не дошёл: единственная причина —
        # фильтр «сам себя не проверяю». Печатаем это отдельно, иначе ниже
        # встанет ✓ при нулевом знаменателе — та же беда, что и с missing.
        print("ⓘ проверять нечего: указан только сам verify_sql_columns.py")
        print("  Ничего не проверено — это НЕ «всё хорошо».")
        return 2

    all_problems: list[str] = []
    for f in files:
        all_problems += check_file(f, schema)

    unique = list(dict.fromkeys(all_problems))  # dedup, порядок сохранён
    if unique:
        print(f"НАЙДЕНО {len(unique)} несоответствий схеме:\n")
        for p in unique:
            print(f"  ✗ {p}")
        print(f"\nПроверено файлов: {len(files)}")
        return 1


    print(f"✓ Все колонки в SQL существуют. Проверено файлов: {len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
