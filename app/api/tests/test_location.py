import httpx
import pytest
from fastapi.testclient import TestClient

from geocoding import Geocoder, plain
from main import app, get_geocoder
from mini_data import build_mini_data
from settings import DATA_DIR

NOMECALLES = {"data": {"direcciones": [
    {"id": 5187835, "direccion": "Calle Madrid 10", "tipo": "app", "municipio": "065", "nombreMunicipio": "Getafe",
     "cdVial": "065A0460"},
    {"id": 289285, "direccion": "Calle Madrid", "tipo": "calle", "municipio": "065", "nombreMunicipio": "Getafe",
     "cdVial": "065A0460"},
    {"id": 291492, "direccion": "Calle de Camino de Getafe", "tipo": "calle", "municipio": "058",
     "nombreMunicipio": "Fuenlabrada", "cdVial": "058A0201"}]}}


@pytest.fixture
def data(tmp_path):
    return build_mini_data(tmp_path / "data")


def client_with(handler):
    calls = []

    def wrapped(request):
        calls.append(request)
        return handler(request)
    return httpx.Client(transport=httpx.MockTransport(wrapped)), calls


def test_plain():
    assert plain("  GETAFÉ, C/ Madrid nº10 ") == "getafe c madrid no10"     # igual que ingest (street_norm)


def test_location_number_glued_to_letters(data):
    out = Geocoder(data).search("C/ Madrid nº10, Getafe")
    assert out[0]["label"] == "Calle Madrid 10, Getafe" and out[0]["precision"] == "address"


def test_location_address_with_number_local(data):
    out = Geocoder(data).search("calle madrid 10 getafe")
    assert out[0] == {"label": "Calle Madrid 10, Getafe", "municipality": "Getafe", "ine_code": "28065",
                      "coordinate": {"lat": 40.3056775, "lon": -3.7314934}, "precision": "address"}
    assert out[-1]["precision"] == "municipality" and out[-1]["ine_code"] == "28065"


def test_location_street_without_number(data):
    out = Geocoder(data).search("Calle de la Constitución, Getafe")
    assert out[0]["precision"] == "street" and out[0]["label"] == "Calle de la Constitución, Getafe"


def test_location_municipality_by_name_without_accents(data):
    for text in ("MADRID", "getafé", "Getafe"):
        out = Geocoder(data).search(text)
        assert out[0]["precision"] == "municipality"
    assert Geocoder(data).search("GETAFÉ")[0]["coordinate"] == {"lat": pytest.approx(40.295), "lon": pytest.approx(-3.725)}
    assert Geocoder(data).search("geta")[0]["municipality"] == "Getafe"     # parcial, sin numero ni calle


def test_location_municipality_words_before_streets(data):
    # «las rozas» es parte del nombre de Las Rozas de Madrid y tambien una calle de Getafe: primero el municipio
    out = Geocoder(data).search("las rozas")
    assert out[0]["precision"] == "municipality" and out[0]["label"] == "Las Rozas de Madrid"
    assert any(c["label"] == "Calle de las Rozas, Getafe" for c in out)


def test_location_uses_nomecalles_only_when_local_fails_and_caches(data):
    client, calls = client_with(lambda r: httpx.Response(200, json=NOMECALLES))
    g = Geocoder(data, client)
    assert g.search("calle madrid 10 getafe")[0]["label"] == "Calle Madrid 10, Getafe"
    assert calls == []                                                     # el callejero local ya lo encuentra
    out = g.search("calle madrd 10 getafe")                                # errata: solo la arregla el buscador
    assert out[0]["precision"] == "address" and out[0]["coordinate"]["lon"] == pytest.approx(-3.7314934)
    assert all(c["ine_code"] == "28065" for c in out)                      # Fuenlabrada no: el texto dice Getafe
    g.search("Calle Madrd 10 Getafe")
    assert len(calls) == 1 and calls[0].url.params["busqueda"] == "calle madrd 10 getafe"


def test_location_nomecalles_down_falls_back_local(data):
    def down(request):
        raise httpx.ConnectError("caido")
    client, _ = client_with(down)
    out = Geocoder(data, client).search("calle madrd 10 getafe")
    assert out == [{"label": "Getafe", "municipality": "Getafe", "ine_code": "28065",
                    "coordinate": {"lat": 40.295, "lon": -3.725}, "precision": "municipality"}]
    client, _ = client_with(lambda r: httpx.Response(500))
    assert Geocoder(data, client).search("calle madrid 10 getafe")[0]["precision"] == "address"


def test_location_nothing_found(data):
    assert Geocoder(data).search("zzzzzz") == []


def test_location_text_bounds_422(data):
    app.dependency_overrides[get_geocoder] = lambda: Geocoder(data)
    try:
        c = TestClient(app)
        assert c.get("/location", params={"text": "ab"}).status_code == 422
        assert c.get("/location", params={"text": "x" * 201}).status_code == 422
        r = c.get("/location", params={"text": "calle madrid 10 getafe"})
        assert r.status_code == 200 and r.json()["candidates"][0]["precision"] == "address"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.slow
def test_location_real_calle_madrid_10_getafe():
    if not (DATA_DIR / "clean" / "addresses.parquet").exists():
        pytest.skip("sin clean/addresses.parquet (python -m normalize addresses en ingest)")
    out = Geocoder(DATA_DIR).search("calle madrid 10 getafe")          # D-04, solo callejero local
    assert out[0]["precision"] == "address" and out[0]["ine_code"] == "28065"
    assert out[0]["coordinate"]["lon"] == pytest.approx(-3.7314934, abs=1e-6)
    assert out[0]["coordinate"]["lat"] == pytest.approx(40.3056775, abs=1e-6)


def test_location_without_municipality_file_is_503_not_500(data):
    (data / "clean" / "municipality.parquet").unlink()
    app.dependency_overrides[get_geocoder] = lambda: Geocoder(data)
    try:
        r = TestClient(app, raise_server_exceptions=False).get("/location", params={"text": "calle madrid 10 getafe"})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503 and "datos" in r.json()["detail"]
