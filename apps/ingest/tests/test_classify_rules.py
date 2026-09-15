from hmb.classify import condition_of, direction_of, is_digest


def test_direction_want_markers_multilingual():
    assert direction_of("Suche LARP Schwert bis 60 €") == "want"
    assert direction_of("Ищу наручи кожаные, Москва") == "want"
    assert direction_of("Gezocht: larp zwaard") == "want"
    assert direction_of("Zwaard NIEUW. Ben jij op zoek naar een mooi zwaard? Bestel!") == "offer"   # реклама продавца, не спрос
    assert direction_of("Plakfolie kopen? Op zoek naar hip plakfolie? Bij ons 1001 soorten") == "offer"
    assert direction_of("Verkaufe LARP Schwert, neuwertig") == "offer"


def test_condition_negation_is_respected():
    assert condition_of("wenig genutzt, guter Zustand") == "used"
    assert condition_of("Neu, unbenutzt") == "new"
    assert condition_of("nicht gebraucht, neu") == "new"
    assert condition_of("Schwert 100 cm") == "unknown"


def test_digest_is_price_list_not_single_lot():
    text = "Preisliste:\n- Schwert 60 €\n- Dolch 25 €\n- Schild 80 €\n- Axt 45 €"
    assert is_digest(text) is True
    assert is_digest("Verkaufe Schwert 60 € VB") is False
