"""Grafo peatonal en memoria (arquitectura §4.4). Coste por peticion, vectorizado; nunca <= 0."""
import math
from dataclasses import dataclass, field

import igraph as ig
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree
from shapely import wkb

M_PER_DEG_LAT = 111_320.0


class RouteNotFound(Exception):
    pass


@dataclass
class Graph:
    lon: np.ndarray
    lat: np.ndarray
    u: np.ndarray
    v: np.ndarray
    length: np.ndarray
    traffic: np.ndarray
    green: np.ndarray
    near_fountain: np.ndarray
    near_bench: np.ndarray
    near_aed: np.ndarray
    geom_wkb: list
    ig: ig.Graph
    csr: csr_matrix
    tree: cKDTree
    cos_lat0: float
    tree_nodes: np.ndarray | None = None                  # nodo de cada punto del KD-tree (componente principal)
    fountain_id: np.ndarray | None = None                 # id del punto mas cercano por tramo (None si no hay)
    bench_id: np.ndarray | None = None
    aed_id: np.ndarray | None = None
    _geom: dict = field(default_factory=dict)

    def geom(self, i):
        if i not in self._geom:
            self._geom[i] = wkb.loads(self.geom_wkb[i])
        return self._geom[i]


def _xy(lon, lat, cos_lat0):
    # proyeccion local equirectangular: suficiente para distancias de pocos km
    return np.column_stack([np.asarray(lon) * M_PER_DEG_LAT * cos_lat0, np.asarray(lat) * M_PER_DEG_LAT])


def load_graph(directory):
    n = pd.read_parquet(directory / "nodes.parquet").sort_values("node")
    e = pd.read_parquet(directory / "edges.parquet")
    cos_lat0 = math.cos(math.radians(float(n["lat"].mean())))
    u, v = e["u"].to_numpy(np.int64), e["v"].to_numpy(np.int64)
    length = e["length_m"].to_numpy(float)
    count = len(n)
    graph_ig = ig.Graph(n=count, edges=np.column_stack([u, v]).tolist(), directed=False)
    # vias OSM superpuestas repiten el par (u, v): csr_matrix sumaria las longitudes, se queda la menor
    pairs = (pd.DataFrame({"a": np.minimum(u, v), "b": np.maximum(u, v), "length": length})
             .groupby(["a", "b"], as_index=False)["length"].min())
    a, b, w = pairs["a"].to_numpy(), pairs["b"].to_numpy(), pairs["length"].to_numpy()
    csr = csr_matrix((np.concatenate([w, w]), (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(count, count))
    # el KD-tree solo tiene la componente principal: un trozo suelto de red no atrapa el origen
    _, labels = connected_components(csr, directed=False)
    tree_nodes = np.flatnonzero(labels == np.bincount(labels).argmax()) if count else np.arange(0)
    xy = _xy(n["lon"].to_numpy(float), n["lat"].to_numpy(float), cos_lat0)
    ids = {k: e[f"{k}_id"].to_numpy(object) if f"{k}_id" in e else None for k in ("fountain", "bench", "aed")}
    return Graph(lon=n["lon"].to_numpy(float), lat=n["lat"].to_numpy(float), u=u, v=v, length=length,
                 traffic=e["traffic"].to_numpy(float), green=e["green_pct"].to_numpy(float),
                 near_fountain=e["near_fountain"].to_numpy(bool), near_bench=e["near_bench"].to_numpy(bool),
                 near_aed=e["near_aed"].to_numpy(bool), geom_wkb=list(e["geom"]), ig=graph_ig, csr=csr,
                 tree=cKDTree(xy[tree_nodes]), cos_lat0=cos_lat0, tree_nodes=tree_nodes,
                 fountain_id=ids["fountain"], bench_id=ids["bench"], aed_id=ids["aed"])


def nearest_node(g, lon, lat, max_m=300):
    d, i = g.tree.query(_xy([lon], [lat], g.cos_lat0)[0])
    if d > max_m:
        raise RouteNotFound(f"No hay red peatonal a menos de {max_m} m")
    return int(g.tree_nodes[i]) if g.tree_nodes is not None else int(i)


def nearest_nodes(g, lons, lats, max_m=300):
    """Nodo mas cercano (componente principal) de cada punto y su distancia en metros; -1 si esta a mas de max_m."""
    d, i = g.tree.query(_xy(lons, lats, g.cos_lat0))
    nodes = g.tree_nodes[i] if g.tree_nodes is not None else i
    return np.where(d <= max_m, nodes, -1).astype(np.int64), d


def edge_costs(g, weights, floor):
    green = np.nan_to_num(g.green, nan=0.0)
    factor = (1 + weights.get("traffic", 0) * g.traffic - weights.get("green", 0) * green
              - weights.get("fountains", 0) * g.near_fountain)
    return g.length * np.maximum(factor, floor)


def shortest_path(g, origin, target, costs, algorithm="dijkstra"):
    if algorithm == "astar":
        xy = _xy(g.lon, g.lat, g.cos_lat0)
        # escala = min(coste / linea recta) de cada tramo: heuristica consistente por construccion.
        # length_m (UTM) puede ser algo menor que la distancia en _xy; una heuristica no consistente
        # da rutas peores y hace que igraph 0.11.6 falle (segfault) en el grafo de Getafe
        straight = np.hypot(*(xy[g.u] - xy[g.v]).T)
        positive = straight > 0
        scale = float(np.min(costs[positive] / straight[positive])) if positive.any() else 0.0
        heuristic = lambda graph, a, b: float(np.hypot(*(xy[a] - xy[b]))) * scale * (1 - 1e-9)  # margen de redondeo
        edges = g.ig.get_shortest_path_astar(origin, target, heuristics=heuristic, weights=costs, output="epath")
    else:
        edges = g.ig.get_shortest_path(origin, target, weights=costs, output="epath")
    if origin != target and not edges:
        raise RouteNotFound("Origen y destino no están conectados por la red peatonal")
    return list(edges)


def bounded_distances(g, origin, limit_m):
    return dijkstra(g.csr, directed=False, indices=origin, limit=limit_m)


def _count(ids, flags, idx):
    # cada punto una vez: un banco o una fuente marca todos los tramos a menos de poi_radius_m
    if ids is None:
        return int(flags[idx].sum())
    return len({x for x in ids[idx] if x is not None and x == x})


def summarize(g, edges, traffic_threshold=0.5):
    idx = np.asarray(edges, dtype=np.int64)
    length = g.length[idx]
    green = g.green[idx]
    has_data = ~np.isnan(green)
    green_pct = None if not has_data.any() else float(
        100 * (green[has_data] * length[has_data]).sum() / length[has_data].sum())
    return {"distance_m": float(length.sum()), "green_pct": green_pct,
            "traffic_m": float(length[g.traffic[idx] >= traffic_threshold].sum()),
            "fountains": _count(g.fountain_id, g.near_fountain, idx),
            "benches": _count(g.bench_id, g.near_bench, idx), "aeds": _count(g.aed_id, g.near_aed, idx)}
