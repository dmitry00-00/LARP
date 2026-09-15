"""Mytholon (mytholon.com) — витрина на Shopware 6; код в `shopware.py`."""
from hmb.importers import shopware


def run(db, http=None, limit_pages=None):
    return shopware.run(db, http=http, limit_pages=limit_pages, site="mytholon")
