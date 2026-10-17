from datetime import datetime, timedelta

import duckdb

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
    assert not any(w.startswith("Calor:") for w in res.warnings)          # DEC-06 cargado: ya hay umbral


def test_air_from_nearest_station_with_coverage(tmp_path):
    rec = run(tmp_path, request(window_end=NOW + timedelta(hours=5))).results[0]
    assert rec.hours[0].aqi_category == "good"                             # NO2 30; PM10 sin cobertura no cuenta
    assert rec.hours[-1].aqi_category is None                              # mas de 4 h tras la medicion: sin dato
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
    # aire «razonablemente buena» de 10 a 13 y sin dato a las 14 (tope de 4 h): la falta de dato no puede puntuar mejor
    res = run(tmp_path, request(window_end=NOW + timedelta(hours=5)), no2=50.0)
    rec = res.results[0]
    assert [h.aqi_category for h in rec.hours] == ["fair", "fair", "fair", "fair", None]
    assert rec.best_hour == NOW
    air = next(f for f in rec.factors if f.factor == "air")
    assert air.value == 8.0 and air.weight > 0                     # la nota del sitio si usa el aire medido
    weighted = sum(f.value * f.weight for f in rec.factors if f.value is not None)
    assert rec.score == pytest.approx(weighted, abs=0.01)
    assert PARTIAL_AIR in res.warnings


PARTIAL_AIR = ("Aire: solo hay dato, medido o previsto, para parte de la ventana; se usa el último para la nota, "
               "no para elegir la hora.")


def test_partial_air_warning_with_forecast_wording(tmp_path, monkeypatch):
    # dato previsto solo para las dos primeras horas y sin medicion: el aviso no puede hablar solo de «medición»
    with_air_forecast(monkeypatch, lambda h: "fair" if h <= NOW + timedelta(hours=1) else None)
    res = run(tmp_path, request(limit=1, window_end=NOW + timedelta(hours=5)), air=False)
    assert [h.aqi_category for h in res.results[0].hours] == ["fair", "fair", None, None, None]
    assert PARTIAL_AIR in res.warnings


def test_all_weight_on_air_with_partial_air_is_not_silent_zero(tmp_path):
    weights = {"proximity": 0, "suitability": 0, "green": 0, "air": 1, "weather": 0}
    res = run(tmp_path, request(window_end=NOW + timedelta(hours=4), weights=weights), no2=50.0)
    rec = res.results[0]
    assert rec.score == pytest.approx(8.0) and rec.best_hour == NOW


def _scored(id_, source, name, lon, lat, score=5.0):
    from repository import Candidate
    from services.recommend import Scored
    c = Candidate(id_, source, name, "park", False, "28079", lon, lat, None, "walk", 1.0, 0.0)
    return Scored(c, 100.0, False, False, [], None, score, {}, {})


def test_dedupe_across_sources_and_same_name_far():
    from services.recommend import _page
    retiro = _scored("nmc_parques:133", "nmc_parques", "Parque del Buen Retiro", -3.6845, 40.4153, 9)
    jardines = _scored("ay_parques:5896013", "ay_parques", "Jardines de El Buen Retiro", -3.68450, 40.41564, 8)  # 38 m
    prado_ay = _scored("ay_parques:1", "ay_parques", "Parque del Museo del Prado", -3.6920, 40.4140, 7)
    prado_nmc = _scored("nmc_parques:9", "nmc_parques", "Parque del Museo del Prado", -3.6920, 40.41534, 6)  # 149 m
    other = _scored("ay_parques:2", "ay_parques", "Parque de Otro Sitio", -3.70, 40.42, 5)
    req = s.RecommendRequest(origin=ORIGIN, activity="walk", window_start=NOW, window_end=NOW + timedelta(hours=1),
                             duration_min=45, max_distance_m=3000, limit=5)
    page, _ = _page([retiro, jardines, prado_ay, prado_nmc, other], req, 50, 300)
    assert [x.cand.id for x in page] == ["nmc_parques:133", "ay_parques:1", "ay_parques:2"]


