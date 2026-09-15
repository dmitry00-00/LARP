"""Разбор листинга wargearshop.ru (Storeland) — срез разметки 15.09.2026."""
from hmb.importers.wargearshop import parse_listing, parse_sitemap

HTML = """<html><body><div class="page-headline"><h1>Мечи</h1></div>
<div id="site-path"><p><a href="https://wargearshop.ru/">Главная</a> » <a href="https://wargearshop.ru/catalog">Каталог товаров</a>
 » <a href="https://wargearshop.ru/catalog/LARP">Протектированное Клинковое LARP Вооружение</a> » <span class="current">Мечи</span></p></div>
<table><tr><td class="goodsListItem"><div class="goodsListItemBlock">
 <h3 class="goodsListItemName"><a href="https://wargearshop.ru/goods/Basselard-LARP" title="x">Басселард LARP Длинный. Серия Премиум</a></h3>
 <table class="goodsListItemImage"><tr><td><img class="goods-image-other" src="https://i2.storeland.net/x.jpg" alt="x"/></td></tr></table>
 <div class="oldcena"><div class="goodsListItemPriceOld">8000</div></div>
 <div class="goodsListItemPriceNew"><a href="x"><span title="7 000 российских рублей"><span class="num">7 000</span> <span>Р</span></span></a></div>
</div></td>
<td class="goodsListItem"><div class="goodsListItemBlock">
 <h3 class="goodsListItemName"><a href="/goods/Kinzhal-LARP">Кинжал LARP</a></h3>
 <div class="goodsListItemPriceNew"><span class="num">2 500</span></div>
</div></td></tr></table></body></html>"""

SITEMAP = """<urlset><url><loc>http://wargearshop.ru/</loc></url><url><loc>http://wargearshop.ru/catalog</loc></url>
<url><loc>http://wargearshop.ru/catalog/Shlemy-4</loc></url><url><loc>http://wargearshop.ru/goods/Bakler-LARP</loc></url>
<url><loc>http://wargearshop.ru/catalog/Shlemy-4</loc></url><url><loc>http://wargearshop.ru/catalog/LARP</loc></url></urlset>"""


def test_parse_listing():
    items, title, crumbs = parse_listing(HTML)
    assert title == "Мечи" and crumbs == ["Протектированное Клинковое LARP Вооружение"]
    assert [i["external_id"] for i in items] == ["Basselard-LARP", "Kinzhal-LARP"]
    assert items[0]["price"] == 7000 and items[0]["price_old"] == 8000 and items[0]["has_photo"] is True
    assert items[1]["price"] == 2500 and items[1]["price_old"] is None and items[1]["url"] == "https://wargearshop.ru/goods/Kinzhal-LARP"


def test_parse_sitemap_categories_only_unique():
    assert parse_sitemap(SITEMAP) == ["/catalog/Shlemy-4", "/catalog/LARP"]
