"""Registro de normalizadores: uno por fuente -> app/data/clean/<nombre>.parquet.

Uso: python -m normalize                  # todos
     python -m normalize green poi         # solo esos
"""
import importlib
import pkgutil

REGISTRY = {}


def normalizer(name):
    def register(func):
        REGISTRY[name] = func
        return func
    return register


def load_all():
    for m in pkgutil.iter_modules(__path__):
        if m.name != "__main__":
            importlib.import_module(f"{__name__}.{m.name}")
    return REGISTRY
