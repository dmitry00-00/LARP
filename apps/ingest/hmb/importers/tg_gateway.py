"""Telegram через общий шлюз основы (`~/core/services/tg-gateway`, :8710) — 28.09.2026.

Решение владельца: Telegram читает один парсер одним аккаунтом, проекты берут накопленное.
Шлюз уже держит подписку `larp` (источники с разметкой по тематике: ларп, мечевой бой,
снаряжение, НРИ…); этот модуль:

* **sync** — каналы игр из kogda-igra (`games.telegram_channel`, их же читает `tg_web`)
  добавляет в подписку `larp` (POST — добавить, а не заменить: ручные источники остаются),
  раз в сутки и реже — интервал 720 мин, приоритет ниже ручных;
* **pull** — новые посты подписки по курсору шлюза → `inbox_items`. Источник — тот же
  `tg:<канал>`, что у `tg_web`, `external_id` — id поста: пост, уже взятый через `t.me/s/`,
  второй раз не ляжет. Метка происхождения — `import:tg_gateway`. Каналы НРИ и ролевых
  (теги `нри`, `ролевые`) пропускаются — решение владельца 28.09.2026.

Своего клиента Telegram у LARP больше нет: MTProto, лимиты и замок сессии — забота шлюза.
Курсор — `data/tg_gateway.json`. Шлюз лежит — модуль выходит с `gateway_down`, ничего не
меняя: следующий запуск доберёт всё по курсору.

Запуск: `python -m hmb import tg_gateway`.
"""
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import httpx
import structlog
from sqlalchemy import select

from hmb import config
from hmb.models import Game, InboxItem, Source

log = structlog.get_logger("hmb.import.tg_gateway")

GATEWAY_URL = os.environ.get("TG_GATEWAY_URL", "http://127.0.0.1:8710")
CONSUMER = "larp"
SYNC_EVERY_SEC = 24 * 3600

# разметка шлюза → поля источника: дисциплина и страна (тег — свойство подписки)
DISCIPLINE = [("мечевой бой", "hmb"), ("реконструкция", "reenact"), ("фехтование", "hema"),
              ("ларп", "larp"), ("игры", "larp")]
# НРИ и ролевые (не живого действия) — в подписке larp шлюза есть, но в приём не идут:
# решение владельца 28.09.2026 «игнорируй ролевые каналы». Канал с тегом из DISCIPLINE берётся.
IGNORE = ("нри", "ролевые")
COUNTRY = {"сербия": "RS", "москва": "RU", "липецкая обл.": "RU", "россия": "RU"}


def state_path() -> Path:
    return config.DATA_DIR / "tg_gateway.json"


def _load_state(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {"cursor": 0, "synced_at": 0}


def _save_state(path: Path, st: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, ensure_ascii=False, indent=1))


def game_channels(db) -> list[str]:
    """Открытые каналы игр — как у `tg_web`: приглашения (`+…`) — чаты без превью, их нет."""
    out = set()
    for g in db.scalars(select(Game).where(Game.telegram_channel.is_not(None), Game.deleted.is_(False))):
        h = (g.telegram_channel or "").strip().lstrip("@")
        if h and not h.startswith("+"):
            out.add(h.lower())
    return sorted(out)


def _discipline(tags: list[str]) -> str | None:
    for tag, d in DISCIPLINE:
        if any(t == tag or t.startswith(tag + "/") for t in tags):
            return d
    return None


def _ignored(tags: list[str]) -> bool:
    return _discipline(tags) is None and any(t == g or t.startswith(g + "/") for t in tags for g in IGNORE)


def _country(tags: list[str]) -> str | None:
    return next((COUNTRY[t] for t in tags if t in COUNTRY), None)


