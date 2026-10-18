"""Ruta por distancia objetivo (RF-22, fila 5) sobre una rejilla sintetica."""
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import LineString

import settings
from routing.graph import RouteNotFound, edge_costs, load_graph

from routing.loop import Subgraph

N = 21                       # rejilla N x N, tramos de 100 m
STEP_LAT = 100 / 111_320
STEP_LON = 100 / (111_320 * np.cos(np.radians(40.3)))
LON0, LAT0 = -3.75, 40.30
ISOLATED = (N * N, N * N + 1)    # dos nodos sueltos (otra componente)
TRAFFIC_EDGE = ((5, 7), (5, 8))  # (fila, columna) de sus extremos


def node(r, c):
    return r * N + c


@pytest.fixture(scope="module")
def grid(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("grid")
    lon = [LON0 + c * STEP_LON for r in range(N) for c in range(N)] + [-3.60, -3.60 + STEP_LON]
    lat = [LAT0 + r * STEP_LAT for r in range(N) for c in range(N)] + [40.40, 40.40]
    nodes = pd.DataFrame({"node": range(len(lon)), "osm_id": range(len(lon)), "lon": lon, "lat": lat})
    rows = []
    for r in range(N):
        for c in range(N):
            if c + 1 < N:   # horizontal
                traffic = 1.0 if ((r, c), (r, c + 1)) == TRAFFIC_EDGE else 0.0
                rows.append((node(r, c), node(r, c + 1), 100.0, traffic, 0.0, False))
            if r + 1 < N:   # vertical; la columna central es parque con alguna fuente
                green = 1.0 if c == N // 2 else 0.0
                rows.append((node(r, c), node(r + 1, c), 100.0, 0.0, green, c == N // 2 and r % 5 == 0))
    rows.append((*ISOLATED, 100.0, 0.0, 0.0, False))
    edges = pd.DataFrame(rows, columns=["u", "v", "length_m", "traffic", "green_pct", "near_fountain"])
    edges["highway"] = "footway"
    edges["near_bench"] = False
    edges["near_aed"] = False
    edges["geom"] = [LineString([(lon[u], lat[u]), (lon[v], lat[v])]).wkb for u, v in zip(edges.u, edges.v)]
    nodes.to_parquet(tmp / "nodes.parquet")
    edges.to_parquet(tmp / "edges.parquet")
    return load_graph(tmp)


CENTER = node(N // 2, N // 2)
HEALTHY = {"traffic": 0.5, "green": 0.5, "fountains": 0.2}


def chain_nodes(g, start, edges):
    """Nodos recorridos por una lista de tramos contiguos desde start; falla si no son contiguos."""
    seq = [start]
    for e in edges:
        a, b = int(g.u[e]), int(g.v[e])
        assert seq[-1] in (a, b), "tramos no contiguos"
        seq.append(b if seq[-1] == a else a)
    return seq


def test_loop_config():
    cfg = settings.load("routing")["loop"]
    assert cfg["tolerance"] == 0.10
    assert cfg["own_criterion"] is True


def test_subgraph_radius(grid):
    sub = Subgraph(grid, CENTER, 300, edge_costs(grid, HEALTHY, 0.5))
    assert sub.contains(node(10, 13)) and not sub.contains(node(10, 14))
    assert sub.length_from(CENTER)[node(10, 13)] == pytest.approx(300)


def test_subgraph_path_prefers_healthy(grid):
    a, b = node(*TRAFFIC_EDGE[0]), node(*TRAFFIC_EDGE[1])
    sub = Subgraph(grid, a, 1000, edge_costs(grid, {"traffic": 3.0}, 0.5))
    path = sub.path(a, b, set(), 3.0)
    assert chain_nodes(grid, a, path)[-1] == b
    assert grid.length[path].sum() > 100


def test_subgraph_path_penalizes_used(grid):
    a, b = node(10, 10), node(10, 14)
    sub = Subgraph(grid, a, 2000, edge_costs(grid, HEALTHY, 0.5))
    first = sub.path(a, b, set(), 3.0)
    second = sub.path(b, a, set(first), 3.0)
    assert chain_nodes(grid, b, second)[-1] == a
    assert not set(first) & set(second)


def test_subgraph_path_unreachable(grid):
    sub = Subgraph(grid, CENTER, 5000, edge_costs(grid, HEALTHY, 0.5))
    with pytest.raises(RouteNotFound):
        sub.path(CENTER, ISOLATED[0], set(), 3.0)
