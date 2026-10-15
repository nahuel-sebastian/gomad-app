import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

from routing.graph import (RouteNotFound, bounded_distances, edge_costs, load_graph, nearest_node, nearest_nodes,
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


def test_astar_matches_dijkstra_when_lengths_are_shorter_than_local_xy(tmp_path):
    # en los datos reales length_m (UTM) es hasta un 0,3 % menor que la distancia de la proyeccion local
    # (aqui 1 %, para que salga en un grafo pequeno):
    # una heuristica no consistente hacia que igraph 0.11.6 diera segfault (Getafe, Task 22)
    rng = np.random.default_rng(7)
    side = 30
    ids = np.arange(side * side).reshape(side, side)
    lon = (-3.73 + 0.0005 * (ids % side)).ravel() + rng.uniform(-1e-4, 1e-4, ids.size)
    lat = (40.30 + 0.0004 * (ids // side)).ravel() + rng.uniform(-1e-4, 1e-4, ids.size)
    pairs = [(ids[i, j], ids[i, j + 1]) for i in range(side) for j in range(side - 1)]
    pairs += [(ids[i, j], ids[i + 1, j]) for i in range(side - 1) for j in range(side)]
    u, v = np.array(pairs).T.reshape(2, -1)
    cos0 = np.cos(np.radians(lat.mean()))
    straight = np.hypot((lon[u] - lon[v]) * 111_320 * cos0, (lat[u] - lat[v]) * 111_320)
    edges = pd.DataFrame({"u": u, "v": v, "length_m": straight * 0.99, "traffic": rng.uniform(0, 1, len(u)),
                          "green_pct": rng.uniform(0, 1, len(u)), "near_fountain": rng.uniform(0, 1, len(u)) < 0.1,
                          "highway": "footway", "near_bench": False, "near_aed": False})
    edges["geom"] = [LineString([(lon[a], lat[a]), (lon[b], lat[b])]).wkb for a, b in zip(u, v)]
    pd.DataFrame({"node": ids.ravel(), "osm_id": ids.ravel(), "lon": lon, "lat": lat}).to_parquet(
        tmp_path / "nodes.parquet")
    edges.to_parquet(tmp_path / "edges.parquet")
    g = load_graph(tmp_path)
    for costs in (g.length, edge_costs(g, WEIGHTS, 0.5)):
        for a, b in rng.integers(0, ids.size, (40, 2)):
            d = costs[shortest_path(g, int(a), int(b), costs, "dijkstra")].sum()
            s = costs[shortest_path(g, int(a), int(b), costs, "astar")].sum()
            assert s == pytest.approx(d)


def _write_graph(path, lon, lat, rows, extra=None):
    nodes = pd.DataFrame({"node": range(len(lon)), "osm_id": range(len(lon)), "lon": lon, "lat": lat})
    edges = pd.DataFrame(rows, columns=["u", "v", "length_m"])
    edges["traffic"], edges["green_pct"], edges["highway"] = 0.0, np.nan, "footway"
    edges["near_fountain"] = edges["near_bench"] = edges["near_aed"] = False
    for column, values in (extra or {}).items():
        edges[column] = values
    edges["geom"] = [LineString([(lon[u], lat[u]), (lon[v], lat[v])]).wkb for u, v, _ in rows]
    nodes.to_parquet(path / "nodes.parquet")
    edges.to_parquet(path / "edges.parquet")
    return load_graph(path)


def test_one_fountain_counts_once(tmp_path):
    # una fuente marca todos los tramos a menos de 25 m: se cuenta una vez por id
    lon, lat = [-3.7300, -3.7299, -3.7298, -3.7297], [40.305] * 4
    g = _write_graph(tmp_path, lon, lat, [(0, 1, 9), (1, 2, 9), (2, 3, 9)],
                     {"near_fountain": [True, True, True], "fountain_id": ["f1", "f1", "f2"],
                      "bench_id": [None, None, None], "aed_id": [None, None, None]})
    assert summarize(g, [0, 1, 2])["fountains"] == 2


def test_duplicate_edges_are_not_summed(tmp_path):
    # vias OSM superpuestas dan el mismo par (u, v) dos veces: la matriz no debe sumar las longitudes
    g = _write_graph(tmp_path, [-3.7300, -3.7298], [40.305, 40.305], [(0, 1, 17.5), (1, 0, 17.5)])
    assert bounded_distances(g, 0, 100)[1] == pytest.approx(17.5)


def test_nearest_node_skips_small_fragments(tmp_path):
    # un trozo suelto de red junto a la red principal no debe atrapar el origen (RouteNotFound en la demo)
    lon = [-3.7300, -3.7290, -3.7280, -3.7300, -3.7299]
    lat = [40.3050, 40.3050, 40.3050, 40.3054, 40.3054]          # 3 y 4 a ~45 m de 0, sin conexion
    g = _write_graph(tmp_path, lon, lat, [(0, 1, 90), (1, 2, 90), (3, 4, 9)])
    assert nearest_node(g, -3.7300, 40.3054) == 0


def test_nearest_nodes_vectorized(graph):
    nodes, dist = nearest_nodes(graph, [-3.7300, -3.7289, -3.7000], [40.3050, 40.30505, 40.3100], max_m=300)
    assert nodes.tolist() == [0, 1, -1]                # el tercero cae en la componente aislada: fuera
    assert dist[0] == pytest.approx(0) and dist[1] == pytest.approx(5.6, abs=0.5)
