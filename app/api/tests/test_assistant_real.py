import time

import pytest
from fastapi.testclient import TestClient

from main import app
from settings import DATA_DIR

GETAFE = {"lat": 40.3057, "lon": -3.7329}


@pytest.fixture(scope="module")
def real():
    if not (DATA_DIR / "gomad.duckdb").exists():
        pytest.skip("sin app/data/gomad.duckdb")
    with TestClient(app) as client:          # lifespan: carga el grafo regional
        yield client


@pytest.mark.slow
def test_assistant_route_getafe(real):
    body = {"origin": GETAFE, "params": {"activity": "walk", "distance_km": 3, "loop": False,
                                         "pass_by": ["park", "fountain", "bench"], "avoid": ["traffic"]}}
    t0 = time.perf_counter()
    r = real.post("/assistant/route", json=body)
    elapsed = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    data = r.json()
    print(f"\n/assistant/route Getafe: {elapsed:.2f} s · {data['explanation']}")
    for c in data["conditions"]:
        print(f"  {'OK' if c['met'] else 'NO'} {c['condition']}: {c['detail']}")
    assert elapsed < 5.0
    assert not data["route"]["approximate"] and data["written_by_ai"] is False
    assert len(data["conditions"]) == 6
    assert any(c["condition"] == "Pasar por: parque" and c["met"] for c in data["conditions"])
