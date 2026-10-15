from datetime import timedelta

import pytest

import schemas as s
from mini_data import NOW, ORIGIN, build_mini_data
from repository import Repository
from routing.store import GraphStore
from services.recommend import MEDICAL_DISCLAIMER, UnknownActivity, recommend


def request(**kw):
    base = dict(origin=ORIGIN, activity="walk", window_start=NOW, window_end=NOW + timedelta(hours=3),
                duration_min=45, max_distance_m=1000)
    return s.RecommendRequest(**{**base, **kw})


def run(tmp_path, req=None, graph=False, **data):
    base = build_mini_data(tmp_path / "data", graph=graph, **data)
    graphs = GraphStore.load(base / "graph") if graph else GraphStore()
    return recommend(req or request(), Repository(base), graphs, now=NOW)


def test_ranking_pagination_and_disclaimer(tmp_path):
    first = run(tmp_path, request(limit=1))
    assert first.medical_disclaimer == MEDICAL_DISCLAIMER and first.has_more
    assert first.results[0].destination.id == "eiel_parques:1"
    assert first.results[0].destination.municipality == "Getafe"
    second = run(tmp_path / "b", request(limit=1, offset=1))
    assert second.results[0].destination.id != "eiel_parques:1"


def test_dedupe_same_name_close(tmp_path):
    ids = [r.destination.id for r in run(tmp_path, request(limit=10)).results]
    assert "eiel_parques:1" in ids and "nmc_parques:1" not in ids        # «PARQUE UNO» a 3 m: el mismo sitio


def test_missing_factors_renormalize_with_warnings(tmp_path):
    res = run(tmp_path, request(limit=10))
    capital = next(r for r in res.results if r.destination.id == "ay_parques:1")
    green = next(f for f in capital.factors if f.factor == "green")
    assert green.value is None and green.weight == 0
    assert sum(f.weight for f in capital.factors) == pytest.approx(1)
    assert "Verde: sin datos en Getafe, Madrid." in res.warnings
    assert "Previsión: sin datos para Madrid." in res.warnings
    assert any(w.startswith("Calor:") for w in res.warnings)              # DEC-06 pendiente (heat null)


def test_air_from_nearest_station_with_coverage(tmp_path):
    rec = run(tmp_path, request(window_end=NOW + timedelta(hours=4))).results[0]
    assert rec.hours[0].aqi_category == "good"                             # NO2 30; PM10 sin cobertura no cuenta
    assert rec.hours[-1].aqi_category is None                              # mas de 3 h tras la medicion: sin dato
    assert any(d.source == "aire_dia" and "Getafe" in d.label for d in rec.sources)


def test_rain_now_better_later_explains(tmp_path):
    res = run(tmp_path, precip=lambda h: 90.0 if h == 0 else 0.0)
    rec = res.results[0]
    assert rec.hours[0].outdoor_ok is False and rec.best_hour == NOW + timedelta(hours=1)
    assert rec.explanation.startswith("Ahora no: mejor a las 11:00 (lluvia: 90 % de probabilidad (umbral de criterio propio))")


def test_rain_all_window_proposes_covered(tmp_path):
    res = run(tmp_path, precip=90.0, forecast_ines=("28065", "28079"))
    assert res.results[0].indoor_alternative and res.results[0].destination.id == "eiel_deporte:1"
    assert any("sitios cubiertos" in w for w in res.warnings)


def test_surprise_me_distinct_activities(tmp_path):
    res = run(tmp_path, request(activity=None, limit=3))
    labels = [r.explanation.split("Para ")[1].split(":")[0] for r in res.results]
    assert len(set(labels)) == len(labels) == 3                          # caminar, correr y gimnasio
    assert not res.has_more                                              # no hay una cuarta actividad a 1 km


def test_distance_graph_or_approximate(tmp_path):
    res = run(tmp_path, request(limit=10), graph=True)
    by_id = {r.destination.id: r for r in res.results}
    assert by_id["eiel_parques:1"].distance_m == pytest.approx(100, abs=1)          # por la red: 100 m
    assert not any(d.source == "config:recommend" for d in by_id["eiel_parques:1"].sources)
    assert any(d.source == "config:recommend" and d.own_criterion for d in by_id["nmc_parques:2"].sources)
    assert by_id["nmc_parques:2"].distance_m == pytest.approx(555.9 * 1.3, rel=0.01)


def test_window_in_past_warns(tmp_path):
    res = run(tmp_path, request(window_start=NOW - timedelta(hours=5), window_end=NOW - timedelta(hours=3)))
    assert "La ventana horaria elegida ya ha pasado: elige otra." in res.warnings
    assert all(r.hours == [] and r.best_hour is None for r in res.results)


def test_unknown_activity(tmp_path):
    with pytest.raises(UnknownActivity):
        run(tmp_path, request(activity="parapente"))


def test_explanation_numbers_match_object(tmp_path):
    rec = run(tmp_path).results[0]
    from engine.explanation import fmt_distance, fmt_number
    assert fmt_distance(rec.distance_m) in rec.explanation and fmt_number(rec.score) in rec.explanation


def test_rain_blocks_even_if_a_place_has_no_forecast(tmp_path):
    # Parque Capital (28079) no tiene prevision: no debe impedir la alternativa cubierta si llueve donde hay datos
    res = run(tmp_path, precip=90.0)
    assert any(r.indoor_alternative and r.destination.id == "eiel_deporte:1" for r in res.results)
    assert any("sitios cubiertos" in w for w in res.warnings)


def test_hour_without_air_data_does_not_win(tmp_path):
    # aire «razonablemente buena» de 10 a 12 y sin dato a las 13: la falta de dato no puede puntuar mejor
    res = run(tmp_path, request(window_end=NOW + timedelta(hours=4)), no2=50.0)
    rec = res.results[0]
    assert [h.aqi_category for h in rec.hours] == ["fair", "fair", "fair", None]
    assert rec.best_hour == NOW
    air = next(f for f in rec.factors if f.factor == "air")
    assert air.value == 8.0 and air.weight == 0                    # dato solo en parte de la ventana: no puntua
    assert rec.score == pytest.approx(rec.hours[0].score)
