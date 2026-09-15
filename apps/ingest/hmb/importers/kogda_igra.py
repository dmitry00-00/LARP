"""kogda-igra.ru — документированный JSON-API календаря игр.

`/api/changed/<unix_ts>` → [{id, deleted_flag, update_date}], `/api/game/<id>` →
25 полей, среди них `vk_club` и `telegram_channel` — то есть календарь даёт
**реестр сообществ игр** (где продают после игры) и **всплески спроса**
(`players_count`, `begin`). robots.txt 15.09.2026: `/api/` не запрещён.

Курсор — `sources.meta.cursor_ts`; писатель — этот модуль (recruit: у
`last_polled_at` 17 дней не было писателя). Проверяем, что он двигается:
`hmb status` печатает `sources_polled`.
"""
from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from hmb.http import Http
from hmb.models import Game, Source

log = structlog.get_logger("hmb.import.kogda_igra")

SOURCE_ID = "kogda_igra"
BASE = "https://kogda-igra.ru"
DEFAULT_SINCE = 1735689600  # 2025-01-01 UTC — игры, менявшиеся с начала 2025


def ensure_source(db) -> Source:
    src = db.get(Source, SOURCE_ID)
    if src is None:
        src = Source(id=SOURCE_ID, kind="calendar", title="КогдаИгра — календарь РИ", url=BASE,
                     country="RU", lang="ru", discipline="larp", access="json", robots_ok=True,
                     note="JSON-API: /api/changed/<ts>, /api/game/<id>; vk_club и telegram_channel у каждой игры",
                     meta={"cursor_ts": DEFAULT_SINCE})
        db.add(src); db.flush()
    return src


def _ts(s: str | None) -> int | None:
    if not s:
        return None
    try:
        return int(datetime.fromisoformat(s).timestamp())
    except ValueError:
        return None


def run(db, http: Http | None = None, max_games: int | None = None, since: int | None = None) -> dict:
    http = http or Http(delay=0.8)
    src = ensure_source(db)
    cursor = since or int((src.meta or {}).get("cursor_ts") or DEFAULT_SINCE)
    changed = http.json(f"{BASE}/api/changed/{cursor}")
    if isinstance(changed, dict):          # «пустой объект», если ничего нет
        changed = []
    changed.sort(key=lambda r: r.get("update_date") or "")
    if max_games:
        changed = changed[:max_games]
    fetched = created = updated = deleted = errors = 0
    with_vk = with_tg = 0
    last_update = None
    for row in changed:
        gid = int(row["id"])
        if str(row.get("deleted_flag")) == "1":
            g = db.get(Game, gid)
            if g is not None:
                g.deleted = True; deleted += 1
            last_update = row.get("update_date") or last_update
            continue
        try:
            data = http.json(f"{BASE}/api/game/{gid}")
        except Exception as exc:  # noqa: BLE001
            errors += 1; log.warning("kogda_igra.game_failed", id=gid, err=str(exc)); continue
        fetched += 1
        if not isinstance(data, dict) or "name" not in data:
            # закрытая ({"access-denied":"1"}) или слитая ({"redirect_id":…}) — запоминаем факт
            g = db.get(Game, gid) or Game(id=gid, name=f"(закрыта или слита: {data})"[:300])
            db.merge(g); last_update = row.get("update_date") or last_update
            continue
        g = db.get(Game, gid)
        if g is None:
            g = Game(id=gid, name=data["name"][:300]); db.add(g); created += 1
        else:
            updated += 1
        g.name = data["name"][:300]
        g.begin = (data.get("begin") or None)
        g.region = data.get("sub_region_disp_name") or data.get("sub_region_name")
        try:
            g.players_count = int(data.get("players_count")) if data.get("players_count") not in (None, "") else None
        except (TypeError, ValueError):
            g.players_count = None
        g.game_type = data.get("game_type_name"); g.status = data.get("status_name")
        g.vk_club = (data.get("vk_club") or None); g.telegram_channel = (data.get("telegram_channel") or None)
        g.polygon_name = data.get("polygon_name"); g.deleted = str(data.get("deleted_flag")) == "1"
        g.source_update_date = data.get("update_date"); g.raw = data
        with_vk += bool(g.vk_club); with_tg += bool(g.telegram_channel)
        last_update = data.get("update_date") or row.get("update_date") or last_update
        if fetched % 50 == 0:
            # коммит батчами: SQLite — один писатель, длинная транзакция запирает базу
            db.commit(); log.info("kogda_igra.progress", fetched=fetched)
    db.flush()
    src.last_polled_at = datetime.now(UTC)
    new_cursor = _ts(last_update) or cursor
    src.meta = {**(src.meta or {}), "cursor_ts": new_cursor, "last_changed": len(changed)}
    db.flush()
    return {"changed_rows": len(changed), "fetched": fetched, "created": created, "updated": updated,
            "deleted": deleted, "errors": errors, "with_vk_club": with_vk, "with_telegram_channel": with_tg,
            "cursor_ts": new_cursor}
