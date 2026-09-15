"""«Мечи из Печи» — витрина на orgs.biz; код в `orgsbiz.py`."""
from hmb.importers import orgsbiz


def run(db, http=None, limit_pages=None):
    return orgsbiz.run(db, http=http, limit_pages=limit_pages, site="mechiizpechi")
