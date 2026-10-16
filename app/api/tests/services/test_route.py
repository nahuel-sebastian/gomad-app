import pytest

import schemas as s
from mini_data import ORIGIN, build_mini_data
from repository import Repository
from routing.store import GraphStore
from services.route import path_coordinates, route

PARK = {"lat": 40.3050, "lon": -3.7289}         # nodo 1


@pytest.fixture
def setup(tmp_path):
    base = build_mini_data(tmp_path / "data", graph=True)
    return Repository(base), GraphStore.load(base / "graph")


def test_direct_and_healthy_on_graph(setup):
    repo, graphs = setup
    res = route(s.RouteRequest(origin=ORIGIN, destination=PARK), repo, graphs)
    assert res.direct.distance_m == pytest.approx(100) and res.healthy.distance_m == pytest.approx(220)
    assert res.healthy.green_pct > res.direct.green_pct and res.direct.traffic_m == pytest.approx(100)
    assert res.healthy.geometry.coordinates[0] == [ORIGIN["lon"], ORIGIN["lat"]]
    assert res.healthy.geometry.coordinates[-1] == [PARK["lon"], PARK["lat"]]
    assert {(p.type, p.source) for p in res.healthy.pois} == {("fountain", "ay_fuentes"), ("bench", "osm")}
    assert res.direct.pois == []                                    # la fuente queda a 39 m de la avenida
    assert "1 fuente" in res.healthy.description and "1 banco" in res.healthy.description
    assert res.healthy.duration_min == pytest.approx(220 / 4500 * 60, abs=0.1)   # walk 4,5 km/h
    assert not res.healthy.approximate and any(d.source == "osm" for d in res.sources)


def test_path_coordinates_follow_direction(setup):
    _, graphs = setup
    g = graphs.zones[0].graph
    # de 1 a 0 por el parque: tramos 3-1, 2-3 y 0-2 recorridos al reves
    coords = path_coordinates(g, 1, [3, 2, 1])
    assert coords == [[-3.7289, 40.3050], [-3.7289, 40.3043], [-3.7300, 40.3043], [-3.7300, 40.3050]]


def test_senior_walks_slower(setup):
    repo, graphs = setup
    res = route(s.RouteRequest(origin=ORIGIN, destination=PARK, profile="senior"), repo, graphs)
    assert res.direct.duration_min == pytest.approx(100 / 3500 * 60, abs=0.1)


def test_route_outside_graph_is_approximate(setup):
    repo, graphs = setup
    far = {"lat": 40.9500, "lon": -3.4700}                          # Patones: sin grafo
    res = route(s.RouteRequest(origin=ORIGIN, destination=far), repo, graphs)
    assert res.direct.approximate and res.healthy.approximate
    assert res.direct.geometry.coordinates == [[ORIGIN["lon"], ORIGIN["lat"]], [far["lon"], far["lat"]]]
    assert res.direct.description.startswith("Línea recta de")
    assert any("línea recta" in w for w in res.warnings)
    assert res.sources and all(d.own_criterion for d in res.sources)            # RF-19: tambien la aproximada
    assert res.sources[0].label == "Distancia aproximada: línea recta (criterio propio)"


def test_geometry_without_repeated_points(setup):
    repo, graphs = setup
    res = route(s.RouteRequest(origin=ORIGIN, destination=PARK), repo, graphs)
    for variant in (res.direct, res.healthy):
        c = variant.geometry.coordinates
        assert all(a != b for a, b in zip(c, c[1:]))
