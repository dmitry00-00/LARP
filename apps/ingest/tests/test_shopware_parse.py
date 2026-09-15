"""Разбор листинга Shopware 6 (Mytholon) — срез 15.09.2026."""
from hmb.importers.shopware import category_urls, parse_listing

HTML = """<html><h1>LARP- und Mittelalter-Rüstungen</h1><p>392 Artikel</p>
<div class="card product-box box-image" data-product-information='{"id":"d3d5f001","name":"Adam Armschienen","brand":"Mytholon_metal","price":24.89}'>
 <a class="product-name" href="https://mytholon.com/Adam-Armschienen/191332M">Adam Armschienen</a>
 <img class="product-image" src="https://mytholon.com/media/x.jpg"/><div class="product-price">24,89 €</div></div>
<div class="card product-box" data-product-information='{"id":"abc","name":"Gugel","brand":"Mytholon","price":null}'><a href="https://mytholon.com/Gugel/1">Gugel</a></div>
</html>"""


def test_parse_listing():
    items, title, total = parse_listing(HTML)
    assert title.startswith("LARP-") and total == 392 and len(items) == 2
    assert items[0]["price"] == 25 and items[0]["brand"] == "Mytholon_metal" and items[0]["image_url"].endswith("x.jpg")
    assert items[1]["price"] is None and items[1]["image_url"] is None


def test_category_urls_drop_products_and_service_pages():
    base = "https://mytholon.com"
    urls = [base + "/", base + "/Ruestungen", base + "/Ruestungen/Helme", base + "/Adam-Armschienen/191332M", base + "/x/966882", base + "/account/login", base + "/Ruestungen"]
    assert category_urls(urls, base) == [base + "/Ruestungen", base + "/Ruestungen/Helme"]
