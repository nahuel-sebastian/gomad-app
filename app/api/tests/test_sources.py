"""GET /sources (B1 Task 38): editor, licencia, URL y fechas de cada fuente usada (RF-19)."""
import json
from datetime import timedelta

from fastapi.testclient import TestClient

import schemas as s
import settings
from main import app, get_repo
from mini_data import NOW, ORIGIN, build_mini_data
from repository import Repository
from routing.store import GraphStore
from services.recommend import recommend
from services.route import route
from services.sources import used_ids

PARK = {"lat": 40.3050, "lon": -3.7289}         # nodo 1 del grafo minimo


def get_sources(base):
    app.dependency_overrides[get_repo] = lambda: Repository(base)
    try:
        r = TestClient(app, raise_server_exceptions=False).get("/sources")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200, r.text
    return {x["id"]: x for x in r.json()["sources"]}


def test_sources_all_have_license():
    cfg = settings.load("sources")
    ids = used_ids(cfg, settings.load("indicators"))
    assert {"aemet", "osm", "nmc_deporte", "sanitarios", "padron", "boe_ica", "sanidad_calor",
            "config:weights"} <= ids
    assert "destination_activity" not in ids                     # tabla de build_db, no una fuente
    for sid in ids:
        entry = cfg["catalog"].get(sid)
        assert entry, f"{sid} sin entrada en catalog"
        assert cfg["labels"].get(sid), f"{sid} sin etiqueta"
        assert entry["publisher"] and entry["license"], sid
        assert entry["url"].startswith("https://"), sid


def test_sources_endpoint_dates(tmp_path):
    base = build_mini_data(tmp_path / "data")
    (base / "raw").mkdir()
    (base / "raw" / "manifest.json").write_text(json.dumps({
        "eiel_parques": {"downloaded": "2026-10-14T15:51:38", "checked": "2026-10-16T11:47:46"},
        "aemet": {"last_failure": {"date": "2026-10-16T11:48:08", "error": "Falta AEMET_API_KEY"}},
    }), encoding="utf-8")
    got = get_sources(base)
    assert list(got) == list(settings.load("sources")["catalog"])          # todas, en el orden del YAML
    assert got["eiel_parques"]["last_refresh"] == "2026-10-16T11:47:46"
    assert got["eiel_parques"]["last_failure"] is None
    assert got["aemet"]["last_refresh"] is None and got["aemet"]["last_failure"] == "2026-10-16T11:48:08"
    assert got["osm"]["license"].startswith("ODbL")
    assert got["eiel_parques"]["name"] == settings.load("sources")["labels"]["eiel_parques"]


def test_sources_without_manifest(tmp_path):
    base = build_mini_data(tmp_path / "data")
    got = get_sources(base)
    assert got["nmc_deporte"]["last_refresh"] == "2026-10-16T15:56:26"       # de source_date
    assert got["osm"]["last_refresh"] == "2026-10-14T01:55:22"                # Last-Modified en hora local
    assert got["sanitarios"]["last_refresh"] is None and got["sanitarios"]["last_failure"] is None


def test_sources_without_database(tmp_path):
    got = get_sources(tmp_path)
    assert got and all(x["last_refresh"] is None and x["last_failure"] is None for x in got.values())


def test_sources_broken_manifest(tmp_path):
    base = build_mini_data(tmp_path / "data")
    (base / "raw").mkdir()
    (base / "raw" / "manifest.json").write_text("{roto", encoding="utf-8")
    assert get_sources(base)["nmc_deporte"]["last_refresh"] == "2026-10-16T15:56:26"


def test_every_response_source_is_listed(tmp_path):
    base = build_mini_data(tmp_path / "data", graph=True)
    repo, graphs = Repository(base), GraphStore.load(base / "graph")
    req = dict(origin=ORIGIN, activity="walk", window_start=NOW, window_end=NOW + timedelta(hours=3),
               duration_min=45, max_distance_m=1000, limit=10)
    seen = []
    for res in (recommend(s.RecommendRequest(**req), repo, graphs, now=NOW),
                recommend(s.RecommendRequest(**req), repo, GraphStore(), now=NOW)):     # con linea recta
        seen += [d for r in res.results for d in r.sources]
    seen += route(s.RouteRequest(origin=ORIGIN, destination=PARK), repo, graphs).sources
    seen += route(s.RouteRequest(origin=ORIGIN, destination={"lat": 40.95, "lon": -3.47}), repo, graphs).sources
    listed = get_sources(base)
    assert {"config:recommend", "config:straight_line", "config:weights", "osm", "eiel_parques"} <= {d.source for d in seen}
    for d in seen:
        assert d.source in listed, d.source
        # la etiqueta de la respuesta empieza por el nombre de /sources («… · estación X», «… × 1,3»)
        assert d.label.startswith(listed[d.source]["name"]), (d.label, listed[d.source]["name"])
