import logging
import time
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

import main
from main import app, get_graphs, get_repo
from mini_data import build_mini_data
from repository import Repository
from routing.store import GraphStore
from settings import DATA_DIR

GETAFE = {"lat": 40.3057, "lon": -3.7329}
SOL = {"lat": 40.4169, "lon": -3.7035}


def body(origin, activity="walk", hours=3, **kw):
    now = datetime.now().replace(second=0, microsecond=0)
    return {"origin": origin, "activity": activity, "window_start": now.isoformat(),
            "window_end": (now + timedelta(hours=hours)).isoformat(), "duration_min": 45, "max_distance_m": 3000, **kw}


@pytest.fixture
def mini(tmp_path):
    base = build_mini_data(tmp_path / "data")
    app.dependency_overrides[get_repo] = lambda: Repository(base)
    app.dependency_overrides[get_graphs] = lambda: GraphStore()
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_activities_from_config():
    data = TestClient(app).get("/activities").json()
    assert [a["id"] for a in data["activities"]] == ["walk", "run", "swim", "padel", "tennis", "football", "basketball", "gym"]
    assert data["profiles"] == ["general", "senior", "stroller", "sensitive"] and data["companions"] == ["dog", "kids"]
    assert data["default_weights"]["proximity"] == 0.3


def test_unknown_activity_is_422(mini):
    assert mini.post("/recommend", json=body(GETAFE, activity="parapente")).status_code == 422


def test_recommend_without_data_is_503_not_500(tmp_path):
    app.dependency_overrides[get_repo] = lambda: Repository(tmp_path)
    app.dependency_overrides[get_graphs] = lambda: GraphStore()
    try:
        r = TestClient(app, raise_server_exceptions=False).post("/recommend", json=body(GETAFE))
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503


def test_logs_without_location(mini, caplog):
    caplog.set_level(logging.INFO, logger="gomad.api")
    mini.post("/recommend", json=body(GETAFE))
    mini.get("/location", params={"text": "calle madrid 10 getafe"})
    text = caplog.text
    assert "POST /recommend 200" in text and "GET /location" in text
    for secret in ("40.30", "-3.73", "madrid 10", "calle", "getafe"):
        assert secret not in text.lower()


@pytest.fixture(scope="module")
def real():
    if not (DATA_DIR / "gomad.duckdb").exists():
        pytest.skip("sin app/data/gomad.duckdb")
    with TestClient(app) as client:          # lifespan: carga los grafos de data/graph/
        yield client


@pytest.mark.slow
def test_recommend_getafe(real):
    t0 = time.perf_counter()
    r = real.post("/recommend", json=body(GETAFE))
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    data = r.json()
    print(f"\n/recommend Getafe: {elapsed:.2f} s, avisos: {data['warnings']}")
    assert elapsed < 3.0
    assert len(data["results"]) == 3 and data["has_more"]
    for rec in data["results"]:
        assert rec["destination"]["ine_code"] == "28065" or rec["distance_m"] <= 3000
        assert rec["explanation"] and rec["sources"] and 0 <= rec["score"] <= 10


@pytest.mark.slow
def test_recommend_capital_without_vpla(real):
    t0 = time.perf_counter()
    r = real.post("/recommend", json=body(SOL))
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    data = r.json()
    print(f"\n/recommend capital: {elapsed:.2f} s, avisos: {data['warnings']}")
    assert elapsed < 3.0
    assert data["results"]
    capital = [x for x in data["results"] if x["destination"]["ine_code"] == "28079"]
    assert capital and all(next(f for f in x["factors"] if f["factor"] == "green")["value"] is None for x in capital)
    assert any(w.startswith("Verde: sin datos en") and "Madrid" in w for w in data["warnings"])


@pytest.mark.slow
def test_surprise_me_three_distinct_activities(real):
    t0 = time.perf_counter()
    data = real.post("/recommend", json=body(GETAFE, activity=None)).json()
    print(f"\n/recommend Sorpréndeme: {time.perf_counter() - t0:.2f} s")
    labels = [r["explanation"].split("Para ")[1].split(":")[0] for r in data["results"]]
    assert len(labels) == 3 and len(set(labels)) == 3


def test_route_outside_graph_is_approximate(mini):
    r = mini.post("/route", json={"origin": GETAFE, "destination": {"lat": 40.95, "lon": -3.47}})
    assert r.status_code == 200
    data = r.json()
    assert data["direct"]["approximate"] and data["healthy"]["approximate"]
    assert data["direct"]["geometry"]["type"] == "LineString"


@pytest.mark.slow
def test_route_getafe(real):
    payload = {"origin": GETAFE, "destination": {"lat": 40.3120, "lon": -3.7230}}
    t0 = time.perf_counter()
    r = real.post("/route", json=payload)
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    data = r.json()
    print(f"\n/route Getafe: {elapsed:.2f} s · {data['direct']['description']} · {data['healthy']['description']}")
    assert elapsed < 5.0
    assert not data["direct"]["approximate"] and not data["healthy"]["approximate"]
    assert data["healthy"]["distance_m"] >= data["direct"]["distance_m"] - 1
    assert len(data["healthy"]["geometry"]["coordinates"]) > 2


@pytest.mark.slow
def test_route_capital(real):
    t0 = time.perf_counter()
    r = real.post("/route", json={"origin": SOL, "destination": {"lat": 40.4153, "lon": -3.6845}})   # Sol -> Retiro
    elapsed = time.perf_counter() - t0
    print(f"\n/route capital: {elapsed:.2f} s · {r.json()['healthy']['description']}")
    assert r.status_code == 200 and elapsed < 5.0


@pytest.mark.slow
def test_route_capital_four_at_once_under_5s(real):
    # el jurado entra a la vez tras la demo: 4 rutas largas simultaneas en la capital
    from concurrent.futures import ThreadPoolExecutor
    payload = {"origin": SOL, "destination": {"lat": 40.3800, "lon": -3.6200}}   # ~8,9 km, ~1 s sola

    def timed(_):
        t0 = time.perf_counter()
        r = real.post("/route", json=payload)
        assert r.status_code == 200
        return time.perf_counter() - t0
    real.post("/route", json=payload)                                   # calentar
    with ThreadPoolExecutor(4) as pool:
        times = list(pool.map(timed, range(4)))
    print(f"\n4 rutas a la vez en la capital: {[round(t, 2) for t in times]} s")
    assert max(times) < 5.0
