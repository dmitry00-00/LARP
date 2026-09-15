"""Импортёры: по модулю на источник, у каждого `run(db, **kw) -> dict` с числами."""
import importlib


def load(name: str):
    return importlib.import_module(f"hmb.importers.{name}")
