import logging

import pytest
from fastapi.testclient import TestClient

import settings
from ai.dictionary import Analysis
from ai.provider import RulesProvider
from main import app, get_assistant, get_graphs, get_repo
from mini_data import ORIGIN, build_mini_data
from repository import Repository
from routing.store import GraphStore

EXAMPLE = "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado"
PATONES = {"lat": 40.9500, "lon": -3.4700}


class SpyLanguage:
    """OCI Language simulado: guarda exactamente lo que se le envia."""

    def __init__(self):
        self.sent = []

    def analyze(self, text):
        self.sent.append(text)
        return Analysis(entities=[("15 km", "QUANTITY")], phrases=["parque"])


@pytest.fixture
def client(tmp_path):
    base = build_mini_data(tmp_path / "data", graph=True)
    language = SpyLanguage()
    app.dependency_overrides[get_repo] = lambda: Repository(base)
    app.dependency_overrides[get_graphs] = lambda: GraphStore.load(base / "graph")
    app.dependency_overrides[get_assistant] = lambda: RulesProvider(settings.load("assistant"), language)
    yield TestClient(app), language
    app.dependency_overrides.clear()


def test_interpret_endpoint(client):
    http, _ = client
    r = http.post("/assistant/interpret", json={"text": EXAMPLE})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["params"]["distance_km"] == 15 and data["clarification"] is None and data["rejection"] is None


def test_interpret_rejects_medical(client):
    http, _ = client
    data = http.post("/assistant/interpret", json={"text": "¿Puedo correr con la tensión alta?"}).json()
    assert data["params"] is None and "consejo médico" in data["rejection"]


def test_interpret_sends_only_text_and_logs_nothing(client, caplog):
    http, language = client
    caplog.set_level(logging.INFO, logger="gomad.api")
    http.post("/assistant/interpret", json={"text": EXAMPLE})
    assert language.sent == [EXAMPLE]
    assert "POST /assistant/interpret 200" in caplog.text
    assert "supermercado" not in caplog.text and "15 km" not in caplog.text


def test_route_endpoint_mini(client, caplog):
    http, language = client
    caplog.set_level(logging.INFO, logger="gomad.api")
    body = {"origin": ORIGIN, "params": {"activity": "walk", "distance_km": 1, "loop": False, "pass_by": ["park"]}}
    r = http.post("/assistant/route", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["written_by_ai"] is False and data["conditions"] and data["route"]["kind"] == "healthy"
    assert language.sent == []                      # la ruta nunca pasa por OCI
    assert "POST /assistant/route 200" in caplog.text
    assert "40.30" not in caplog.text and "-3.73" not in caplog.text


def test_route_without_destination_is_422(client):
    http, _ = client
    app.dependency_overrides[get_graphs] = lambda: GraphStore()
    body = {"origin": PATONES, "params": {"activity": "walk", "distance_km": 2, "pass_by": ["park"]}}
    r = http.post("/assistant/route", json=body)
    assert r.status_code == 422 and "parque" in r.json()["detail"]


def test_default_provider_without_credentials_is_dictionary_only(monkeypatch):
    for key in ("IA_PROVEEDOR", "OCI_COMPARTMENT_ID"):
        monkeypatch.delenv(key, raising=False)
    if hasattr(app.state, "assistant"):
        monkeypatch.delattr(app.state, "assistant")
    data = TestClient(app).post("/assistant/interpret", json={"text": "5 km con fuentes"}).json()
    assert data["params"]["pass_by"] == ["fountain"]
