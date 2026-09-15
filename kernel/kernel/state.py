"""Local SQLite state — last-polled message ids, skill run audit, LLM cost log.

Only OpenClaw writes here. The Recruit DB is the source of truth for
business data; this file is bounded to operational state.
"""

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

_SCHEMA = """
CREATE TABLE IF NOT EXISTS telegram_processed (
    channel_handle  TEXT PRIMARY KEY,
    last_message_id INTEGER NOT NULL,
    updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skill_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name      TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    finished_at     TEXT,
    status          TEXT NOT NULL,
    items_processed INTEGER,
    error_text      TEXT
);
CREATE INDEX IF NOT EXISTS ix_skill_runs_started ON skill_runs (started_at DESC);

CREATE TABLE IF NOT EXISTS llm_calls (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name      TEXT,
    model           TEXT,
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    cached_tokens   INTEGER,
    cost_usd        REAL,
    duration_ms     INTEGER,
    success         INTEGER,
    called_at       TEXT NOT NULL
);

-- Channel discovery candidates — tracks @handles seen in posts / forward chains
-- and web-crawled from tgstat.ru / telemetr.io.
-- Prevents re-proposing the same handle on every weekly run.
CREATE TABLE IF NOT EXISTS channel_candidates (
    handle          TEXT PRIMARY KEY,
    mention_count   INTEGER NOT NULL DEFAULT 0,   -- organic @mentions in posts
    forward_count   INTEGER NOT NULL DEFAULT 0,   -- forward-chain sources
    crawl_count     INTEGER NOT NULL DEFAULT 0,   -- web-crawl hits (tgstat/telemetr)
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    evaluated_at    TEXT,       -- set after LLM quality scoring
    quality_score   REAL,       -- 0..1 from LLM; NULL = not yet scored
    proposed_at     TEXT        -- set when successfully sent to Recruit
);
CREATE INDEX IF NOT EXISTS ix_cc_last_seen ON channel_candidates (last_seen DESC);

-- Near-duplicate fingerprints (64-bit SimHash per inbox item).
-- Used by classify_post to skip re-classifying reposted content.
CREATE TABLE IF NOT EXISTS content_fingerprints (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint     INTEGER NOT NULL,      -- 64-bit SimHash (stored as Python int)
    inbox_item_id   TEXT NOT NULL,
    channel_handle  TEXT,
    created_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_fp_fingerprint ON content_fingerprints (fingerprint);
CREATE INDEX IF NOT EXISTS ix_fp_created     ON content_fingerprints (created_at DESC);

-- Репозитории GitHub, найденные скиллом discover_github: реестр «что видели,
-- что собрали». Содержимое (вопросы/задачи) в базу не пишется — оно уходит в
-- data/github/questions.csv, формат easyoffer, его читают бэкенд-инструменты.
CREATE TABLE IF NOT EXISTS github_repos (
    full            TEXT PRIMARY KEY,       -- owner/name
    seed            TEXT NOT NULL,          -- repo | topic:<t> | search:<q>
    class           TEXT NOT NULL,
    profile         TEXT NOT NULL,
    license         TEXT,
    redistributable INTEGER NOT NULL,
    stars           INTEGER NOT NULL,
    score           REAL NOT NULL,
    first_seen      TEXT NOT NULL,
    last_seen       TEXT NOT NULL,
    harvested_at    TEXT,                   -- NULL = ещё не собран
    items           INTEGER                 -- сколько элементов дал harvest
);
CREATE INDEX IF NOT EXISTS ix_gh_score ON github_repos (harvested_at, score DESC);
"""