def test_sources_do_not_repeat(tmp_path):
    # un destino de VPLA con verde llevaba vpla_redes dos veces (fuente del destino y fuente del verde)
    res = run(tmp_path, request(limit=10))
    vpla = next(r for r in res.results if r.destination.id == "vpla_redes:1")
    assert vpla.sources[0].source == "vpla_redes" and vpla.destination.source.source == "vpla_redes"
    for r in res.results:
        ids = [d.source for d in r.sources]
        assert len(ids) == len(set(ids)), ids


# guion de Carmen (DEC-06): Getafe, zona 722802 (umbral 37,4 °C); sensacion termica que baja por la tarde
CARMEN_FEELS = {15: 36.0, 16: 36.0, 17: 36.0, 18: 34.0, 19: 33.0, 20: 31.0, 21: 29.0, 22: 28.0}


def carmen(tmp_path, day_max, profile="senior", days=None, start=15, end=22, **kw):
    """Prevision de Getafe de 0 a 23 h; pico day_max a las 16 h (las demas de 14 a 18 h, un grado menos)."""
    base = build_mini_data(tmp_path / "data", forecast=False)
    rt = duckdb.connect(str(base / "realtime.duckdb"))
    for day, peak in (days or {16: day_max}).items():
        for h in range(24):
            temp = None if peak is None and 14 <= h <= 18 else (peak if h == 16 else peak - 1 if 14 <= h <= 18 else 25.0)
            rt.execute("INSERT INTO forecast VALUES ('28065', ?, ?, ?, 0, 0, 5, 'Despejado', '2026-10-16T08:00:00')",
                       [datetime(2026, 10, day, h), temp, CARMEN_FEELS.get(h, 25.0)])
    rt.close()
    req = request(profile=profile, window_start=datetime(2026, 10, 16, start),
                  window_end=datetime(2026, 10, 16, end) if end > start else datetime(2026, 10, 17, end), **kw)
    return recommend(req, Repository(base), GraphStore(), now=NOW)


def test_carmen_38_now_no_better_at_21(tmp_path):
    res = carmen(tmp_path, 38.0)
    rec = res.results[0]
    assert rec.best_hour == datetime(2026, 10, 16, 21)
    assert rec.explanation.startswith(
        "Ahora no: mejor a las 21:00 (día de calor (máx. prevista 38 °C, umbral de tu zona 37,4 °C)")
    assert "(umbral de criterio propio)" in rec.explanation
    assert "Día de calor en tu zona" not in res.warnings


def test_carmen_38_surprise_has_covered_alternative(tmp_path):
    res = carmen(tmp_path, 38.0, activity=None, limit=3)
    assert any(r.destination.covered for r in res.results)


def test_carmen_36_is_not_heat_day(tmp_path):
    res = carmen(tmp_path, 36.0)
    assert res.results[0].best_hour == datetime(2026, 10, 16, 15)
    assert not res.results[0].explanation.startswith("Ahora no")
    assert "Día de calor en tu zona" not in res.warnings


def test_heat_day_general_only_warns(tmp_path):
    res = carmen(tmp_path, 38.0, profile="general")
    assert "Día de calor en tu zona" in res.warnings
    assert res.results[0].hours[0].outdoor_ok is True


def test_heat_day_kids_companion_blocks(tmp_path):
    rec = carmen(tmp_path, 38.0, profile="general", companions=["kids"]).results[0]
    assert rec.hours[0].outdoor_ok is False and rec.best_hour == datetime(2026, 10, 16, 21)


def test_heat_day_max_ignores_missing_temps(tmp_path):
    rec = carmen(tmp_path, None, days={16: None}).results[0]
    assert rec.hours[0].outdoor_ok is True                                # sin temperatura de pico: no es dia de calor


def test_window_across_days_uses_each_day_max(tmp_path):
    rec = carmen(tmp_path, 38.0, days={16: 38.0, 17: 30.0}, start=22, end=17).results[0]
    by_hour = {h.hour: h for h in rec.hours}
    assert by_hour[datetime(2026, 10, 17, 15)].outdoor_ok is True         # el 17 no es dia de calor


# --- fila 2 (Task 92): aire previsto de CAMS en las horas futuras ------------------------------------------------------
class FakeAirForecast:
    """Feed falso: categoria prevista por hora solo para Getafe (28065), descargada a las 10:00."""

    def __init__(self, by_hour):
        self.by_hour = by_hour

    def get(self, ine):
        return (dict(self.by_hour), NOW) if ine == "28065" else None


