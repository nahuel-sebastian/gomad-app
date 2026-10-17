"""GET /municipality/{ine_code} (B1 Tasks 36 y 37): indicadores DEC-09 con fuente y fecha, sin ranking."""
import json

import duckdb
import pytest
from fastapi.testclient import TestClient

import schemas as s
import settings
from main import app, get_repo
from mini_data import build_mini_data
from repository import Repository
from settings import DATA_DIR

KEYS = [i["key"] for i in settings.load("indicators")["indicators"]]
SRC = s.DataSource(source="sanitarios", label="Centros sanitarios", date=None)


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
                                "date": "2026-10-16T15:56:26", "own_criterion": False},
                     "extra_sources": []}
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


def test_municipality_lists_every_source(mini):
    """RF-19: un indicador con varias fuentes las cita todas (la primera en source, el resto en extra_sources)."""
    data = mini.get("/municipality/28065").json()
    by = {i["key"]: i for i in data["indicators"]}
    assert by["green_m2_per_inhabitant"]["source"]["source"] == "vpla_redes"
    assert [x["source"] for x in by["green_m2_per_inhabitant"]["extra_sources"]] == ["padron"]
    assert [x["source"] for x in by["rail_stations"]["extra_sources"]] == ["nmc_estcerca"]
    assert by["sport_facilities"]["extra_sources"] == []


def test_municipality_row_sources_split(mini):
    """C3: la fila guarda las fuentes que usa en ese municipio; la primera va a source, el resto a extra_sources,
    y despues las fijas del YAML (padron) que no esten ya."""
    by = {i["key"]: i for i in mini.get("/municipality/28127").json()["indicators"]}
    green = by["green_m2_per_inhabitant"]
    assert green["source"]["source"] == "osm" and green["year"] is None and green["value"] == pytest.approx(290.7)
    assert [x["source"] for x in green["extra_sources"]] == ["padron"]          # no cita vpla_redes: no se usa
    sport = by["sport_facilities_per_1000"]
    assert sport["source"]["source"] == "nmc_deporte"
    assert [x["source"] for x in sport["extra_sources"]] == ["osm", "padron"]


def test_municipality_single_source_row_unchanged(mini):
    by = {i["key"]: i for i in mini.get("/municipality/28065").json()["indicators"]}
    assert by["green_m2_per_inhabitant"]["source"]["source"] == "vpla_redes"
    assert [x["source"] for x in by["green_m2_per_inhabitant"]["extra_sources"]] == ["padron"]


def test_fit_says_own_criterion(mini):
    assert mini.get("/municipality/28065").json()["fit_own_criterion"] is False      # sin encaje
    assert mini.get("/municipality/28065", params={"profile": "senior"}).json()["fit_own_criterion"] is True


def test_municipality_broken_db_is_503(tmp_path):
    """Base con tablas de otra forma (columna que falta): 503 legible, no 500."""
    base = build_mini_data(tmp_path / "data")
    con = duckdb.connect(str(base / "gomad.duckdb"))
    con.execute("ALTER TABLE route_poi DROP COLUMN ine_code")
    con.close()
    app.dependency_overrides[get_repo] = lambda: Repository(base)
    try:
        r = TestClient(app, raise_server_exceptions=False).get("/municipality/28065", params={"companions": ["dog"]})
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 503


def test_poi_count_skips_out_of_service(tmp_path):
    base = build_mini_data(tmp_path / "data")
    repo = Repository(base)
    assert repo.poi_count("28065", "fountain") == 1          # la fuente CERRADA_TEMPORALMENT (working false) no cuenta


def test_validate_fit_fails_readably():
    from services.municipality import validate_fit
    cfg = settings.load("indicators")
    activities = [a["id"] for a in settings.load("activities")["activities"]]
    assert validate_fit(cfg, activities) is cfg
    bad = settings.load("indicators")
    bad["fit"]["profiles"]["senior"].append("no_existe")
    with pytest.raises(ValueError, match="no_existe"):
        validate_fit(bad, activities)
    bad = settings.load("indicators")
    bad["fit"]["activities"]["when_absent"] = "quizas"
    with pytest.raises(ValueError, match="quizas"):
        validate_fit(bad, activities)
    bad = settings.load("indicators")
    del bad["fit"]["companions"]["dog"]["label"]
    with pytest.raises(ValueError, match="dog"):
        validate_fit(bad, activities)


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
    # C3: Madrid fuera de VPLA con verde de OSM; Patones con EIEL; Getafe Nomecalles + OSM
    assert values["28079"]["green_m2_per_inhabitant"] > 0
    assert values["28107"]["sport_facilities"] == 4
    assert values["28065"]["sport_facilities"] >= 19
    nulls = {k for v in values.values() for k, x in v.items() if x is None}
    assert nulls == {"good_3g_pct"}                                # solo la conectividad fuera de EIEL


