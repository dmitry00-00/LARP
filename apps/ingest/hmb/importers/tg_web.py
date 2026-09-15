"""Telegram-каналы игр через `t.me/s/<канал>` — вне квоты аккаунта
(`kernel/clients/tg_web.py`). Источник списка — `games.telegram_channel`
(kogda-igra API). Invite-ссылки (`+…`) — это чаты, превью у них нет: пропускаем
и считаем отдельно.

Это лента ВСЕГО (анонсы, отчёты, объявления), а не барахолка: тематический
гейт в `classify.py` ПОМЕЧАЕТ не про снаряжение как `off_topic`, не удаляет.
Курсор — `sources.meta.last_id` на канал; писатель — этот модуль.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import structlog
from sqlalchemy import select

from hmb.models import Game, InboxItem, Source
from kernel.clients.tg_web import TgWebClient

log = structlog.get_logger("hmb.import.tg_web")


def _handles(db) -> dict[str, list[Game]]:
    out: dict[str, list[Game]] = {}
    for g in db.scalars(select(Game).where(Game.telegram_channel.is_not(None), Game.deleted.is_(False))):
        h = (g.telegram_channel or "").strip().lstrip("@")
        if h:
            out.setdefault(h, []).append(g)
    return out


def ensure_source(db, handle: str, games: list[Game]) -> Source:
    sid = f"tg:{handle.lower()}"
    src = db.get(Source, sid)
    if src is None:
        src = Source(id=sid, kind="tg", title=f"@{handle} — {games[0].name[:80]}", url=f"https://t.me/s/{handle}",
                     country="RU", lang="ru", discipline="larp", access="html", robots_ok=True,
                     note="канал игры из kogda-igra; читается через t.me/s/ (вне квоты)",
                     meta={"last_id": 0, "games": [g.id for g in games]})
        db.add(src); db.flush()
    return src


async def _run(db, max_pages: int, limit_channels: int | None) -> dict:
    now = datetime.now(UTC)
    handles = _handles(db)
    public = {h: g for h, g in handles.items() if not h.startswith("+")}
    invites = len(handles) - len(public)
    stats = {"channels_total": len(handles), "invite_chats_skipped": invites, "channels_polled": 0,
             "no_preview": 0, "posts_new": 0, "per_channel": {}}
    async with TgWebClient() as tg:
        for i, (handle, games) in enumerate(sorted(public.items())):
            if limit_channels and i >= limit_channels:
                break
            src = ensure_source(db, handle, games)
            last_id = int((src.meta or {}).get("last_id") or 0)
            posts = await tg.fetch_since(handle, min_id=last_id, max_pages=max_pages)
            stats["channels_polled"] += 1
            if not posts and last_id == 0:
                stats["no_preview"] += 1
                src.meta = {**(src.meta or {}), "no_preview_at": now.isoformat()}
            n = 0
            for p in posts:
                if not p.text or len(p.text.strip()) < 8:
                    continue
                ext = str(p.id)
                item = db.scalar(select(InboxItem).where(InboxItem.source_id == src.id, InboxItem.external_id == ext))
                if item is None:
                    item = InboxItem(source_id=src.id, external_id=ext, raw_text=p.text, provenance="import:tg_web",
                                     url=f"https://t.me/{handle}/{p.id}", title=p.text.split("\n", 1)[0][:200],
                                     posted_at=p.date, country="RU", lang="ru", fetched_at=now)
                    db.add(item); n += 1
            if posts:
                src.meta = {**(src.meta or {}), "last_id": max(int((src.meta or {}).get("last_id") or 0), max(p.id for p in posts))}
            src.last_polled_at = now
            stats["posts_new"] += n; stats["per_channel"][handle] = n
            db.commit()
            await asyncio.sleep(1.0)
    return stats


def run(db, max_pages: int = 3, limit_channels: int | None = None, **_kw) -> dict:
    return asyncio.run(_run(db, max_pages, limit_channels))
