"""Cada descarga que lee la ingesta tiene editor, licencia y URL en config/sources.yaml (RF-19, /sources)."""
import importlib.util
import pathlib
import re

import yaml

from common import CONFIG_DIR

ROOT = pathlib.Path(__file__).resolve().parent.parent           # app/ingest


def _download_ids():
    spec = importlib.util.spec_from_file_location("download_sources", ROOT / "scripts" / "download_sources.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return set(mod.SOURCES)


def read_by_ingest():
    """Ids de descarga citados como literal en el codigo de procesado (normalize, build_db, graph, common...)."""
    files = [*ROOT.glob("*.py"), *(ROOT / "normalize").glob("*.py")]
    text = "\n".join(p.read_text(encoding="utf-8") for p in files)
    return {i for i in _download_ids() if re.search(rf"[\"']{re.escape(i)}[\"']", text)}


def test_every_ingested_source_is_in_catalog():
    cfg = yaml.safe_load((CONFIG_DIR / "sources.yaml").read_text(encoding="utf-8"))
    used = read_by_ingest()
    # las que alimentan estaciones de aire y el reparto por municipio no salen en ninguna respuesta,
    # pero sus datos si se ven (nombre de la estacion, municipio de cada destino)
    assert {"aire_estaciones", "ay_aire_estaciones", "municipios", "nmc_deporte", "osm"} <= used
    missing = sorted(used - set(cfg["catalog"]))
    assert missing == [], f"sin entrada en catalog de sources.yaml: {missing}"
    unlabeled = sorted(used - set(cfg["labels"]))
    assert unlabeled == [], f"sin etiqueta en sources.yaml: {unlabeled}"
