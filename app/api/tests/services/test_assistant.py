import pytest

import schemas as s
import settings
from ai.provider import RulesProvider
from mini_data import ORIGIN, build_mini_data
from repository import Repository
from routing.store import GraphStore
from services import assistant
from routing.graph import RouteNotFound
from routing.loop import Waypoint
from services.assistant import NoDestination, assistant_route

PARK = [-3.7289, 40.3050]            # «Parque Uno», nodo 1 del grafo mini
PATONES = {"lat": 40.9500, "lon": -3.4700}


@pytest.fixture
def setup(tmp_path):
    base = build_mini_data(tmp_path / "data", graph=True)
    return Repository(base), GraphStore.load(base / "graph"), RulesProvider(settings.load("assistant"))


def ask(setup, origin=ORIGIN, graphs=None, **params):
    repo, loaded, provider = setup
    req = s.AssistantRouteRequest(origin=origin, params=s.AssistantParams(**{"activity": "walk", **params}))
    return assistant_route(req, repo, loaded if graphs is None else graphs, provider)


def by_name(res):
    return {c.condition: c for c in res.conditions}


def test_passes_by_nearest_park(setup):
    res = ask(setup, loop=False, pass_by=["park"])          # sin objetivo: ida al parque
    assert res.route.kind == "healthy" and not res.route.approximate and res.written_by_ai is False
    assert res.route.geometry.coordinates[0] == [ORIGIN["lon"], ORIGIN["lat"]]
    assert res.route.geometry.coordinates[-1] == PARK
    assert res.route.distance_m == pytest.approx(220, abs=1)          # por el parque, no por la avenida
    park = by_name(res)["Pasar por: parque"]
    assert park.met and "Parque Uno" in park.detail
    assert by_name(res)["Solo ida"].met
    assert res.explanation.startswith("Ruta saludable de ida hasta «Parque Uno»")


def test_fountain_and_bench_checked_on_route(setup):
    res = ask(setup, distance_km=1, loop=False, pass_by=["fountain", "bench"])
    conditions = by_name(res)
    assert conditions["Pasar por: fuentes"].met and conditions["Pasar por: bancos"].met
    # la fuente cerrada (ay_fuentes:2) no se elige ni cuenta
    assert all(p.coordinate.lon != -3.72945 or p.type != "fountain" for p in res.route.pois)


def test_unavailable_conditions_are_honest(setup):
    res = ask(setup, distance_km=5, loop=True, pass_by=["supermarket"], avoid=["hills"])
    conditions = by_name(res)
    assert [c.condition for c in res.conditions] == ["Distancia de 5 km (±10 %)", "Ida y vuelta",
                                                     "Pasar por: supermercado", "Evitar: cuestas"]
    # el grafo mini no da 5 km: la ruta circular mas cercana, con el aviso de loop_route
    distance = conditions["Distancia de 5 km (±10 %)"]
    assert not distance.met and "la más cercana mide" in distance.detail
    assert conditions["Ida y vuelta"].met
    assert res.route.geometry.coordinates[-1] == [ORIGIN["lon"], ORIGIN["lat"]]
    assert "sin datos de supermercados" in conditions["Pasar por: supermercado"].detail.lower()
    assert "sin datos de desnivel" in conditions["Evitar: cuestas"].detail.lower()
    assert "parque más cercano" in res.explanation and "la más cercana mide" in res.explanation
    assert not any("todavía no está disponible" in c.detail for c in res.conditions)


def test_avoid_traffic(setup):
    res = ask(setup, distance_km=1, loop=False, pass_by=["park"], avoid=["traffic"])
    assert res.route.traffic_m == 0
    assert by_name(res)["Evitar: tráfico"].met


def test_round_trip_with_target_uses_loop_route(setup):
    res = ask(setup, distance_km=0.3, loop=True, pass_by=["park"])
    assert res.route.geometry.coordinates[0] == res.route.geometry.coordinates[-1] == [ORIGIN["lon"], ORIGIN["lat"]]
    assert res.route.distance_m == pytest.approx(320, abs=1)         # 0-2-3-1 por el parque y vuelta por la avenida
    conditions = by_name(res)
    assert conditions["Ida y vuelta"].met and conditions["Distancia de 0,3 km (±10 %)"].met
    assert conditions["Pasar por: parque"].met
    assert res.explanation.startswith("Ruta saludable de ida y vuelta")


