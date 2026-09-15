# kernel/ — домен-независимое ядро, перенесённое из recruit

> Собрано **15.09.2026** копированием из `~/recruit` (ветка
> `claude/phase-3-development-tdUYi`, коммит `7d28f91`). Импорты переписаны
> `openclaw.*` → `kernel.*`, содержимое модулей не менялось, кроме
> перечисленного в «Что изменено». **196 тестов проходят на новом месте**
> (`PYTHONPATH=. python -m pytest -q`, venv recruit/openclaw).
>
> Это библиотека и шаблон, а не общая схема данных (ROADMAP, последний
> раздел): свою БД HMB-Market держит сам, ядро её не знает.

## Что здесь и откуда

| путь в kernel | откуда в recruit | строк | зачем HMB-Market |
|---|---|---:|---|
| `kernel/telemetry.py` | `openclaw/telemetry.py` | 703 | `ApiMeter`: счётчик обращений к Telegram, флуды, самокалибрующийся потолок, токен-ковш, адаптивный темп. **До первого массового обхода**, не после первого бана |
| `kernel/sidefiles.py` | `openclaw/sidefiles.py` | 130 | файлы состояния рядом с сессией; суффиксы под несколько аккаунтов |
| `kernel/accounts.py` | `openclaw/accounts.py` | 178 | детерминированный шард каналов по аккаунтам (`TG_ACCOUNTS`) |
| `kernel/state.py` | `openclaw/state.py` | 416 | SQLite-стейт: обработанные посты, прогоны скиллов, вызовы LLM, отпечатки дублей. Таблицы `channel_candidates`/`github_repos` — recruit-специфика, при первой миграции стейта убрать |
| `kernel/ner_extractor.py` | `openclaw/ner_extractor.py` | 502 | словарный экстрактор по алиасам: кириллические границы, короткие идентификаторы, `_Guard.forbid` (контекст для ключей-ловушек), «имя узла — тоже ключ». `feed.json.slots[].{id, aliases}` — уже нужной формы |
| `kernel/clients/tg_web.py` | `openclaw/clients/tg_web.py` | 308 | чтение `t.me/s/<канал>` — **вне квоты**, ноль домена. Транспорт Горизонта 1 |
| `kernel/clients/telegram.py` | `openclaw/clients/telegram.py` | 505 | MTProto через Telethon с замком на двери (лимиты спрашивает клиент, не скилл), сохранение вложений **до** разбора |
| `kernel/clients/llm.py` | `openclaw/clients/llm.py` | 289 | OpenAI-совместимый клиент: автоопределение модели LM Studio, стражи `max_tokens`, учёт токенов |
| `kernel/skills/dedup.py` | `openclaw/skills/dedup.py` | 315 | SimHash-дедуп, чистый Python. Порог 8 бит откалиброван на вакансиях — **перемерить на лотах** |
| `kernel/skills/salary.py` | `openclaw/skills/salary.py` | 249 | парсер «от/до/N–M/к/тыс + валюта». Для лота это парсер **цены** как есть; и образец для парсера обмеров |
| `kernel/db/fx.py` | `app/services/fx.py` | 393 | курсы: якорь `usd_per`, фетч раз в час, статический фолбэк, классификатор валют (₸ ₽ $ € грн) |
| `kernel/db/mutation_audit.py` | `app/core/mutation_audit.py` | 203 | крючок на Engine: любая правка ≥500 строк пишется в журнал |
| `ops/lib/mutation_journal.py` | `ops/lib/mutation_journal.py` | 159 | сам журнал `analysis/mutations/YYYY-MM.jsonl` |
| `scripts/verify_sql_columns.py` | `apps/backend/scripts/…` | 289 | страж пар «таблица→колонка» по метаданным SQLAlchemy, база не нужна |
| `scripts/dump_schema_doc.py` | `apps/backend/scripts/…` | 200 | генератор `docs/SCHEMA.md` из моделей |
| `ops/rotate_logs.command` | `ops/rotate_logs.command` | 120 | copytruncate для launchd-логов (rename ломает открытые дескрипторы) |
| `ops/check/verify_sql.command` | `ops/check/verify_sql.command` | — | обёртка; пока бэкенда нет — выходит кодом 2, а не «✓ проверено 0» |
| `tests/` | `apps/openclaw/tests/` | 11 файлов | 196 тестов (в recruit те же 11 файлов дают 198 — минус два вырезанных) |
| `kernel/config.py` | `openclaw/config.py` | урезан | только ключи, которые читают перенесённые модули |

## Что изменено относительно recruit

* `config.py` — оставлены только 10 ключей, которые читают модули:
  `openclaw_home`, `openclaw_sqlite_path`, `llm_base_url/api_key/model/
  timeout_sec/max_tokens/max_tokens_local`, `tg_api_id/api_hash/session_path`,
  `openclaw_mock_telegram`, `watch_interval_sec`, `max_batch_size`. Env-файл —
  `.env.ingest`. **Дефолты путей** `/var/lib/openclaw/…` → `/var/lib/hmb-ingest/…`.
  Имена полей `openclaw_*` сохранены намеренно: их читают модули,
  переименование — отдельная правка с тестами.
