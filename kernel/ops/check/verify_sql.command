#!/bin/zsh
# =====================================================================
# verify_sql.command — сверить сырой SQL в скриптах с реальной схемой.
#
# Обёртка над scripts/verify_sql_columns.py (перенесён из recruit 15.09.2026).
# В recruit 31.07 новый скрипт сослался на несуществующую колонку, и ошибка
# вылезла уже на живой базе — хотя ловится статически за секунду.
#
# Пока в HMB-Market нет бэкенда с моделями SQLAlchemy — печатает это и выходит
# кодом 2: «проверено файлов: 0» — это НЕ «всё чисто» (AGENT_RULES §14).
#
# Запуск (из каталога бэкенда, когда он появится):
#   KERNEL_MODELS=app.models zsh kernel/ops/check/verify_sql.command <файл>.py
# =====================================================================
set -u
KERNEL_DIR="${0:A:h:h:h}"
BACKEND="${BACKEND_DIR:-}"
if [[ -z "$BACKEND" || ! -d "$BACKEND" ]]; then
  echo "⛔ бэкенда ещё нет (BACKEND_DIR не задан) — сверять нечего, файлов проверено: 0" >&2
  exit 2
fi
cd "$BACKEND" || exit 1
.venv/bin/python "$KERNEL_DIR/scripts/verify_sql_columns.py" "$@"