def with_air_forecast(monkeypatch, category_of):
    hours = [NOW - timedelta(hours=2) + timedelta(hours=i) for i in range(48)]
    feed = FakeAirForecast({h: category_of(h) for h in hours})
    monkeypatch.setattr("services.recommend.air_forecast_feed", lambda repo: feed)


def test_future_hours_use_air_forecast(tmp_path, monkeypatch):
    with_air_forecast(monkeypatch, lambda h: "poor" if h > NOW else "good")
    res = run(tmp_path, request(window_end=NOW + timedelta(hours=5), profile="sensitive"))
    rec = next(r for r in res.results if r.destination.id == "eiel_parques:1")
    assert rec.hours[0].aqi_category == "good"                             # hora en curso: medicion real
    assert [h.aqi_category for h in rec.hours[1:]] == ["poor"] * 4         # horas futuras: previsto
    assert rec.best_hour == NOW
    future_air = [r for h in rec.hours[1:] for r in h.reasons if r.startswith("Calidad del aire")]
    assert future_air and all(r.endswith(" (prevista)") for r in future_air)
    assert not any(r.endswith(" (prevista)") for r in rec.hours[0].reasons)
    cams = [d for d in rec.sources if d.source == "cams_air"]
    assert len(cams) == 1 and "prevista" in cams[0].label and cams[0].date == NOW
    assert "Calidad del aire prevista" in rec.explanation


def test_current_hour_without_measurement_uses_forecast(tmp_path, monkeypatch):
    with_air_forecast(monkeypatch, lambda h: "fair")
    res = run(tmp_path, request(limit=1), air=False)      # solo Getafe: Madrid no tiene prevision falsa
    rec = res.results[0]
    assert rec.destination.id == "eiel_parques:1"
    assert [h.aqi_category for h in rec.hours] == ["fair", "fair", "fair"]
    assert not any(w.startswith("Aire: sin medición reciente") for w in res.warnings)
    assert any(d.source == "cams_air" for d in rec.sources)


def test_window_tomorrow_uses_forecast(tmp_path, monkeypatch):
    with_air_forecast(monkeypatch, lambda h: "moderate")
    base = build_mini_data(tmp_path / "data")
    rt = duckdb.connect(str(base / "realtime.duckdb"))
    for h in (8, 9, 10):
        rt.execute("INSERT INTO forecast VALUES ('28065', ?, 18, 18, 0, 0, 5, 'Despejado', '2026-10-16T08:00:00')",
                   [datetime(2026, 10, 17, h)])
    rt.close()
    req = request(window_start=datetime(2026, 10, 17, 8), window_end=datetime(2026, 10, 17, 10))
    rec = next(r for r in recommend(req, Repository(base), GraphStore(), now=NOW).results
               if r.destination.id == "eiel_parques:1")
    assert [h.aqi_category for h in rec.hours] == ["moderate", "moderate"]


def test_without_air_forecast_behaves_as_before(tmp_path, monkeypatch):
    monkeypatch.setattr("services.recommend.air_forecast_feed", lambda repo: None)
    rec = run(tmp_path, request(window_end=NOW + timedelta(hours=5))).results[0]
    assert rec.hours[0].aqi_category == "good" and rec.hours[-1].aqi_category is None
    assert not any(d.source == "cams_air" for d in rec.sources)


def test_covered_site_cites_cams_when_it_shows_forecast(tmp_path, monkeypatch):
    # RF-19: un cubierto tambien muestra hours[].aqi_category; si viene de CAMS, la fuente debe figurar
    with_air_forecast(monkeypatch, lambda h: "good")
    res = run(tmp_path, request(activity="gym", limit=10, window_end=NOW + timedelta(hours=3)))
    rec = next(r for r in res.results if r.destination.id == "eiel_deporte:1")
    assert [h.aqi_category for h in rec.hours][1:] == ["good", "good"]
    cams = [d for d in rec.sources if d.source == "cams_air"]
    assert len(cams) == 1 and cams[0].date == NOW
