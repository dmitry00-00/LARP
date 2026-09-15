"""Разбор __NEXT_DATA__ marktplaats.nl — срез 15.09.2026."""
import json
from datetime import UTC, datetime

from hmb.importers.marktplaats import parse_date, parse_page

NOW = datetime(2026, 9, 15, 18, 0, tzinfo=UTC)
DATA = {"props": {"pageProps": {"searchRequestAndResponse": {"totalResultCount": 60, "listings": [
    {"itemId": "m2438300789", "title": "LARP zwaard 100 cm", "description": "Weinig gebruikt latex zwaard.",
     "priceInfo": {"priceCents": 4500, "priceType": "FIXED"}, "location": {"cityName": "Woudenberg"}, "date": "2 sep 26",
     "imageUrls": ["//images.marktplaats.com/a.jpg", "//images.marktplaats.com/b.jpg"],
     "attributes": [{"key": "condition", "value": "Zo goed als nieuw"}, {"key": "delivery", "value": "Ophalen"}],
     "vipUrl": "/v/hobby-en-vrije-tijd/kostuums-theaterbenodigdheden-en-larp/m2438300789-larp-zwaard"},
    {"itemId": "m1", "title": "Schild", "priceInfo": {"priceCents": 0, "priceType": "FAST_BID"}, "date": "Gisteren", "attributes": []},
]}}}}
HTML = '<html><script id="__NEXT_DATA__" type="application/json">' + json.dumps(DATA) + "</script></html>"


def test_parse_page():
    ads, total = parse_page(HTML, NOW)
    assert total == 60 and len(ads) == 2
    a, b = ads
    assert a["external_id"] == "m2438300789" and a["price"] == 45 and a["condition"] == "used"
    assert a["posted_at"] == datetime(2026, 9, 2, tzinfo=UTC) and a["photos_count"] == 2
    assert a["photo_urls"][0] == "https://images.marktplaats.com/a.jpg"
    assert a["url"].startswith("https://www.marktplaats.nl/v/")
    assert b["price"] is None and b["price_type"] == "FAST_BID" and b["posted_at"] == datetime(2026, 9, 14, tzinfo=UTC)


def test_parse_date_forms():
    assert parse_date("Vandaag", NOW) == datetime(2026, 9, 15, tzinfo=UTC)
    assert parse_date("Eergisteren", NOW) == datetime(2026, 9, 13, tzinfo=UTC)
    assert parse_date("29 aug 26", NOW) == datetime(2026, 8, 29, tzinfo=UTC)
    assert parse_date("onbekend", NOW) is None