* `kernel/__init__.py`, `clients/__init__.py`, `skills/__init__.py` — пустые
  (в recruit там docstring и `__version__`, читателей у которого нет).
* `clients/telegram.py` — ключ каталога вложений `RECRUIT_ATTACHMENT_ROOT` →
  `ATTACHMENT_ROOT`. **Фото по-прежнему НЕ качаются**: `_MIME_EXT` знает только
  PDF/DOCX/DOC, `msg.photo` не смотрится. Это первая правка Горизонта 1
  (DATA_SOURCES §1: фото вмятины — единственное свидетельство состояния).
  Учёт стоимости скачивания против ковша (`telemetry.download_cost`) уже есть.
* `db/fx.py` — модель `CurrencyRate` заменена на `CurrencyRateMixin` (проект
  объявляет модель на своём `Base`), IO-функции принимают `model`;
  `vacancy_salary_norm`/`candidate_salary_norm` → `range_norm`/`point_norm`
  (старые имена — алиасы). **Добавлены алиасы валют** `₸ тг тенге → KZT`,
  `₽ руб р. → RUB`, `£ → GBP`: в recruit `classify_currency("₸")` отдавал
  `unknown` — для базы в KZ это не хвост.
* `db/fx.py` — логгер `app.fx` → `kernel.fx`.
* `db/mutation_audit.py` — путь к `ops/lib` и корню: `parents[4]` → `parents[2]`.
* `scripts/verify_sql_columns.py`, `dump_schema_doc.py` — пакет моделей из
  `KERNEL_MODELS` (по умолчанию `app.models`), не хардкод; каталоги
  `KERNEL_OPS_DIR` (по умолчанию `kernel/ops`) и `KERNEL_DOCS_DIR` (по умолчанию
  `docs/` рядом с `kernel/`). В копии recruit оба пути считались по глубине
  дерева и на новом месте резолвились в `~/ops` и `~/docs/SCHEMA.md` — поймано
  независимой проверкой переноса 15.09, не тестами: тестов у стражей нет.
* `tests/test_flood_guard.py` — вырезаны два теста про `check_dead_channels`
  (скилл не перенесён); урок оставлен комментарием в файле.
* Строки `X-Title`, User-Agent, `.env.openclaw` в сообщениях — переименованы.

## Что перенесено, но требует адаптации до первого запуска

* `scripts/dump_schema_doc.py:_GROUPS` — группировка таблиц по префиксам
  recruit (`candidate`, `vacanc`, `inbox_`…). Для чужой схемы всё уйдёт в
  «Прочее» — переписать под `lots`/`slots`/`makers` с первой моделью.
* `ops/rotate_logs.command` — маски `recruit-*.log` и каталог `recruit-archive`
  в рабочем коде. На HMB-Market скрипт не найдёт ни одного файла, пока имена
  логов не заданы.
* `skills/dedup.py` — порог 8 бит и `RETENTION_DAYS=30` откалиброваны на
  вакансиях; на лотах перемерить.
* `db/fx.py:_ALIASES` — голое «Р» как рубль сознательно НЕ добавлено (слишком
  широко без замера), только «Р.», «РУБ», «₽».

## Ручки окружения, которые модули читают напрямую

`WATCH_API_BUDGET_PER_DAY` (700) · `WATCH_HARD_FLOOD_SEC` · `WATCH_CEILING_*` ·
`WATCH_BURST_SHARE` · `WATCH_PACE_*` · `WATCH_MAX_CHANNELS_PER_RUN` ·
`WATCH_EST_REQUESTS_PER_CHANNEL` · `TG_ACCOUNTS` (+ `TG_*_<ACC>`) ·
`WATCH_NEW_CHANNELS_PER_DAY` · `ATTACHMENT_ROOT` (абсолютный путь: `~` и
`$HOME` в `.env` шеллом не раскрываются — AGENT_RULES §9).

## Что в ядро сознательно НЕ взято

* `skills/watch_channels.py`, `watch_web.py` — цикл обхода привязан к
  `RecruitClient` и порогам длины резюме; переписывать сток под `inbox_items`
  HMB-Market, взяв структуру.
* `classify_post`, `topic_gate`, `regex_prefilter`, `template_extractor` —
  промпты и словари про IT. Брать **структуру** и правило 13.09: вердикт гейта
  `unknown` («словарь молчит») ≠ `not_ours` — отсев только по второму.
* `services/matching.py` (898 строк) — намертво на `WorkEntry`/`VacancyRequirement`;
  переносится контракт исходов `matched/gap/extra` + новый `conflict`, не код.
* `hybrid_score.py`, `ranker.py`, эмбеддинги — ROADMAP «чего не делаем».
* Celery, построчные `notifications`, `Tool.status='candidate'` — мёртвое или
  вредное в recruit, см. `docs/sessions/SESSION_2026_09_15_RECRUIT_TRANSFER.md`.

## Как запустить тесты

```bash
cd ~/LARP/kernel
PYTHONPATH=. ~/recruit/apps/openclaw/.venv/bin/python -m pytest -q   # пока нет своего venv
# свой venv: python3 -m venv .venv && .venv/bin/pip install -e '.[test]'
```
