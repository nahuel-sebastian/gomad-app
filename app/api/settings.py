"""Rutas compartidas y carga de config/*.yaml. Los valores decididos por el equipo viven ahi, nunca en el codigo."""
import functools
import os
import pathlib

import yaml

APP_DIR = pathlib.Path(__file__).resolve().parent.parent                       # app
CONFIG_DIR = pathlib.Path(os.environ.get("GOMAD_CONFIG_DIR", APP_DIR / "config"))
DATA_DIR = pathlib.Path(os.environ.get("GOMAD_DATA_DIR", APP_DIR / "data"))


@functools.cache
def load(name: str) -> dict | None:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        return None
    return yaml.safe_load(path.read_text(encoding="utf-8"))
