"""calimacil — та же Shopify-витрина, что epicarmoury (см. там)."""
from hmb.importers import epicarmoury as _e


def run(db, **kw):
    return _e.run(db, site="calimacil", **kw)