def test_one_way_with_target_does_not_close(setup, monkeypatch):
    seen = {}
    real = assistant.loop_route

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(assistant, "loop_route", spy)
    res = ask(setup, distance_km=0.22, loop=False, pass_by=["park"])
    assert seen["loop"] is False and seen["waypoints"] == [1]
    assert seen["traffic_threshold"] == settings.load("routing")["traffic_display_threshold"]
    assert res.route.geometry.coordinates[-1] != [ORIGIN["lon"], ORIGIN["lat"]]
    assert by_name(res)["Solo ida"].met and by_name(res)["Distancia de 0,22 km (±10 %)"].met


def test_round_trip_without_target_returns_to_start(setup, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("sin objetivo no se llama a loop_route")

    monkeypatch.setattr(assistant, "loop_route", boom)
    res = ask(setup, loop=True, pass_by=["park"])
    assert res.route.geometry.coordinates[-1] == [ORIGIN["lon"], ORIGIN["lat"]]
    assert by_name(res)["Ida y vuelta"].met and [c.condition for c in res.conditions][0] == "Ida y vuelta"


@pytest.mark.parametrize("error", [RouteNotFound("sin conexion"), ValueError("objetivo")])
def test_loop_route_errors_fall_back(setup, monkeypatch, error):
    def fail(*a, **k):
        raise error

    monkeypatch.setattr(assistant, "loop_route", fail)
    res = ask(setup, distance_km=2, loop=True, pass_by=["park"])
    distance = by_name(res)["Distancia de 2 km (±10 %)"]
    assert not distance.met and "No se ha podido ajustar la distancia" in distance.detail
    assert by_name(res)["Ida y vuelta"].met and by_name(res)["Pasar por: parque"].met


def test_one_way_ending_at_automatic_point(setup, monkeypatch):
    real = assistant.loop_route

    def auto_end(g, origin, target_m, costs, cfg, **kw):
        r = real(g, origin, target_m, costs, cfg, **kw)
        r.waypoints = [Waypoint(1, -3.7289, 40.3050, True), Waypoint(3, -3.7289, 40.3043, False)]
        r.edges, r.coordinates = [1, 2, 3, 3], [[-3.73, 40.305], [-3.73, 40.3043], [-3.7289, 40.3043],
                                                [-3.7289, 40.305], [-3.7289, 40.3043]]
        return r

    monkeypatch.setattr(assistant, "loop_route", auto_end)
    res = ask(setup, distance_km=0.3, loop=False, pass_by=["park"])
    assert "un punto elegido" in res.explanation and "hasta «Parque Uno»" not in res.explanation


def test_no_network_is_approximate(setup):
    res = ask(setup, graphs=GraphStore(), distance_km=2, loop=False, pass_by=["park", "fountain"])
    assert res.route.approximate and res.route.geometry.coordinates[0] == [ORIGIN["lon"], ORIGIN["lat"]]
    assert not by_name(res)["Pasar por: fuentes"].met


def test_nothing_nearby_raises(setup):
    with pytest.raises(NoDestination):
        ask(setup, origin=PATONES, graphs=GraphStore(), distance_km=2, pass_by=["park"])


def test_waypoint_far_from_network_is_approximate(setup, monkeypatch):
    far = assistant._Point("park", "Parque Dos", -3.7300, 40.3100, 556.0)    # a 555 m del nodo mas cercano
    monkeypatch.setattr(assistant, "_nearest", lambda repo, origin, kind, rcfg, pool: far if kind == "park" else None)
    res = ask(setup, distance_km=1, loop=False, pass_by=["park"])
    assert res.route.approximate
    assert res.route.geometry.coordinates[-1] == [-3.7300, 40.3100]
    assert not by_name(res)["Pasar por: parque"].met
    assert res.explanation.startswith("Ruta aproximada hasta «Parque Dos»")


def test_approximate_target_is_never_met(setup):
    res = ask(setup, graphs=GraphStore(), distance_km=0.1, loop=False, pass_by=["park"])
    distance = by_name(res)["Distancia de 0,1 km (±10 %)"]
    assert res.route.approximate and not distance.met
    assert distance.detail == settings.load("assistant")["route"]["texts"]["no_network"]
