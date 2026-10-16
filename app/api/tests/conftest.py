import os
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]      # app/api
DATA_DIR = ROOT.parent / "data"                          # app/data
# ninguna prueba llama a los portales: sin LiveStore, la API lee realtime.duckdb como antes de B2
os.environ.setdefault("GOMAD_LIVE", "off")


@pytest.fixture
def root():
    return ROOT


def pytest_collection_modifyitems(config, items):
    # las pruebas "slow" necesitan app/data descargado; si no esta, se saltan
    if (DATA_DIR / "raw" / "municipios" / "municipios.geojson").exists():
        return
    skip = pytest.mark.skip(reason="faltan datos reales en app/data (ingest/scripts/download_sources.py)")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
