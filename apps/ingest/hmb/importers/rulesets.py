"""Регламенты систем игр — из seeds/rulesets.json. Идемпотентно: правила
пересоздаются целиком (это справочник, а не поток)."""
from __future__ import annotations

import json
from pathlib import Path

from hmb.models import Ruleset, RulesetLimit

SEED = Path(__file__).parent.parent / "seeds" / "rulesets.json"


def run(db, **_kw) -> dict:
    data = json.loads(SEED.read_text())
    n_rs = n_lim = 0
    for r in data["rulesets"]:
        rs = db.get(Ruleset, r["id"])
        if rs is None:
            rs = Ruleset(id=r["id"], title=r["title"], url=r["url"], lang=r["lang"], accessed_at=r["accessed_at"])
            db.add(rs)
        rs.title = r["title"]; rs.version = r.get("version"); rs.url = r["url"]; rs.lang = r["lang"]
        rs.country = r.get("country"); rs.accessed_at = r["accessed_at"]; rs.note = r.get("note")
        rs.limits.clear(); db.flush()
        for lim in r["limits"]:
            rs.limits.append(RulesetLimit(**lim)); n_lim += 1
        n_rs += 1
    db.flush()
    return {"rulesets": n_rs, "limits": n_lim}
