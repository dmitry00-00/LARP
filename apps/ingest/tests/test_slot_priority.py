"""Правило выбора слота на случаях, стоивших прогона 15.09 (замеры на Epic
Armoury и свежей партии kleinanzeigen). Словарь — посев в память."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from hmb.models import Base
from hmb.slots import SlotMatcher, seed_slots


@pytest.fixture(scope="module")
def matcher():
    eng = create_engine("sqlite://")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        seed_slots(s); s.commit()
        yield SlotMatcher(s)


@pytest.mark.parametrize("title,expected", [
    ("Breda Rapier Holder Small", "scabbard"),          # держатель важнее оружия в названии
    ("Schwert-Halter Leder Schwarz Kreuzritter", "scabbard"),
    ("Samt Choker Schwert Ketten Gothic Larp", "jewelry"),  # украшение с мотивом меча
    ("Larp Mittelalter- Elfenschwert, Schaumstoff", "sword_1h"),  # материал — не слот
    ("LARP Waffe Schwert 100 cm", "sword_1h"),           # родовое уступает конкретному
    ("Продам поддоспешник стёганый, размер L", "gambeson"),
    ("Ищу наручи кожаные", "bracers"),
    ("Wappenröcke gebraucht", "tunic"),                  # немецкое множественное
    ("Complete Battle Standard Set - T-Top", "kit"),     # набор
    ("shipping-standard", None),                         # ловушка: тег доставки — не знамя
])
def test_best_slot(matcher, title, expected):
    slot, _conf = matcher.best(title, None)
    assert slot == expected
