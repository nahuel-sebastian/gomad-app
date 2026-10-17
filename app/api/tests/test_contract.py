import json

from fastapi.testclient import TestClient

from main import app

ROUTES = {
    ("get", "/activities"), ("get", "/location"), ("post", "/recommend"), ("post", "/route"),
    ("get", "/municipality/{ine_code}"), ("post", "/assistant/interpret"), ("post", "/assistant/route"),
    ("get", "/sources"), ("get", "/health"), ("get", "/map/points"),
}


def test_all_contract_routes_exist():
    schema = app.openapi()
    present = {(method, path) for path, ops in schema["paths"].items() for method in ops}
    assert ROUTES <= present


def test_versioned_openapi_is_up_to_date(root):
    """Si falla: python scripts/export_openapi.py y regenerar los tipos del front (Task 23)."""
    saved = json.loads((root.parent / "frontend" / "src" / "api" / "openapi.json").read_text(encoding="utf-8"))
    assert saved == app.openapi()


def test_inverted_window_is_422():
    body = {"origin": {"lat": 40.3, "lon": -3.73}, "window_start": "2026-10-20T10:00:00",
            "window_end": "2026-10-20T09:00:00", "duration_min": 45, "max_distance_m": 3000}
    r = TestClient(app).post("/recommend", json=body)
    assert r.status_code == 422


def test_unknown_field_is_422():
    r = TestClient(app).post("/assistant/interpret", json={"text": "15 km", "location": "x"})
    assert r.status_code == 422


def test_aware_window_is_converted_to_madrid_local_time():
    """El motor trabaja en hora local de Madrid sin zona; toISOString() del navegador manda UTC."""
    from datetime import datetime

    from schemas import RecommendRequest
    req = RecommendRequest(origin={"lat": 40.3, "lon": -3.73}, window_start="2026-10-20T09:00:00",
                           window_end="2026-10-20T18:00:00Z", duration_min=45, max_distance_m=3000)
    assert req.window_end == datetime(2026, 10, 20, 20, 0)      # CEST = UTC+2
    assert req.window_end.tzinfo is None


def test_mixed_timezone_inverted_window_is_422_not_500():
    body = {"origin": {"lat": 40.3, "lon": -3.73}, "window_start": "2026-10-20T13:00:00",
            "window_end": "2026-10-20T10:00:00Z", "duration_min": 45, "max_distance_m": 3000}
    r = TestClient(app, raise_server_exceptions=False).post("/recommend", json=body)
    assert r.status_code == 422
