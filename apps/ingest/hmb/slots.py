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
    added_slots = added_aliases = removed_aliases = 0
    for s in data["slots"]:
        slot = db.get(Slot, s["id"])
        if slot is None:
            slot = Slot(id=s["id"]); db.add(slot); added_slots += 1
        slot.group = s["group"]; slot.label_ru = s["ru"]; slot.label_en = s["en"]
        slot.parent_id = s.get("parent_id"); slot.zones = s.get("zones") or []
        slot.layer = s.get("layer"); slot.measures = s.get("measures") or []
        db.flush()
        wanted = {name.lower() for names in s["aliases"].values() for name in names}
        have: set[str] = set()
        for a in db.scalars(select(SlotAlias).where(SlotAlias.slot_id == slot.id)):
            # Посев — источник истины для origin='seed': алиас, снятый из файла
            # (ловушка «standard», «набор»), снимается и из базы. Чужие origin не трогаем.
            if a.origin == "seed" and a.alias.lower() not in wanted:
                db.delete(a); removed_aliases += 1
            else:
                have.add(a.alias.lower())
        for lang, names in s["aliases"].items():
            for name in names:
                if name.lower() not in have:
                    db.add(SlotAlias(slot_id=slot.id, alias=name, lang=lang, origin="seed"))
                    have.add(name.lower()); added_aliases += 1
    db.flush()
    return {"slots": added_slots, "aliases": added_aliases, "removed": removed_aliases}


# Хвост кириллического ключа у SkillExtractor открыт (kernel/ner_extractor:
# «медицин» ловит склонения), голова — закрыта. Значит, русский алиас должен
# быть ОСНОВОЙ: «фибула» не найдёт «фибулы», «корона» — «короны» (замер на
# donjon.ru 15.09: 12 «фибул парных» без слота при живом алиасе «фибула»).
# Основа = слово без последней гласной/мягкого знака, не короче 4 букв, только
# для однословных алиасов от 5 букв. Ловушки префикса («венец» → «Венецианский»)
# лечатся списком отказов в посеве, не границей — как в recruit.
_RU_STEM_RX = re.compile(r"^[а-яё]{4,}[аяыиоеьй]$")


def ru_stems(aliases: list[str]) -> list[str]:
    out: list[str] = []
    for a in aliases:
        low = a.lower()
        if _RU_STEM_RX.fullmatch(low):
            stem = low[:-1]
            if stem not in out and stem not in aliases:
                out.append(stem)
    return out


def canonical_dict(db: Session) -> dict[str, dict]:
    """Форма, которую ждёт SkillExtractor: {id: {name, aliases}}. Имя — тоже ключ."""
    out: dict[str, dict] = {}
    for slot in db.scalars(select(Slot)):
        aliases = [slot.label_ru] + [a.alias for a in slot.aliases]
        ru = [a.alias for a in slot.aliases if a.lang == "ru"]
        out[slot.id] = {"name": slot.label_en, "aliases": aliases + ru_stems(ru)}
    return out


# Немецкие и нидерландские композиты: «Elfenschwert», «Ridderkostuum» — граница
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
    # NL (marktplaats 15.09: «RVS zwaarden», «Ridderkostuum», «larpwapens», «Cosplay schilden»)
    ("zwaard", "sword_1h"), ("schild", "shield"), ("harnas", "cuirass"), ("kostuum", "costume"), ("wapen", "weapon_other"),
    ("bijl", "axe"), ("dolk", "dagger"), ("boog", "bow"), ("speer", "spear"), ("staf", "staff"), ("kolder", "chainmail"),
    ("kraag", "gorget"), ("gordel", "belt"), ("tasje", "pouch"), ("laars", "boots"), ("hoed", "headwear"),
    ("masker", "mask"), ("handschoen", "gloves"), ("jurk", "dress"), ("pak", "costume"), ("pruik", "costume"),
]
_DE_HEAD_RX = re.compile(r"\b[a-zäöüß]{3,}?(" + "|".join(h for h, _ in _DE_HEADS) + r")(?:e|en|er|es|s)?\b", re.I)
_DE_HEAD_SLOT = dict(_DE_HEADS)


# «Меч с ножнами», «Sword with scabbard», «Schwert mit Scheide» — предмет
# один, аксессуар в комплекте. Иначе слот-контейнер (ножны) побеждает меч:
# на donjon.ru 15.09 так уехали бы 40 мечей и кинжалов. Фразу вырезаем до
# поиска; «Ножны для меча» без предлога остаются ножнами.
_INCLUDED_RX = re.compile(
    r"\b(?:с|со|в)\s+(?:[а-яё]+ыми\s+|[а-яё]+ых\s+)?(?:ножн\w*|чехл\w*|подвес\w*|поясом|ремн\w*)\b"
    r"|\bwith\s+(?:scabbard|sheath|holder|belt|frog)\b"
    r"|\bmit\s+(?:scheide|halter|gürtel|halterung)\b"
    r"|\bmet\s+(?:schede|houder|riem)\b", re.I)


class SlotMatcher:
    def __init__(self, db: Session) -> None:
        self._ex = SkillExtractor(canonical_dict(db))

    def match(self, text: str) -> list[str]:
        """Все слоты, упомянутые в тексте, в порядке появления; композиты — запасным проходом."""
        ids = self._ex.extract_ids(_INCLUDED_RX.sub(" ", text or ""))
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


def reslot(db: Session, source_id: str | None = None) -> dict:
    """Пересчитать слот у лотов по сохранённым полям — после каждого посева словаря.

    Витрины Shopify матчились по title + product_type + tags; tags в `specs` не
    хранятся, поэтому для них пересчёт беднее импорта на одно поле — честнее
    перезапустить `hmb import <site>` (минута). Для donjon и объявлений поля те же.
    """
    from hmb.models import InboxItem, Lot
    matcher = SlotMatcher(db)
    q = select(Lot)
    if source_id:
        q = q.where(Lot.source_id == source_id)
    seen = changed = matched = 0
    for lot in db.scalars(q):
        sp = lot.specs or {}
        path = sp.get("path") or []
        hint = " · ".join([*path[-2:], sp.get("category") or sp.get("product_type") or ""]).strip(" ·")
        text = " · ".join(t for t in (sp.get("vk_category"), sp.get("description") or sp.get("tags")) if t)
        if not text and lot.inbox_item_id:
            # объявления: описание живёт в raw_text сырья, как и при classify
            item = db.get(InboxItem, lot.inbox_item_id)
            text = item.raw_text if item else ""
        new, conf = matcher.best(lot.title, hint, text)
        seen += 1
        if new:
            matched += 1
        if new != lot.slot_id:
            lot.slot_id = new; lot.slot_confidence = conf; changed += 1
    db.commit()
    return {"seen": seen, "changed": changed, "matched": matched, "coverage": round(matched / seen, 3) if seen else None}