class State:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path
        with self._conn() as c:
            c.executescript(_SCHEMA)
            # Safe migration: add crawl_count to channel_candidates if it doesn't
            # exist yet (installs created before task #24).
            try:
                c.execute(
                    "ALTER TABLE channel_candidates ADD COLUMN"
                    " crawl_count INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # column already exists — nothing to do

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        # 30 с вместо дефолтных 5: файл один на демон и на ручные прогоны
        # (`run-once discover_github` идёт десятки минут рядом с циклом
        # watch → classify, который пишет сюда каждые 5 минут). Дефолт
        # ронял ручной прогон «database is locked» на первой же записи,
        # попавшей в чужую транзакцию (11.09, вечер).
        conn = sqlite3.connect(self._path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── Telegram offsets ─────────────────────────────────────────

    def get_last_message_id(self, channel_handle: str) -> int:
        with self._conn() as c:
            row = c.execute(
                "SELECT last_message_id FROM telegram_processed WHERE channel_handle = ?",
                (channel_handle,),
            ).fetchone()
            return row["last_message_id"] if row else 0

    def set_last_message_id(self, channel_handle: str, message_id: int) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO telegram_processed (channel_handle, last_message_id, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT (channel_handle) DO UPDATE
                  SET last_message_id = excluded.last_message_id,
                      updated_at      = excluded.updated_at
                """,
                (channel_handle, message_id, datetime.now(UTC).isoformat()),
            )

    # ── Skill runs ────────────────────────────────────────────────

    def start_run(self, skill_name: str) -> int:
        with self._conn() as c:
            cur = c.execute(
                """
                INSERT INTO skill_runs (skill_name, started_at, status)
                VALUES (?, ?, 'running')
                """,
                (skill_name, datetime.now(UTC).isoformat()),
            )
            return cur.lastrowid or 0

    def finish_run(
        self,
        run_id: int,
        *,
        status: str,
        items_processed: int | None = None,
        error_text: str | None = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                UPDATE skill_runs
                SET finished_at = ?, status = ?, items_processed = ?, error_text = ?
                WHERE id = ?
                """,
                (
                    datetime.now(UTC).isoformat(),
                    status,
                    items_processed,
                    error_text,
                    run_id,
                ),
            )

    # ── GitHub repos (discover_github) ─────────────────────────────

    def upsert_github_repo(self, row: dict) -> bool:
        """True — репозиторий новый. Повторная встреча обновляет score/stars и
        last_seen, но не сбрасывает harvested_at."""
        now = datetime.now(UTC).isoformat()
        with self._conn() as c:
            known = c.execute("SELECT 1 FROM github_repos WHERE full = ?", (row["full"],)).fetchone()
            if known:
                c.execute(
                    "UPDATE github_repos SET class=?, profile=?, license=?, redistributable=?, "
                    "stars=?, score=?, last_seen=? WHERE full=?",
                    (row["class"], row["profile"], row["license"], int(row["redistributable"]),
                     row["stars"], row["score"], now, row["full"]),
                )
                return False
            c.execute(
                "INSERT INTO github_repos (full, seed, class, profile, license, redistributable, stars, score, "
                "first_seen, last_seen) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (row["full"], row["seed"], row["class"], row["profile"], row["license"],
                 int(row["redistributable"]), row["stars"], row["score"], now, now),
            )
            return True

    def github_repos_to_harvest(self, *, min_score: float, limit: int,
                                priority_profiles: tuple[str, ...] = (),
                                priority_min_score: float | None = None) -> list[str]:
        """Кого собирать: приоритетные профили первыми (и со своим порогом),
        остальные — по score. Без приоритета порядок по score отдавал
        сбор звёздным DevOps-репозиториям, а C++/embedded/python ждали."""
        pmin = min_score if priority_min_score is None else priority_min_score
        marks = ",".join("?" for _ in priority_profiles) or "''"
        with self._conn() as c:
            rows = c.execute(
                f"SELECT full FROM github_repos WHERE harvested_at IS NULL AND ("
                f"  (profile IN ({marks}) AND score >= ?) OR score >= ?) "
                f"ORDER BY (profile IN ({marks})) DESC, score DESC LIMIT ?",
                (*priority_profiles, pmin, min_score, *priority_profiles, limit),
            ).fetchall()
        return [r[0] for r in rows]

    def mark_github_harvested(self, full: str, items: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE github_repos SET harvested_at = ?, items = ? WHERE full = ?",
                      (datetime.now(UTC).isoformat(), items, full))

    def github_repo_stats(self) -> dict:
        with self._conn() as c:
            total, harvested, items = c.execute(
                "SELECT count(*), count(harvested_at), coalesce(sum(items), 0) FROM github_repos"
            ).fetchone()
        return {"total": total, "harvested": harvested, "items": items}

    # ── Deduplication fingerprints ────────────────────────────────

    def add_fingerprint(
        self,
        fingerprint: int,
        inbox_item_id: str,
        channel_handle: str | None = None,
    ) -> None:
        """Store a SimHash fingerprint for the given inbox item."""
        # SimHash is an unsigned 64-bit int, but SQLite INTEGER is signed 64-bit
        # — values ≥ 2^63 overflow on insert. Store the two's-complement signed
        # form; load_fingerprints converts it back. The bit pattern (and so the
        # Hamming distance) is preserved, and no DB migration is needed.
        signed = fingerprint - (1 << 64) if fingerprint >= (1 << 63) else fingerprint
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO content_fingerprints
                    (fingerprint, inbox_item_id, channel_handle, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (signed, inbox_item_id, channel_handle, datetime.now(UTC).isoformat()),
            )

    def load_fingerprints(self, *, retention_days: int = 30) -> list[tuple[int, str]]:
        """Return all (fingerprint, inbox_item_id) pairs from the last N days.

        Loaded into memory once per classify_post run; cheap because SQLite
        is local and the 30-day window contains at most tens of thousands of rows.
        """
        cutoff = datetime.now(UTC).isoformat()[:10]  # YYYY-MM-DD prefix
        # Subtract retention_days using string math isn't reliable — use a
        # parameterised datetime calculation available in SQLite.
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT fingerprint, inbox_item_id
                FROM content_fingerprints
                WHERE created_at >= datetime('now', ? || ' days')
                """,
                (f"-{retention_days}",),
            ).fetchall()
        # Undo the signed-storage trick from add_fingerprint → unsigned 64-bit.
        out: list[tuple[int, str]] = []
        for r in rows:
            fp = r["fingerprint"]
            if fp < 0:
                fp += 1 << 64
            out.append((fp, r["inbox_item_id"]))
        return out

    def cleanup_fingerprints(self, *, retention_days: int = 30) -> int:
        """Delete fingerprints older than retention_days. Returns row count."""
        with self._conn() as c:
            cur = c.execute(
                "DELETE FROM content_fingerprints WHERE created_at < datetime('now', ? || ' days')",
                (f"-{retention_days}",),
            )
            return cur.rowcount

    # ── Channel discovery candidates ──────────────────────────────

    def upsert_channel_candidate(
        self,
        handle: str,
        *,
        mention_count: int = 0,
        forward_count: int = 0,
        crawl_count: int = 0,
    ) -> None:
        """Record (or increment) a discovered candidate channel.

        Idempotent — safe to call every scan cycle.  All counts are *added*
        to existing totals so repeated observations accumulate over time.

        Signal weights used in ``pending_channel_candidates``:
          score = mention_count + forward_count × 2 + crawl_count
        """
        now = datetime.now(UTC).isoformat()
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO channel_candidates
                    (handle, mention_count, forward_count, crawl_count,
                     first_seen, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (handle) DO UPDATE
                  SET mention_count = mention_count + excluded.mention_count,
                      forward_count = forward_count + excluded.forward_count,
                      crawl_count   = crawl_count   + excluded.crawl_count,
                      last_seen     = excluded.last_seen
                """,
                (handle, mention_count, forward_count, crawl_count, now, now),
            )

    def is_channel_candidate_known(self, handle: str) -> bool:
        """True if we have already evaluated this handle (proposed or rejected)."""
        with self._conn() as c:
            row = c.execute(
                "SELECT evaluated_at FROM channel_candidates WHERE handle = ?",
                (handle,),
            ).fetchone()
        return row is not None and row["evaluated_at"] is not None

    def mark_channel_evaluated(
        self,
        handle: str,
        *,
        quality_score: float,
        proposed: bool,
    ) -> None:
        """Record LLM quality score and optional proposal timestamp."""
        now = datetime.now(UTC).isoformat()
        with self._conn() as c:
            c.execute(
                """
                UPDATE channel_candidates
                SET evaluated_at = ?,
                    quality_score = ?,
                    proposed_at   = CASE WHEN ? THEN ? ELSE proposed_at END
                WHERE handle = ?
                """,
                (now, quality_score, proposed, now, handle),
            )

    def pending_channel_candidates(
        self,
        *,
        limit: int = 30,
    ) -> list[dict]:
        """Return un-evaluated candidates ordered by total signal strength."""
        with self._conn() as c:
            rows = c.execute(
                """
                SELECT handle, mention_count, forward_count, crawl_count,
                       (mention_count + forward_count * 2 + crawl_count) AS score
                FROM channel_candidates
                WHERE evaluated_at IS NULL
                ORDER BY score DESC, last_seen DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── LLM cost log ──────────────────────────────────────────────

    def log_llm_call(
        self,
        *,
        skill_name: str,
        model: str,
        tokens_in: int | None,
        tokens_out: int | None,
        duration_ms: int,
        success: bool,
        cached_tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        with self._conn() as c:
            c.execute(
                """
                INSERT INTO llm_calls (
                    skill_name, model, tokens_in, tokens_out, cached_tokens,
                    cost_usd, duration_ms, success, called_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill_name,
                    model,
                    tokens_in,
                    tokens_out,
                    cached_tokens,
                    cost_usd,
                    duration_ms,
                    1 if success else 0,
                    datetime.now(UTC).isoformat(),
                ),
            )
