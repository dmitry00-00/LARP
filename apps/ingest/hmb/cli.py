"""`python -m hmb <команда>` — точка входа приёма. Каждая команда печатает,
что сделала, числом и знаменателем."""
from __future__ import annotations

import argparse
import json
import sys

from hmb import db as dbm


def cmd_init(_a):
    dbm.init_db()
    from hmb.slots import seed_slots
    with dbm.session() as s:
        print(json.dumps({"seed_slots": seed_slots(s)}, ensure_ascii=False))


def cmd_import(a):
    dbm.init_db()
    from hmb import importers
    mod = importers.load(a.source)
    with dbm.session() as s:
        res = mod.run(s, **({"limit_pages": a.limit_pages} if a.limit_pages else {}))
    print(json.dumps(res, ensure_ascii=False, indent=1, default=str))


def cmd_classify(a):
    dbm.init_db()
    from hmb.classify import classify_pending
    with dbm.session() as s:
        print(json.dumps(classify_pending(s, limit=a.limit), ensure_ascii=False, indent=1))


def cmd_export(_a):
    dbm.init_db()
    from hmb.export_feed import write
    with dbm.session() as s:
        print(json.dumps(write(s), ensure_ascii=False, indent=1))


def cmd_reslot(a):
    """Пересчёт слотов по сохранённым полям — «каждый посев — новый замер»."""
    dbm.init_db()
    from hmb.slots import reslot, seed_slots
    with dbm.session() as s:
        seeded = seed_slots(s); s.commit()
        res = reslot(s, a.source)
    print(json.dumps({"seed": seeded, **res}, ensure_ascii=False, indent=1))


def cmd_status(_a):
    dbm.init_db()
    from sqlalchemy import func, select
    from hmb.models import Game, InboxItem, Lot, Ruleset, Slot, SlotAlias, Source
    with dbm.session() as s:
        out = {
            "sources": s.scalar(select(func.count()).select_from(Source)),
            "slots": s.scalar(select(func.count()).select_from(Slot)),
            "slot_aliases": s.scalar(select(func.count()).select_from(SlotAlias)),
            "lots_total": s.scalar(select(func.count()).select_from(Lot)),
            "lots_by_kind_dir": [list(r) for r in s.execute(select(Lot.kind, Lot.direction, func.count()).group_by(Lot.kind, Lot.direction))],
            "lots_with_slot": s.scalar(select(func.count()).select_from(Lot).where(Lot.slot_id.is_not(None))),
            "inbox_by_status": [list(r) for r in s.execute(select(InboxItem.status, func.count()).group_by(InboxItem.status))],
            "games": s.scalar(select(func.count()).select_from(Game)),
            "rulesets": s.scalar(select(func.count()).select_from(Ruleset)),
            "sources_polled": [[r.id, str(r.last_polled_at)[:19] if r.last_polled_at else None] for r in s.scalars(select(Source))],
        }
    print(json.dumps(out, ensure_ascii=False, indent=1))


def main(argv=None):
    p = argparse.ArgumentParser(prog="hmb")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    pi = sub.add_parser("import"); pi.add_argument("source"); pi.add_argument("--limit-pages", type=int); pi.set_defaults(fn=cmd_import)
    pc = sub.add_parser("classify"); pc.add_argument("--limit", type=int, default=5000); pc.set_defaults(fn=cmd_classify)
    sub.add_parser("export").set_defaults(fn=cmd_export)
    pr = sub.add_parser("reslot"); pr.add_argument("--source"); pr.set_defaults(fn=cmd_reslot)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
