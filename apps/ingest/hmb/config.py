"""Настройки приёма. Всё — из окружения, дефолты — под запуск с диска.

БД по умолчанию — SQLite в `data/hmb.sqlite` у корня проекта: бэкенда и
Postgres ещё нет (CLAUDE.md «Прод — это код на диске»), а модели написаны на
SQLAlchemy 2.0, так что переезд на Postgres — смена `HMB_DATABASE_URL`, не
переписывание. Alembic — долг: пока `create_all`.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]            # ~/LARP
DATA_DIR = Path(os.environ.get("HMB_DATA_DIR") or ROOT / "data")
DATABASE_URL = os.environ.get("HMB_DATABASE_URL") or f"sqlite:///{DATA_DIR / 'hmb.sqlite'}"
SITE_FEED = ROOT / "site" / "data" / "feed.json"

# Вежливость обхода: один клиент, пауза между запросами к одному хосту.
USER_AGENT = os.environ.get("HMB_USER_AGENT", "hmb-market-ingest/0.1 (+aggregator; contact via site)")
POLITE_DELAY_SEC = float(os.environ.get("HMB_POLITE_DELAY_SEC", "1.5"))
