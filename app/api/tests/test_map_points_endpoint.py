"""GET /map/points (C2, Task 142): destinos y puntos utiles de la caja visible del mapa."""
import logging
import time

import pytest
from fastapi.testclient import TestClient

from main import app, get_map_config, get_repo
from mini_data import build_mini_data
from repository import Repository
from settings import DATA_DIR

BOX = "-3.735,40.300,-3.720,40.312"
CFG = {"own_criterion": True, "max_span_deg": 0.3, "max_points": 1500, "pool_activity": "swim"}


@pytest.fixture
def client(tmp_path):
    base = build_mini_data(tmp_path / "data")
    app.dependency_overrides[get_repo] = lambda: Repository(base)
    app.dependency_overrides[get_map_config] = lambda: dict(CFG)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_map_points_returns_destinations_by_default(client):
    r = client.get("/map/points", params={"bbox": BOX})
    assert r.status_code == 200
    data = r.json()
    assert data["truncated"] is False and data["clipped"] is False
    kinds = {p["kind"] for p in data["points"]}
    assert kinds <= {"facility", "pool", "park", "recreation_area", "trail", "bathing_area"}
    first = next(p for p in data["points"] if p["id"] == "eiel_parques:1")
    assert first == {"id": "eiel_parques:1", "kind": "park", "name": "Parque Uno",
                     "coordinate": {"lat": 40.3050, "lon": -3.7289}, "working": None, "source": "eiel_parques"}


def test_map_points_kinds_select_pois(client):
    r = client.get("/map/points", params=[("bbox", BOX), ("kinds", "fountain"), ("kinds", "bench")])
    points = {p["id"]: p for p in r.json()["points"]}
    assert set(points) == {"ay_fuentes:1", "ay_fuentes:2", "osm:node/1"}
    assert points["ay_fuentes:2"]["working"] is False
    assert points["osm:node/1"]["name"] is None


def test_map_points_bins_are_a_kind(client):
    # las papeleras (OSM) ya estan en route_poi: el mapa explorable tambien las pinta
    r = client.get("/map/points", params=[("bbox", BOX), ("kinds", "bin")])
    assert r.status_code == 200
    points = r.json()["points"]
    assert [(p["id"], p["kind"]) for p in points] == [("osm:node/2", "bin")]


def test_map_points_unknown_kind_is_422(client):
    assert client.get("/map/points", params={"bbox": BOX, "kinds": "casino"}).status_code == 422


@pytest.mark.parametrize("bbox", ["1,2,3", "x,0,1,1", "1,0,0,1", "0,0,1,95"])
def test_map_points_bad_bbox_is_422(client, bbox):
    r = client.get("/map/points", params={"bbox": bbox})
    assert r.status_code == 422
    assert "zona del mapa" in r.json()["detail"]


def test_map_points_needs_bbox(client):
    assert client.get("/map/points").status_code == 422


def test_map_points_clips_big_box(client):
    data = client.get("/map/points", params={"bbox": "-4.5,39.8,-3.0,41.2"}).json()
    assert data["clipped"] is True
    # centro -3.75, 40.5: la caja recortada (-3.9..-3.6, 40.35..40.65) no llega a Getafe (40.30)
    assert all(40.35 <= p["coordinate"]["lat"] <= 40.65 for p in data["points"])


def test_map_points_caps_points(client):
    app.dependency_overrides[get_map_config] = lambda: {**CFG, "max_points": 2}
    data = client.get("/map/points", params={"bbox": BOX}).json()
    assert len(data["points"]) == 2 and data["truncated"] is True


def test_map_points_without_data_is_503(tmp_path):
    app.dependency_overrides[get_repo] = lambda: Repository(tmp_path)
    app.dependency_overrides[get_map_config] = lambda: dict(CFG)
    try:
        assert TestClient(app).get("/map/points", params={"bbox": BOX}).status_code == 503
    finally:
        app.dependency_overrides.clear()


def test_map_points_does_not_log_bbox(client, caplog):
    with caplog.at_level(logging.INFO, logger="gomad.api"):
        client.get("/map/points", params={"bbox": "-3.7311,40.3013,-3.7207,40.3109"})
        client.get("/map/points", params={"bbox": "-3.7311,40.3013,x,40.3109"})
    text = " ".join(rec.getMessage() for rec in caplog.records)
    assert "/map/points" in text
    assert "3.7311" not in text and "40.3013" not in text and "bbox" not in text


@pytest.mark.slow
def test_map_points_real_data_latency():
    """Getafe a zoom 15 en un movil (~0,02 grados) con todos los tipos: < 0,5 s."""
    if not (DATA_DIR / "gomad.duckdb").exists():
        pytest.skip("sin gomad.duckdb")
    client = TestClient(app)
    kinds = [("kinds", k) for k in ("facility", "pool", "park", "recreation_area", "fountain", "bench", "aed",
                                     "dog_area", "playground")]
    t0 = time.perf_counter()
    r = client.get("/map/points", params=[("bbox", "-3.7400,40.2950,-3.7200,40.3150"), *kinds])
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200 and r.json()["points"]
    assert elapsed < 0.5
