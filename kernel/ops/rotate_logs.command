#!/bin/zsh
# rotate_logs.command — ротация файлов логов recruit в ~/Library/Logs: архивирует хвост и обнуляет файл на месте.
#
# Зачем: ротации файлов в проекте не было ВООБЩЕ (сверено 09.09.2026).
# `com.recruit.scheduler` чистит строки `telegram_message_log` в БД, файлов не
# касается; записи в /etc/newsyslog.d про recruit нет. К 09.09 набежало:
# recruit-backend.log 2.5 ГБ, openclaw 215 МБ, backend.err 171 МБ.
#
# ПОЧЕМУ НЕ newsyslog. Он ротирует ПЕРЕИМЕНОВАНИЕМ, а логи держит открытыми
# launchd (StandardOutPath), и дескриптор переживает переименование: демон
# продолжил бы писать в переименованный файл, а новый остался бы пустым
# навсегда. Проверено экспериментом 09.09: launchd открывает лог с O_APPEND,
# поэтому обнуление НА МЕСТЕ (`: > файл`) безопасно — следующая запись идёт
# с нулевого смещения, дыры из NUL не возникает. Отсюда copytruncate, а не
# rename; своего демона тоже не нужно.
#
# Цена, которую платим осознанно: между копированием хвоста и обнулением
# строки, записанные в эту миллисекунду, теряются. Для логов приемлемо, для
# журналов правок — нет (те живут в analysis/mutations, здесь не трогаются).
#
# Read-only без --apply: печатает, что сделал бы. Запуск: zsh ops/rotate_logs.command [--apply]
#
# ── Как это читать ───────────────────────────────────────────────────
# Таблица показывает ВСЕ логи recruit, а не только тронутые: знаменатель
# важнее галочки. Колонка «решение»:
#   ротация  — файл больше порога, будет заархивирован и обнулён;
#   в норме  — меньше порога, не трогаем.
# «Хвост» — сколько последних мегабайт уезжает в архив; ВСЁ, что старше,
# теряется безвозвратно. Архивы лежат в ~/Library/Logs/recruit-archive,
# на каждый лог хранится не больше KEEP_ARCHIVES штук.
# Если файлов не нашлось вовсе — это отдельное состояние, скрипт скажет
# «НЕ НАЙДЕНО НИ ОДНОГО ЛОГА» и выйдет с кодом 2: пустая таблица не должна
# читаться как «всё в норме».

set -uo pipefail

LOG_DIR="$HOME/Library/Logs"
ARCHIVE_DIR="$LOG_DIR/recruit-archive"
MAX_MB=${ROTATE_MAX_MB:-64}        # больше этого — ротируем
TAIL_MB=${ROTATE_TAIL_MB:-16}      # столько последних МБ уезжает в архив
KEEP_ARCHIVES=${ROTATE_KEEP:-5}    # архивов на один лог

APPLY=0
[[ "${1:-}" == "--apply" ]] && APPLY=1

echo "════════════════════════════════════════════════════════════════"
echo " Ротация логов recruit — $(date '+%Y-%m-%d %H:%M')"
echo "════════════════════════════════════════════════════════════════"
if (( APPLY )); then
  echo " Режим: --apply (файлы будут обнулены)"
else
  echo " Режим: показ. Ничего не меняется. Для действия: --apply"
fi
echo " Порог: ${MAX_MB} МБ · хвост в архив: ${TAIL_MB} МБ · архивов на лог: ${KEEP_ARCHIVES}"
echo ""

# Глоб в zsh при nomatch роняет команду (CLAUDE.md, «Ловушки») → find.
FILES=()
while IFS= read -r f; do FILES+=("$f"); done < <(
  find "$LOG_DIR" -maxdepth 1 -type f \( -name 'recruit-*.log' -o -name 'recruit-*.err' \) 2>/dev/null | sort
)

if (( ${#FILES[@]} == 0 )); then
  echo "⚠ НЕ НАЙДЕНО НИ ОДНОГО ЛОГА в $LOG_DIR"
  echo "  Это не «всё в норме»: скрипту нечем было ответить."
  exit 2
fi

printf "%-34s %10s  %s\n" "файл" "размер" "решение"
printf "%-34s %10s  %s\n" "──────────────────────────────────" "──────────" "───────"

rotated=0
freed_mb=0
for f in "${FILES[@]}"; do
  bytes=$(stat -f %z "$f")
  mb=$(( bytes / 1024 / 1024 ))
  name=$(basename "$f")
  if (( mb <= MAX_MB )); then
    printf "%-34s %7d МБ  в норме\n" "$name" "$mb"
    continue
  fi
  printf "%-34s %7d МБ  ротация\n" "$name" "$mb"
  rotated=$(( rotated + 1 ))
  freed_mb=$(( freed_mb + mb - TAIL_MB ))
  (( APPLY )) || continue

  mkdir -p "$ARCHIVE_DIR"
  stamp=$(date '+%Y%m%d-%H%M%S')
  arc="$ARCHIVE_DIR/$name.$stamp.gz"
  if ! tail -c $(( TAIL_MB * 1024 * 1024 )) "$f" | gzip -c > "$arc"; then
    echo "   ✗ архив не записался, файл НЕ обнуляю: $arc"
    continue
  fi
  # Обнуление на месте: тот же inode, дескриптор launchd остаётся валидным.
  : > "$f"
  echo "   ✓ архив $(basename "$arc") ($(stat -f %z "$arc" | awk '{printf "%.1f МБ", $1/1048576}')), файл обнулён"

  # Прополка старых архивов этого же лога.
  old=()
  while IFS= read -r a; do old+=("$a"); done < <(
    find "$ARCHIVE_DIR" -maxdepth 1 -type f -name "$name.*.gz" 2>/dev/null | sort -r
  )
  if (( ${#old[@]} > KEEP_ARCHIVES )); then
    for a in "${old[@]:$KEEP_ARCHIVES}"; do
      rm -f "$a" && echo "   · удалён старый архив $(basename "$a")"
    done
  fi
done

echo ""
if (( rotated == 0 )); then
  echo "Ничего не переросло порог ${MAX_MB} МБ — ротация не нужна."
else
  if (( APPLY )); then
    echo "Ротировано файлов: $rotated · освобождено ≈ ${freed_mb} МБ"
  else
    echo "Под ротацию попадает файлов: $rotated · освободилось бы ≈ ${freed_mb} МБ"
    echo "Запусти с --apply, чтобы это произошло."
  fi
fi
