#!/usr/bin/env python3
"""Mide la red peatonal de OSM para un municipio: nodos, tramos, tiempo y memoria.

Usa pyrosm si esta instalado; si no (pyrosm no compila en Python 3.12, Task 8),
el respaldo con pyosmium de Task 20 paso 3b: un tramo por par de nodos consecutivos.

Uso: python scripts/probe_pyrosm.py 28065
"""
import json
import math
import os
import pathlib
import resource
import sys
import time

import geopandas as gpd
from shapely.geometry import LineString

ROOT = pathlib.Path(__file__).resolve().parent.parent      # app/ingest
DATA_DIR = pathlib.Path(os.environ.get("GOMAD_DATA_DIR", ROOT.parent / "data"))
PBF = DATA_DIR / "raw" / "osm" / "madrid-latest.osm.pbf"

# valores de highway que se recorren a pie (respaldo pyosmium, Task 20 paso 3b)
WALKING_HIGHWAYS = {
    "footway", "path", "pedestrian", "living_street", "residential", "service", "steps", "track",
    "unclassified", "tertiary", "secondary", "primary", "cycleway",
    "tertiary_link", "secondary_link", "primary_link",
}
FOOT_ALLOWED = {"yes", "designated", "permissive"}


def municipality_bbox(ine_code):
    muni = gpd.read_file(DATA_DIR / "raw" / "municipios" / "municipios.geojson")
    muni = muni.set_crs(25830, allow_override=True).to_crs(4326)
    row = muni[("28" + muni["CDMUNICIPIO"].astype(str).str.zfill(3)) == ine_code]
    if row.empty:
        sys.exit(f"Municipio {ine_code} no encontrado")
    return [float(v) for v in row.total_bounds]


def haversine_m(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(a))


def network_pyrosm(bbox):
    from pyrosm import OSM
    osm = OSM(str(PBF), bounding_box=bbox)
    return osm.get_network(network_type="walking", nodes=True)


def network_osmium(bbox):
    import osmium

    minx, miny, maxx, maxy = bbox

    def inside(loc):
        return minx <= loc.lon <= maxx and miny <= loc.lat <= maxy

    class WalkingWays(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.nodes = {}
            self.rows = []

        def way(self, w):
            tags = w.tags
            highway = tags.get("highway")
            if highway not in WALKING_HIGHWAYS:
                return
            foot = tags.get("foot")
            if foot == "no":
                return
            if tags.get("access") in ("no", "private") and foot not in FOOT_ALLOWED:
                return
            refs = [(n.ref, n.location) for n in w.nodes if n.location.valid()]
            # el tramo entra si alguno de sus extremos cae en la caja (como bounding_box de pyrosm)
            for (u, lu), (v, lv) in zip(refs, refs[1:]):
                if u == v or not (inside(lu) or inside(lv)):
                    continue
                self.nodes[u] = (lu.lon, lu.lat)
                self.nodes[v] = (lv.lon, lv.lat)
                self.rows.append({
                    "u": u, "v": v, "id": w.id, "highway": highway,
                    "length": haversine_m(lu.lon, lu.lat, lv.lon, lv.lat),
                    "geometry": LineString([(lu.lon, lu.lat), (lv.lon, lv.lat)]),
                })

    handler = WalkingWays()
    handler.apply_file(str(PBF), locations=True)
    nodes = gpd.GeoDataFrame(
        {"id": list(handler.nodes), "lon": [c[0] for c in handler.nodes.values()],
         "lat": [c[1] for c in handler.nodes.values()]},
        geometry=gpd.points_from_xy([c[0] for c in handler.nodes.values()],
                                    [c[1] for c in handler.nodes.values()]), crs=4326)
    edges = gpd.GeoDataFrame(handler.rows, geometry="geometry", crs=4326)
    return nodes, edges


def main(ine_code):
    try:
        import pyrosm  # noqa: F401
        engine, network = "pyrosm", network_pyrosm
    except ImportError:
        engine, network = "osmium", network_osmium
    bbox = municipality_bbox(ine_code)
    t0 = time.perf_counter()
    nodes, edges = network(bbox)
    seconds = time.perf_counter() - t0
    mem_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(json.dumps({"municipality": ine_code, "engine": engine, "bbox": bbox, "nodes": len(nodes),
                      "edges": len(edges), "seconds": round(seconds, 1), "max_memory_mb": round(mem_mb),
                      "edge_columns": list(edges.columns)[:40],
                      "highway": edges["highway"].value_counts().head(15).to_dict()}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "28065")
