import pytest

import schemas as s
import settings
from ai.provider import RulesProvider
from mini_data import ORIGIN, build_mini_data
from repository import Repository
from routing.store import GraphStore
from services import assistant
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
    res = ask(setup, duration_min=30, loop=False, pass_by=["park"])
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
    assert [c.condition for c in res.conditions] == ["Distancia de 5 km (±10 %)", "Circular",
                                                     "Pasar por: supermercado", "Evitar: cuestas"]
    assert not any(c.met for c in res.conditions)
    assert "todavía no está disponible" in conditions["Circular"].detail
    assert "todavía no está disponible" in conditions["Distancia de 5 km (±10 %)"].detail
    assert "sin datos de supermercados" in conditions["Pasar por: supermercado"].detail.lower()
    assert "sin datos de desnivel" in conditions["Evitar: cuestas"].detail.lower()
    assert "parque más cercano" in res.explanation and "Cumple 0 de 4 condiciones" in res.explanation


def test_avoid_traffic(setup):
    res = ask(setup, distance_km=1, loop=False, pass_by=["park"], avoid=["traffic"])
    assert res.route.traffic_m == 0
    assert by_name(res)["Evitar: tráfico"].met


def test_plan_loop_hook_is_used(setup, monkeypatch):
    calls = []

    def fake_loop(graph, origin_node, target_m, waypoint_nodes, costs):
        calls.append((origin_node, target_m, waypoint_nodes))
        return [1, 2, 3, 0]                    # 0 -> 2 -> 3 -> 1 -> 0

    monkeypatch.setattr(assistant, "plan_loop", fake_loop)
    res = ask(setup, distance_km=0.3, loop=True, pass_by=["park"])
    assert calls == [(0, 300.0, [1])]
    assert res.route.geometry.coordinates[-1] == [ORIGIN["lon"], ORIGIN["lat"]]
    assert res.route.distance_m == pytest.approx(320, abs=1)
    conditions = by_name(res)
    assert conditions["Circular"].met and conditions["Distancia de 0,3 km (±10 %)"].met
    assert conditions["Pasar por: parque"].met


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
