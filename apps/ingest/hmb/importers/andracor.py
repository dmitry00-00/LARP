"""Andracor (andracor.com) — витрина на OXID; код в `oxid.py`."""
from hmb.importers import oxid


def run(db, http=None, limit_pages=None):
    return oxid.run(db, http=http, limit_pages=limit_pages, site="andracor")
