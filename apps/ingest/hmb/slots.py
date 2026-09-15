"""Словарь слотов: посев из seeds/slots.json и сопоставление текста слоту.

Сопоставление — `kernel.ner_extractor.SkillExtractor` (кириллические границы,
длинный алиас побеждает короткий, guard'ы контекста). Один экстрактор на все
языки: в объявлении язык заранее неизвестен.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from hmb.models import Slot, SlotAlias
from kernel.ner_extractor import SkillExtractor

SEED = Path(__file__).parent / "seeds" / "slots.json"


def seed_slots(db: Session) -> dict[str, int]:
    """Идемпотентно: слоты обновляются, алиасы добавляются (origin='seed')."""
    data = json.loads(SEED.read_text())
    added_slots = added_aliases = 0
    for s in data["slots"]:
        slot = db.get(Slot, s["id"])
        if slot is None:
            slot = Slot(id=s["id"]); db.add(slot); added_slots += 1
        slot.group = s["group"]; slot.label_ru = s["ru"]; slot.label_en = s["en"]
        slot.parent_id = s.get("parent_id"); slot.zones = s.get("zones") or []
        slot.layer = s.get("layer"); slot.measures = s.get("measures") or []
        db.flush()
        have = {a.alias.lower() for a in db.scalars(select(SlotAlias).where(SlotAlias.slot_id == slot.id))}
        for lang, names in s["aliases"].items():
            for name in names:
                if name.lower() not in have:
                    db.add(SlotAlias(slot_id=slot.id, alias=name, lang=lang, origin="seed"))
                    have.add(name.lower()); added_aliases += 1
    db.flush()
    return {"slots": added_slots, "aliases": added_aliases}


def canonical_dict(db: Session) -> dict[str, dict]:
    """Форма, которую ждёт SkillExtractor: {id: {name, aliases}}. Имя — тоже ключ."""
    out: dict[str, dict] = {}
    for slot in db.scalars(select(Slot)):
        out[slot.id] = {"name": slot.label_en, "aliases": [slot.label_ru] + [a.alias for a in slot.aliases]}
    return out


# Немецкие композиты: «Elfenschwert», «Kettenschwert», «Wikingerhelm» — граница
# слова не даёт алиасу «schwert» сработать внутри. Запасной проход по «голове»
# составного слова (последний корень); только когда обычный словарь молчит.
_DE_HEADS: list[tuple[str, str]] = [
    ("schwert", "sword_1h"), ("säbel", "sword_1h"), ("katana", "sword_1h"),
    ("axt", "axe"), ("beil", "axe"), ("dolch", "dagger"), ("messer", "dagger"),
    ("hammer", "mace_hammer"), ("kolben", "mace_hammer"), ("keule", "mace_hammer"),
    ("speer", "spear"), ("lanze", "spear"), ("hellebarde", "polearm"), ("stab", "staff"),
    ("schild", "shield"), ("bogen", "bow"), ("armbrust", "crossbow"), ("pfeil", "arrows"),
    ("helm", "helmet"), ("haube", "helmet"), ("hemd", "tunic"), ("wams", "gambeson"),
    ("rüstung", "cuirass"), ("panzer", "cuirass"), ("platte", "cuirass"),
    ("handschuh", "gloves"), ("stiefel", "boots"), ("schuh", "boots"),
    ("umhang", "cloak"), ("mantel", "cloak"), ("kleid", "dress"), ("rock", "dress"), ("hose", "trousers"),
    ("mütze", "headwear"), ("hut", "headwear"), ("gürtel", "belt"), ("beutel", "pouch"), ("tasche", "pouch"),
    ("halter", "scabbard"), ("scheide", "scabbard"), ("kette", "jewelry"), ("ring", "jewelry"),
    ("zelt", "tent"), ("maske", "mask"), ("laterne", "camp_gear"), ("becher", "camp_gear"), ("krug", "camp_gear"),
]
_DE_HEAD_RX = re.compile(r"\b[a-zäöüß]{3,}?(" + "|".join(h for h, _ in _DE_HEADS) + r")(?:e|en|er|es|s)?\b", re.I)
_DE_HEAD_SLOT = dict(_DE_HEADS)


class SlotMatcher:
    def __init__(self, db: Session) -> None:
        self._ex = SkillExtractor(canonical_dict(db))

    def match(self, text: str) -> list[str]:
        """Все слоты, упомянутые в тексте, в порядке появления; композиты — запасным проходом."""
        ids = self._ex.extract_ids(text or "")
        if ids:
            return ids
        seen: list[str] = []
        for m in _DE_HEAD_RX.finditer(text or ""):
            sid = _DE_HEAD_SLOT[m.group(1).lower()]
            if sid not in seen:
                seen.append(sid)
        return seen

    def best(self, *parts: str | None) -> tuple[str | None, float]:
        """Один слот для предмета: сначала по заголовку/категории, потом по остальному.

        Уверенность — грубая: 1.0 если в приоритетных полях ровно один слот,
        0.6 если несколько (берём первый), 0.3 если нашёлся только в описании.
        Не «оценка качества», а метка того, где именно сработало.
        """
        prio = [p for p in parts[:2] if p]
        rest = [p for p in parts[2:] if p]
        ids = self.match(" · ".join(prio))
        if ids:
            return _pick(ids), (1.0 if len(ids) == 1 else 0.6)
        ids = self.match(" · ".join(rest))
        if ids:
            return _pick(ids), 0.3
        return None, 0.0


# Слоты, которые в названии «побеждают» упомянутое рядом оружие: «Rapier
# Holder» — держатель, а не рапира; «Sword Belt» — пояс; «Complete Set» —
# комплект. Замер 15.09 на Epic Armoury: без этого правила держатели уходили
# в мечи по порядку появления слов.
# `weapon_parts` здесь НЕ место: «Elfenschwert, Schaumstoff» — меч, материал —
# описание (15.09, свежая партия). `jewelry` — да: «Choker Schwert Ketten» — украшение.
_CONTAINER_SLOTS = ("scabbard", "quiver", "jewelry", "belt", "kit", "banner")
# Родовые слоты уступают любому конкретному: «LARP Waffe Schwert» — меч, не «оружие».
_GENERIC_SLOTS = ("weapon_other", "costume", "other_misc")


def _pick(ids: list[str]) -> str:
    for cid in _CONTAINER_SLOTS:
        if cid in ids:
            return cid
    specific = [i for i in ids if i not in _GENERIC_SLOTS]
    return specific[0] if specific else ids[0]
