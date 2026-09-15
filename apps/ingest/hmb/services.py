"""Услуги — третья сторона рынка (MARKET §7): аренда, изготовление на заказ,
ремонт, подгонка, мероприятия. Витрины кладут их в обычные разделы
(«Аренда», «Услуги консультаций и проведения мероприятий»), и до 15.09 они
становились лотами без слота. Здесь — определение вида услуги по подписи
раздела и названию; направление лота — `service`, вид — в `specs.service_kind`
(ключи те же, что `SVC_RU` на странице: rent · custom · repair · refit ·
consumable · appraisal · logistics · event).
"""
from __future__ import annotations

import re

_KINDS: list[tuple[str, re.Pattern[str]]] = [
    ("rent", re.compile(r"\b(аренд\w*|прокат\w*|напрокат|rent(?:al)?|verleih|huur|te huur)\b", re.I)),
    ("repair", re.compile(r"\b(ремонт\w*|починк\w*|реставрац\w*|repair|reparatur|reparatie)\b", re.I)),
    ("refit", re.compile(r"\b(подгонк\w*|подогнать|refit|anpassung)\b", re.I)),
    ("custom", re.compile(r"\b(на заказ|под заказ|изготовлен\w* на заказ|индивидуальн\w* пошив|custom order|made to order|maßanfertigung|op maat)\b", re.I)),
    ("event", re.compile(r"\b(мастер-класс\w*|мастеркласс\w*|консультац\w*|мероприят\w*|тир|ярмарк\w*|городок|workshop|event)\b", re.I)),
    ("appraisal", re.compile(r"\b(оценк\w*|экспертиз\w*|appraisal)\b", re.I)),
]


_TITLE_RX = re.compile(r"\b(в аренду|напрокат|прокат\w*|аренда\b|услуг\w*|мастер-класс\w*|te huur|zu vermieten|for hire|for rent)\b", re.I)


def service_kind_of(*texts: str | None) -> str | None:
    """Вид услуги, если РАЗДЕЛ говорит об услуге; по названию — только явное
    («в аренду», «напрокат», «услуга», «мастер-класс»). Иначе None — это товар.

    По одному слову в названии не судим: «Repair Glue» — клей, «Event-Kit» —
    линзы, «(под заказ)» — товар со сроком (`specs.made_to_order`), не услуга
    (замер 15.09: 3 ложных «услуги» из 8 при поиске по названию).
    """
    category = texts[0] or "" if texts else ""
    title = " · ".join(t for t in texts[1:] if t)
    for kind, rx in _KINDS:
        if rx.search(category):
            return kind
    if _TITLE_RX.search(category) or (title and _TITLE_RX.search(title)):
        # раздел «Услуги» или явная услуга в названии: вид — по обоим текстам, иначе общий «на заказ»
        joined = category + " · " + title
        for kind, rx in _KINDS:
            if rx.search(joined):
                return kind
        return "custom"
    return None


def made_to_order(*texts: str | None) -> bool:
    return bool(_KINDS[3][1].search(" · ".join(t for t in texts if t)))
