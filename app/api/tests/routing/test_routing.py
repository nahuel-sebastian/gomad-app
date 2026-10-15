import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from routing.graph import (RouteNotFound, bounded_distances, edge_costs, load_graph, nearest_node,
                           shortest_path, summarize)


@pytest.fixture
def graph(tmp_path):
    """   0 --(100 m, avenida)-- 1
          |                      |
       (80 m, parque)        (80 m, parque)
          |                      |
          2 --(60 m, parque)---- 3        4 -- 5 (aislados)
    Directa 0->1 = 100 m por la avenida; saludable 0->2->3->1 = 220 m por parque.
    Coordenadas con distancias geometricas menores que las longitudes (heuristica de A* admisible)."""
    nodes = pd.DataFrame({"node": range(6), "osm_id": range(6),
                          "lon": [-3.7300, -3.7289, -3.7300, -3.7289, -3.7000, -3.6990],   # 0,0011 grados ~ 93 m
                          "lat": [40.3050, 40.3050, 40.3043, 40.3043, 40.3100, 40.3100]})  # 0,0007 grados ~ 78 m
    rows = [(0, 1, 100, 1.0, 0.0, False), (0, 2, 80, 0.0, 1.0, True), (2, 3, 60, 0.0, 1.0, False),
            (3, 1, 80, 0.0, 1.0, False), (4, 5, 85, 0.0, np.nan, False)]
    edges = pd.DataFrame(rows, columns=["u", "v", "length_m", "traffic", "green_pct", "near_fountain"])
    edges["highway"] = "footway"
    edges["near_bench"] = False
    edges["near_aed"] = False
    edges["geom"] = [LineString([(nodes.lon[u], nodes.lat[u]), (nodes.lon[v], nodes.lat[v])]).wkb
                     for u, v in zip(edges.u, edges.v)]
    nodes.to_parquet(tmp_path / "nodes.parquet")
    edges.to_parquet(tmp_path / "edges.parquet")
    return load_graph(tmp_path)


WEIGHTS = {"traffic": 1.0, "green": 0.5, "fountains": 0.2}


def test_costs_always_positive(graph):
    for w in (WEIGHTS, {"traffic": 0, "green": 1, "fountains": 1}, {"traffic": 1, "green": 1, "fountains": 1}):
        c = edge_costs(graph, w, floor=0.5)
        assert (c > 0).all() and (c >= 0.5 * graph.length - 1e-9).all()


@pytest.mark.parametrize("algorithm", ["dijkstra", "astar"])
def test_direct_and_healthy(graph, algorithm):
    direct = shortest_path(graph, 0, 1, graph.length, algorithm)
    healthy = shortest_path(graph, 0, 1, edge_costs(graph, WEIGHTS, 0.5), algorithm)
    sd, sh = summarize(graph, direct), summarize(graph, healthy)
    assert sd["distance_m"] == pytest.approx(100)
    assert sh["distance_m"] == pytest.approx(220)
    assert sh["distance_m"] >= sd["distance_m"]          # la saludable nunca es mas corta
    assert sh["green_pct"] == pytest.approx(100) and sd["traffic_m"] == pytest.approx(100)
    assert sh["fountains"] == 1


def test_unreachable_raises(graph):
    with pytest.raises(RouteNotFound):
        shortest_path(graph, 0, 4, graph.length)


def test_nearest_node(graph):
    assert nearest_node(graph, -3.72999, 40.30501) == 0


def test_nearest_node_too_far(graph):
    with pytest.raises(RouteNotFound):
        nearest_node(graph, -3.60, 40.40)


def test_bounded_dijkstra(graph):
    d = bounded_distances(graph, 0, limit_m=150)
    assert d[1] == pytest.approx(100) and d[2] == pytest.approx(80) and d[3] == pytest.approx(140)
    assert np.isinf(d[4])


def test_green_without_data_is_none(graph):
    assert summarize(graph, [4])["green_pct"] is None
