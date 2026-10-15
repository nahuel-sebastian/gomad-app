"""Grafos peatonales en memoria, cargados una vez al arrancar (lifespan): uno por zona en data/graph/<zona>/."""
from dataclasses import dataclass

import numpy as np

from routing.graph import Graph, load_graph, nearest_nodes


@dataclass
class Zone:
    name: str
    graph: Graph
    bbox: tuple                # (lon_min, lat_min, lon_max, lat_max) de sus nodos


class GraphStore:
    def __init__(self, zones=()):
        # la zona mas pequena primero: mas rapida (Getafe antes que la caja de la capital)
        self.zones = sorted(zones, key=lambda z: len(z.graph.lon))

    @classmethod
    def load(cls, directory):
        zones = []
        for d in sorted(directory.glob("*")) if directory.exists() else []:
            if (d / "nodes.parquet").exists() and (d / "edges.parquet").exists():
                g = load_graph(d)
                zones.append(Zone(d.name, g, (g.lon.min(), g.lat.min(), g.lon.max(), g.lat.max())))
        return cls(zones)

    def locate(self, points, max_m):
        lons = np.array([p[0] for p in points], dtype=float)
        lats = np.array([p[1] for p in points], dtype=float)
        for z in self.zones:
            x0, y0, x1, y1 = z.bbox
            if not ((lons >= x0) & (lons <= x1) & (lats >= y0) & (lats <= y1)).all():
                continue
            nodes, dist = nearest_nodes(z.graph, lons, lats, max_m)
            if (nodes >= 0).all():
                return z, nodes, dist
        return None
