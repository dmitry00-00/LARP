"""«Секира» (sekira.shop) — витрина на InSales; код в `insales.py`."""
from hmb.importers import insales


def run(db, http=None, limit_pages=None):
    return insales.run(db, http=http, limit_pages=limit_pages, site="sekira")