def ensure_source(db, channel: str, tags: list[str], title: str | None = None) -> Source:
    sid = f"tg:{channel.lower()}"
    src = db.get(Source, sid)
    if src is None:
        src = Source(id=sid, kind="tg", title=(title or f"@{channel}")[:200], url=f"https://t.me/{channel}",
                     country=_country(tags), lang="ru", discipline=_discipline(tags), access="json",
                     robots_ok=True, note="канал Telegram из шлюза основы (tg-gateway, подписка larp)",
                     meta={"tags": tags})
        db.add(src)
        db.flush()
    elif tags and (src.meta or {}).get("tags") != tags:
        src.meta = {**(src.meta or {}), "tags": tags}
    return src


def sync(db, http: httpx.Client) -> dict:
    chans = game_channels(db)
    items = [{"handle": h, "tags": ["игры", "игры/канал игры"], "interval_min": 720, "priority": -1} for h in chans]
    r = http.post(f"{GATEWAY_URL}/subscriptions/{CONSUMER}", json={"channels": items})
    r.raise_for_status()
    return {"game_channels": len(chans), "gateway": r.json().get("added", [])}


def pull(db, http: httpx.Client, cursor: int, now: datetime) -> tuple[int, dict]:
    stats = {"posts_seen": 0, "posts_new": 0, "too_short": 0, "ignored_rpg": 0, "per_channel": {}}
    while True:
        r = http.get(f"{GATEWAY_URL}/posts", params={"consumer": CONSUMER, "after": cursor, "limit": 500})
        r.raise_for_status()
        body = r.json()
        for p in body["posts"]:
            stats["posts_seen"] += 1
            text = (p.get("text") or "").strip()
            if len(text) < 8:                              # как у tg_web: пустое и «+» не нужны
                stats["too_short"] += 1
                continue
            ch = p["channel"]
            if ch.startswith(("youtube:", "web:")):        # у larp пока только Telegram; остальное ждёт своего вида
                continue
            if _ignored(p.get("tags") or []):                  # НРИ и ролевые — не наш приём
                stats["ignored_rpg"] += 1
                continue
            src = ensure_source(db, ch, p.get("tags") or [])
            ext = str(p["msg_id"])
            if db.scalar(select(InboxItem.id).where(InboxItem.source_id == src.id, InboxItem.external_id == ext)):
                continue
            images = sum(1 for a in p.get("attachments") or [] if str(a.get("mime", "")).startswith("image/"))
            db.add(InboxItem(source_id=src.id, external_id=ext, raw_text=text, provenance="import:tg_gateway",
                             url=f"https://t.me/{ch}/{p['msg_id']}", title=text.split("\n", 1)[0][:200],
                             posted_at=datetime.fromisoformat(p["date"].replace("Z", "+00:00")) if p.get("date") else None,
                             country=src.country, lang="ru", fetched_at=now, photos_count=images))
            stats["posts_new"] += 1
            stats["per_channel"][ch] = stats["per_channel"].get(ch, 0) + 1
        db.commit()
        cursor = int(body["cursor"])
        if not body.get("more"):
            return cursor, stats


def run(db, *, state_file: Path | None = None, client: httpx.Client | None = None, **_kw) -> dict:
    path = state_file or state_path()
    st = _load_state(path)
    now = datetime.now(UTC)
    http = client or httpx.Client(timeout=30.0)
    try:
        try:
            http.get(f"{GATEWAY_URL}/health").raise_for_status()
        except httpx.HTTPError as exc:
            return {"status": "gateway_down", "error": str(exc)[:200], "cursor": st["cursor"]}
        out: dict = {"status": "ok"}
        if now.timestamp() - float(st.get("synced_at") or 0) > SYNC_EVERY_SEC:
            out["sync"] = sync(db, http)
            st["synced_at"] = now.timestamp()
        st["cursor"], out["pull"] = pull(db, http, int(st.get("cursor") or 0), now)
        out["cursor"] = st["cursor"]
        _save_state(path, st)
        return out
    finally:
        if client is None:
            http.close()
