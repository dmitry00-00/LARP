"""Разбор витрины orgs.biz («Мечи из Печи») — срез разметки 15.09.2026."""
from hmb.importers.orgsbiz import _specs, parse_home

HTML = """<html><body><div class="product"><div itemscope itemtype="http://schema.org/Product">
<link itemprop="url" href="/product/9030258"><div class="product-name"><a href="/product/9030258"><span itemprop="name">
  Меч Питера Певенси &quot;Риндон&quot;, Larp (Ларп)
</span></a></div><div class="product-image"><img src="x.jpg" itemprop="image"/></div>
<div class="product-price">2 800&nbsp;₽</div>
<div class="product-description" itemprop="description">Общая длина: 109 см
Клинок 78 см
Вес 0.4 кг
Плотность: 30 шор</div></div></div></body></html>"""


def test_parse_home_and_specs():
    items = parse_home(HTML, "https://mechiizpechi.orgs.biz")
    assert len(items) == 1
    it = items[0]
    assert it["external_id"] == "9030258" and it["price"] == 2800 and it["has_photo"] is True
    assert it["title"] == 'Меч Питера Певенси "Риндон", Larp (Ларп)'
    sp = _specs(it["description"])
    assert sp["length_cm"] == 109 and sp["blade_cm"] == 78 and sp["weight_g"] == 400 and sp["hardness_shore_a"] == 30