def fit(client, code="28065", **params):
    r = client.get(f"/municipality/{code}", params=params)
    assert r.status_code == 200, r.text
    return r.json()["fit"]


def test_fit_without_preferences_is_empty(mini):
    """Ruling (Task 37): sin preferencias no hay nada que contar -> lista vacia, no «Cumple 0 de 0»."""
    assert fit(mini) == []
    assert fit(mini, profile="general") == [] and fit(mini, profile="sensitive") == []


def test_fit_activities(mini):
    assert fit(mini, activities=["walk", "padel", "gym"]) == [
        "Cumple 2 de 3", "Caminar: sí, 5 sitios", "Pádel: no consta en nuestros datos",
        "Gimnasio y cubierto: sí, 1 sitio"]


def test_fit_repeated_preferences_count_once(mini):
    assert fit(mini, activities=["walk", "walk"], companions=["dog", "dog"]) == [
        "Cumple 1 de 2, 1 sin datos", "Caminar: sí, 5 sitios", "Áreas caninas: sin datos"]


def test_fit_absent_text_follows_source_coverage():
    """Regla general (16/10): el catalogo de destinos es parcial -> «no consta»; un registro completo o un valor
    medido 0 -> «no hay»; una fuente sin cobertura -> «sin datos» (no cuenta como incumplido)."""
    from services.municipality import fit_sentences
    cfg = {"met_if_above": 0, "activities": {"when_absent": "not_listed"},
           "profiles": {"senior": ["health_centres", "schools"]}, "companions": {"kids": ["schools"]}}
    ind = lambda key, value, unit="centros": s.Indicator(category="health", key=key, label=key, value=value,
                                                         unit=unit, year=None, source=SRC)
    by_key = {"health_centres": ind("health_centres", 0.0), "schools": ind("schools", 1.0)}
    out = fit_sentences(cfg, by_key, ["swim"], "senior", ["kids"], {"swim": "Nadar"}, lambda a: 0, lambda t: 0,
                        units_one={"schools": "centro"})
    # schools sale una sola vez aunque lo pidan el perfil y el acompanante; singular con 1
    assert out == ["Cumple 1 de 3", "Nadar: no consta en nuestros datos", "health_centres: no hay en este municipio",
                   "schools: sí, 1 centro"]


def test_fit_profile_and_companions(mini):
    assert fit(mini, profile="senior", companions=["kids", "dog"]) == [
        "Cumple 3 de 4, 1 sin datos",
        "Centros de salud y consultorios: sí, 9 centros",
        "Desfibriladores por 1.000 hab.: sí, 1,4 por 1.000 hab.",
        "Centros educativos: sí, 105 centros",
        "Áreas caninas: sin datos"]                 # Getafe sin areas caninas en route_poi: nunca «No»


def test_fit_no_and_no_data(mini):
    assert fit(mini, "28079", profile="senior") == [
        "Cumple 0 de 2, 1 sin datos", "Centros de salud y consultorios: no hay en este municipio",
        "Desfibriladores por 1.000 hab.: sin datos"]
    assert fit(mini, "28079", profile="stroller") == [
        "Cumple 0 de 1, 1 sin datos", "Zonas verdes por habitante: sin datos"]


def test_fit_dog_yes_where_there_is_data(mini):
    assert fit(mini, "28079", companions=["dog"]) == ["Cumple 1 de 1", "Áreas caninas: sí, 1 área"]


def test_fit_bad_preferences_are_422(mini):
    assert mini.get("/municipality/28065", params={"activities": ["parapente"]}).status_code == 422
    assert mini.get("/municipality/28065", params={"profile": "astronauta"}).status_code == 422
    assert mini.get("/municipality/28065", params={"companions": ["gato"]}).status_code == 422


def test_fit_never_ranks(mini):
    every = [a["id"] for a in settings.load("activities")["activities"]]
    for code in ("28065", "28079"):
        text = " ".join(fit(mini, code, activities=every, profile="senior", companions=["kids", "dog"])).lower()
        for word in ("posición", "puesto", "nota", "percentil", "ranking", "mejor", "peor", "media"):
            assert word not in text


def test_number_format():
    from services.municipality import number
    assert [number(9.0), number(1.366), number(172.788), number(1234.5), number(0.04)] == [
        "9", "1,4", "172,8", "1.234,5", "0,04"]
    # por debajo de 1, dos cifras significativas (nunca «0,00» ni «1,0» para algo que no es 1); sin ceros de cola
    assert [number(0.96), number(0.004), number(0.0456), number(9.96), number(2.5)] == [
        "0,96", "0,004", "0,046", "10", "2,5"]


@pytest.mark.slow
def test_fit_real_getafe(real):
    f = fit(real, "28065", activities=["walk", "swim"], profile="senior", companions=["dog"])
    assert f[0].startswith("Cumple ") and len(f) == 6
    assert f[1].startswith("Caminar: sí, ")
