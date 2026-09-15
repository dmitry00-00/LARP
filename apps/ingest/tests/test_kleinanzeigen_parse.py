"""Разбор выдачи kleinanzeigen — на срезе реальной разметки 15.09.2026 (Astro,
JSON-LD ImageObject у каждого объявления). Ломается разметка — ломается тест,
а не молча пустая выдача (AGENT_RULES §14)."""
from datetime import UTC, datetime

from hmb.importers.kleinanzeigen import parse_listing

HTML = """<html><body>
<article class="flex" data-adid="3513463857" data-href="/s-anzeige/larp-polsterwaffe-streitkolben/3513463857-242-2529">
 <div><script type="application/ld+json">{"creditText":"Kleinanzeigen","title":"LARP Polsterwaffe / Streitkolben Latex / Mittelalter/Cosplay","description":"Ich verkaufe meinen wenig genutzten LARP Streitkolben.\\n\\nGröße: ca. 80cm Länge","contentUrl":"https://img.kleinanzeigen.de/api/v1/prod-ads/images/87/x?rule=$_59.AUTO","@context":"https://schema.org","@type":"ImageObject"}</script>
  <a href="/s-anzeige/x"><div><img src="https://img.kleinanzeigen.de/x" alt="x"><div>3</div></div></a></div>
 <div><div><div><svg></svg>31628 Landesbergen</div><div><svg></svg><span>Heute, 12:17</span></div></div>
  <h2><a href="/s-anzeige/x">LARP Polsterwaffe / Streitkolben Latex / Mittelalter/Cosplay</a></h2>
  <p>Ich verkaufe meinen wenig genutzten LARP Streitkolben. Die Polsterwaffe wurde nur auf einer...</p>
  <div><p class="my-xsmall text-title3 font-strong text-secondary">60 € VB</p><p>Versand möglich</p></div></div>
</article>
<article data-adid="1" data-href="/s-anzeige/y/1"><div></div><div><div>10115 Berlin</div><div>13.09.2026</div><h2><a>Schwert LARP Ritter Schaumgummi neu</a></h2><p>Neu.</p><p class="text-title3">1.250 €</p></div></article>
</body></html>"""


def test_parse_listing_fields():
    now = datetime(2026, 9, 15, 14, 0, tzinfo=UTC)
    ads = parse_listing(HTML, now)
    assert len(ads) == 2
    a = ads[0]
    assert a["external_id"] == "3513463857"
    assert a["url"].startswith("https://www.kleinanzeigen.de/s-anzeige/")
    assert a["title"].startswith("LARP Polsterwaffe")
    assert "80cm" in a["description"]
    assert a["price"] == 60 and a["negotiable"] is True and a["shipping"] is True
    assert a["city"] == "Landesbergen" and a["plz"] == "31628"
    assert a["posted_at"] == datetime(2026, 9, 15, 12, 17, tzinfo=UTC)
    assert a["photos_count"] == 3 and a["photo_urls"]
    b = ads[1]
    assert b["price"] == 1250 and b["negotiable"] is False
    assert b["posted_at"].date().isoformat() == "2026-09-13"
    assert b["title"] == "Schwert LARP Ritter Schaumgummi neu"


def test_empty_page_gives_empty_list_not_error():
    assert parse_listing("<html><body>Keine Ergebnisse</body></html>") == []
