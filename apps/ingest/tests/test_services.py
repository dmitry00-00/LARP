from hmb.services import service_kind_of


def test_service_kind_by_category_and_title():
    assert service_kind_of("Услуги Консультаций и Проведения Мероприятий и Мастер-классов", "Лучный Тир") == "event"
    assert service_kind_of("Аренда", "Кольчуга в аренду") == "rent"
    assert service_kind_of("Мечи", "Меч на заказ по эскизу") is None          # товар под заказ — не услуга
    assert service_kind_of("Изготовление на заказ", "Меч по эскизу") == "custom"
    assert service_kind_of("Мечи", "Каролинг тип X") is None
    assert service_kind_of("Доспехи", "Ремонт кольчуги") is None                 # одно слово в названии — не улика
    assert service_kind_of("Услуги", "Ремонт кольчуги") == "repair"
    assert service_kind_of("Клей и расходники", "Repair Glue - Sword & Shield 10 g") is None
    assert service_kind_of("Аксессуары", "Kontaktlinsen-Event-Kit") is None
    assert service_kind_of("Доспехи", "Кольчуга в аренду на игру") == "rent"
