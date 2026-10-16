"""GET /municipality/{ine_code} (B1 Tasks 36 y 37): indicadores DEC-09 con fuente y fecha, sin ranking."""
import json

import duckdb
import pytest
from fastapi.testclient import TestClient

import settings
from main import app, get_repo
from mini_data import build_mini_data
from repository import Repository
from settings import DATA_DIR

KEYS = [i["key"] for i in settings.load("indicators")["indicators"]]


@pytest.fixture
def mini(tmp_path):
    base = build_mini_data(tmp_path / "data")
    app.dependency_overrides[get_repo] = lambda: Repository(base)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _status(base, code="28065"):
    app.dependency_overrides[get_repo] = lambda: Repository(base)
    try:
        return TestClient(app, raise_server_exceptions=False).get(f"/municipality/{code}")
    finally:
        app.dependency_overrides.clear()


def test_municipality_getafe_indicators(mini):
    r = mini.get("/municipality/28065")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ine_code"] == "28065" and data["name"] == "Getafe" and data["population"] == 193238
    assert [i["key"] for i in data["indicators"]] == KEYS          # orden de indicators.yaml, agrupado por categoria
    sport = next(i for i in data["indicators"] if i["key"] == "sport_facilities")
    assert sport == {"category": "sport", "key": "sport_facilities", "label": "Instalaciones deportivas",
                     "value": 19.0, "unit": "instalaciones", "year": None,
                     "source": {"source": "nmc_deporte", "label": "Instalaciones deportivas (Nomecalles, Comunidad de Madrid)",
                                "date": "2026-10-16T15:56:26", "own_criterion": False}}
    green = next(i for i in data["indicators"] if i["key"] == "green_m2_per_inhabitant")
    assert green["year"] == 2025 and green["value"] == pytest.approx(172.788)
    assert data["fit"] == []


def test_municipality_missing_is_null(mini):
    data = mini.get("/municipality/28079").json()
    green = next(i for i in data["indicators"] if i["key"] == "green_m2_per_inhabitant")
    assert green["value"] is None and green["source"]["source"] == "vpla_redes"   # «sin datos», nunca 0
    # un indicador del YAML sin fila en la tabla tambien sale, como «sin datos»
    assert len(data["indicators"]) == len(KEYS)
    sport = next(i for i in data["indicators"] if i["key"] == "sport_facilities")
    assert sport["value"] is None and sport["label"] == "Instalaciones deportivas"


def test_municipality_unknown_404(mini):
    for code in ("28999", "abc"):
        r = mini.get(f"/municipality/{code}")
        assert r.status_code == 404
        assert "municipio" in r.json()["detail"]


def test_municipality_without_db_is_503(tmp_path):
    assert _status(tmp_path).status_code == 503


def test_municipality_old_db_is_503(tmp_path):
    """gomad.duckdb anterior a la Task 35 (sin municipality_indicator): 503 legible, no 500."""
    base = build_mini_data(tmp_path / "data")
    con = duckdb.connect(str(base / "gomad.duckdb"))
    con.execute("DROP TABLE municipality_indicator")
    con.close()
    r = _status(base)
    assert r.status_code == 503 and "indicadores" in r.json()["detail"]


def test_municipality_no_ranking(mini):
    text = json.dumps(mini.get("/municipality/28065").json(), ensure_ascii=False).lower()
    for word in ("rank", "posición", "percentil", "puesto"):
        assert word not in text


@pytest.fixture(scope="module")
def real():
    if not (DATA_DIR / "gomad.duckdb").exists():
        pytest.skip("sin app/data/gomad.duckdb")
    yield TestClient(app)                     # sin lifespan: get_repo crea Repository(DATA_DIR)


@pytest.mark.slow
def test_municipality_179_respond(real):
    con = duckdb.connect(str(DATA_DIR / "gomad.duckdb"), read_only=True)
    codes = [c for (c,) in con.execute("SELECT ine_code FROM municipality ORDER BY ine_code").fetchall()]
    con.close()
    assert len(codes) == 179
    values = {}
    for code in codes:
        r = real.get(f"/municipality/{code}")
        assert r.status_code == 200, (code, r.text)
        data = r.json()
        assert [i["key"] for i in data["indicators"]] == KEYS and data["population"] > 0
        values[code] = {i["key"]: i["value"] for i in data["indicators"]}
    assert values["28079"]["green_m2_per_inhabitant"] is None      # Madrid fuera de VPLA
    assert values["28107"]["sport_facilities"] is None             # Patones sin Nomecalles deporte
    assert values["28065"]["sport_facilities"] == 19
