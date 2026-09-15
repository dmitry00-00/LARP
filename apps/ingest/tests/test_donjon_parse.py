"""Разбор листинга donjon.ru — на срезе разметки 15.09.2026. Ломается
разметка — ломается тест, а не молча пустая выдача (AGENT_RULES §14)."""
from hmb.importers.donjon import parse_listing, parse_menu

HTML = """<html><body>
<ul><li><a href="/category/oruzhie/">Оружие</a><ul>
 <li><a href="/category/klinkovoe-oruzhie/">Клинковое оружие</a></li>
 <li><a href="/category/larp-oruzhie/">Протектированное оружие для LARP</a></li></ul></li>
 <li><a href="/category/bu/">Барахолка</a></li>
 <li><a href="/category/?action=archive">Архив</a></li></ul>
<div class="item good__item">
  <input name="productID" value="4925" type="hidden"><input class="product_price" value="599000" type="hidden">
  <div class="product"><div class="product-picture"><a href="/product/kotta-srednevekovaya-bu-chp-iv/">
   <div class="img"><img src="/images/resized/169x169/i/default.jpg" alt="x"></div></a>
   <div class="desc"><div class="desc-popup"><div class="frame"><div class="cap">Котта</div>
   <p class="text">Мужская котта. Размер очень маленький, узкая. Состояние хорошее.</p></div></div></div></div>
  <a href="/product/kotta-srednevekovaya-bu-chp-iv/"><div class="name">Котта средневековая БУ (ЧП ИВ)</div></a>
  <div class="price"><span>5 990 руб.</span></div>
  <div class="avail">В наличии: <b>1</b></div></div>
</div>
<div class="item good__item">
  <input name="productID" value="4762" type="hidden"><input class="product_price" value="2880000" type="hidden">
  <div class="product"><div class="img"><img src="/images/resized/169x169/i/4762.jpg" alt="x"></div>
  <a href="/product/mech-flamberg/"><div class="name">Меч "фламберг" в ножнах (АА)</div></a>
  <div class="avail">В наличии: <b>0</b></div></div>
</div>
<p class="pagination"><span class="current">1</span><a href="/category/bu/?page=2">2</a><a href="/category/bu/?page=3">3</a></p>
</body></html>"""


def test_parse_listing_cards_and_pages():
    items, last = parse_listing(HTML)
    assert last == 3
    assert len(items) == 2
    a, b = items
    assert a["external_id"] == "4925" and a["price"] == 5990 and a["available"] == 1
    assert a["url"] == "https://donjon.ru/product/kotta-srednevekovaya-bu-chp-iv/"
    assert a["has_photo"] is False and "Размер очень маленький" in a["description"]
    assert b["price"] == 28800 and b["available"] == 0 and b["has_photo"] is True and b["description"] == ""


def test_parse_menu_skips_parents_and_service_links():
    menu = parse_menu(HTML)
    assert menu == [("klinkovoe-oruzhie", "Клинковое оружие"), ("larp-oruzhie", "Протектированное оружие для LARP"), ("bu", "Барахолка")]
