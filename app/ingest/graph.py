"""OSM -> app/data/graph/<zona>/{nodes,edges}.parquet con factores por tramo (arquitectura §3.4).

Lectura con pyosmium (respaldo de Task 20 paso 3b: pyrosm no compila en Python 3.12, Task 8).
Un tramo por par de nodos consecutivos de cada via peatonal.

Uso: python -m graph 28065            # Getafe -> data/graph/getafe/
     python -m graph all              # toda la Comunidad -> data/graph/region/ (sabado)
"""
import math
import sys
import time

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
import yaml
from shapely.geometry import LineString, Point, Polygon

from common import CLEAN, CONFIG_DIR, DATA_DIR, RAW, assign_municipality, municipalities, write

PBF = RAW / "osm" / "madrid-latest.osm.pbf"
OSM_POI = {("amenity", "bench"): "bench", ("amenity", "drinking_water"): "fountain",
           ("amenity", "waste_basket"): "bin", ("leisure", "dog_park"): "dog_area",
           ("leisure", "playground"): "playground"}
ZONE_NAMES = {"28065": "getafe", "28079": "madrid", "28131": "san_lorenzo"}
# valores de highway que se recorren a pie (Task 20 paso 3b; los *_link los vio Task 8 en Getafe)
WALKING_HIGHWAYS = {
    "footway", "path", "pedestrian", "living_street", "residential", "service", "steps", "track",
    "unclassified", "tertiary", "secondary", "primary", "cycleway",
    "tertiary_link", "secondary_link", "primary_link",
}
FOOT_ALLOWED = {"yes", "designated", "permissive"}


def index_nodes(nodes, edges):
    used = pd.unique(pd.concat([edges["u"], edges["v"]]))
    n = nodes[nodes["id"].isin(used)].reset_index(drop=True)
    n["node"] = np.arange(len(n))
    mapping = dict(zip(n["id"], n["node"]))
    e = edges.assign(u=edges["u"].map(mapping), v=edges["v"].map(mapping)).dropna(subset=["u", "v"])
    e[["u", "v"]] = e[["u", "v"]].astype(np.int64)
    return n.rename(columns={"id": "osm_id"})[["node", "osm_id", "lon", "lat"]], e


def edge_factors(edges, green, poi, config, has_green, covered=None):
    """Factores por tramo. covered: poligonos de los municipios con datos de verde (VPLA); fuera, NaN."""
    e = edges.to_crs(25830).reset_index(drop=True)
    e["length_m"] = e.length
    e["traffic"] = (e["highway"].astype(str).map(config["traffic_by_highway"])
                    .fillna(config["default_traffic"]).astype(float))
    if has_green and len(green):
        e["green_pct"] = (_green_length(e, green.to_crs(25830)) / e["length_m"]).clip(0, 1)
        if covered is not None:
            # la caja de un municipio sin VPLA (Madrid capital) trae zonas de los vecinos: sin dato, no 0
            middle = gpd.GeoDataFrame(geometry=e.geometry.interpolate(0.5, normalized=True), crs=25830)
            inside = gpd.sjoin(middle, covered[["geometry"]].to_crs(25830), how="inner", predicate="within")
            e.loc[~e.index.isin(inside.index), "green_pct"] = np.nan
    else:
        e["green_pct"] = np.nan
    p = poi.to_crs(25830)
    if "working" in p:
        # CLAUDE.md §6.1: la ruta solo cuenta working IS NOT FALSE (las fuentes cerradas se muestran, no cuentan)
        p = p[~p["working"].eq(False).fillna(False).astype(bool)]
    ids = p["id"].astype(str) if "id" in p else pd.Series(p.index.astype(str), index=p.index)
    for kind, column, id_column in (("fountain", "near_fountain", "fountain_id"), ("bench", "near_bench", "bench_id"),
                                    ("aed", "near_aed", "aed_id")):
        pts = p[p["type"] == kind]
        e[id_column] = None
        if len(pts):
            pts = gpd.GeoDataFrame({"poi_id": ids[pts.index].to_numpy()}, geometry=pts.geometry.to_numpy(),
                                   crs=25830)
            near = gpd.sjoin_nearest(e[["geometry"]], pts, how="inner",
                                     max_distance=config["poi_radius_m"], distance_col="d")
            # el mas cercano de cada tramo: su id permite contar cada punto una vez en la ruta
            nearest = near.sort_values("d").groupby(level=0)["poi_id"].first()
            e.loc[nearest.index, id_column] = nearest.to_numpy()
        e[column] = e[id_column].notna().to_numpy()
    return e.to_crs(4326)


def _green_length(e, zones):
    """Metros de cada tramo dentro de zona verde, con indice espacial.

    Cruzar cada tramo con la union de todas las zonas tardaba > 25 min en la caja de Madrid capital.
    Solo se intersecan los pares tramo-zona que se tocan; si un tramo toca varias zonas (VPLA tiene
    poligonos solapados) se unen sus trozos antes de medir, para no contar dos veces.
    """
    zones = zones[["geometry"]].reset_index(drop=True)
    pairs = gpd.sjoin(e[["geometry"]], zones, how="inner", predicate="intersects")
    result = pd.Series(0.0, index=e.index)
    if pairs.empty:
        return result
    pieces = shapely.intersection(e.geometry.loc[pairs.index].to_numpy(),
                                  zones.geometry.loc[pairs["index_right"]].to_numpy())
    pieces = pd.Series(pieces, index=pairs.index)
    repeated = pieces.index.duplicated(keep=False)
    result.loc[pieces.index[~repeated]] = shapely.length(pieces[~repeated].to_numpy())
    if repeated.any():
        merged = pieces[repeated].groupby(level=0).agg(lambda parts: shapely.union_all(parts.to_numpy()))
        result.loc[merged.index] = shapely.length(merged.to_numpy())
    return result


def _haversine_m(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(a))


def read_osm(pbf, bbox):
    """Una sola lectura del extracto: red peatonal dentro de la caja y mobiliario de toda la Comunidad.

    Devuelve (nodes, edges, osm): nodes con id/lon/lat, edges con u/v/highway/geometry y osm con
    los elementos de mobiliario (osm_type, osm_id, key, value, coords).
    """
    import osmium

    minx, miny, maxx, maxy = bbox if bbox else (-180.0, -90.0, 180.0, 90.0)

    def inside(loc):
        return minx <= loc.lon <= maxx and miny <= loc.lat <= maxy

    def poi_tag(tags):
        for key, value in OSM_POI:
            if tags.get(key) == value:
                return key, value
        return None

    class Reader(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.nodes = {}
            self.rows = []
            self.pois = []

        def node(self, n):
            tag = poi_tag(n.tags)
            if tag and n.location.valid():
                self.pois.append(("node", n.id, *tag, [(n.location.lon, n.location.lat)]))

        def way(self, w):
            tags = w.tags
            tag = poi_tag(tags)
            if tag:
                coords = [(n.location.lon, n.location.lat) for n in w.nodes if n.location.valid()]
                if coords:
                    self.pois.append(("way", w.id, *tag, coords))
            highway = tags.get("highway")
            if highway not in WALKING_HIGHWAYS:
                return
            foot = tags.get("foot")
            if foot == "no" or (tags.get("access") in ("no", "private") and foot not in FOOT_ALLOWED):
                return
            refs = [(n.ref, n.location) for n in w.nodes if n.location.valid()]
            # el tramo entra si alguno de sus extremos cae en la caja (como bounding_box de pyrosm)
            for (u, lu), (v, lv) in zip(refs, refs[1:]):
                if u == v or not (inside(lu) or inside(lv)):
                    continue
                self.nodes[u] = (lu.lon, lu.lat)
                self.nodes[v] = (lv.lon, lv.lat)
                self.rows.append((u, v, highway, LineString([(lu.lon, lu.lat), (lv.lon, lv.lat)])))

    r = Reader()
    r.apply_file(str(pbf), locations=True)
    nodes = pd.DataFrame({"id": list(r.nodes), "lon": [c[0] for c in r.nodes.values()],
                          "lat": [c[1] for c in r.nodes.values()]})
    edges = gpd.GeoDataFrame(pd.DataFrame(r.rows, columns=["u", "v", "highway", "geometry"]),
                             geometry="geometry", crs=4326)
    osm = pd.DataFrame(r.pois, columns=["osm_type", "osm_id", "key", "value", "coords"])
    return nodes, edges, osm


def _poi_point(coords):
    if len(coords) == 1:
        return Point(coords[0])
    if len(coords) >= 4 and coords[0] == coords[-1]:
        return Polygon(coords).representative_point()
    return LineString(coords).interpolate(0.5, normalized=True)


def osm_pois(osm):
    """Mobiliario de OSM con el esquema de clean/poi.parquet (status y working sin dato)."""
    if osm is None or osm.empty:
        return gpd.GeoDataFrame({"id": [], "type": [], "source": [], "ine_code": [], "status": [],
                                 "working": pd.array([], dtype="boolean")}, geometry=[], crs=4326)
    kinds = [OSM_POI[(k, v)] for k, v in zip(osm["key"], osm["value"])]
    pois = gpd.GeoDataFrame({"id": "osm:" + osm["osm_type"] + "/" + osm["osm_id"].astype(str),
                             "type": kinds, "source": "osm", "ine_code": None, "status": None,
                             "working": pd.array([pd.NA] * len(osm), dtype="boolean")},
                            geometry=[_poi_point(c) for c in osm["coords"]], crs=4326)
    return pois[["id", "type", "source", "ine_code", "status", "working", "geometry"]]


def build_graph(pbf, bbox, out_dir, config):
    t0 = time.perf_counter()
    nodes, edges, osm = read_osm(pbf, bbox)
    edges = edges[edges["u"] != edges["v"]]
    # mobiliario OSM -> poi.parquet (una sola lectura del extracto; toda la Comunidad)
    region = municipalities().union_all()
    new_poi = osm_pois(osm)
    new_poi = assign_municipality(new_poi[new_poi.intersects(region)].copy())
    old_poi = gpd.read_parquet(CLEAN / "poi.parquet")
    poi = gpd.GeoDataFrame(pd.concat([old_poi[old_poi["source"] != "osm"], new_poi], ignore_index=True),
                           geometry="geometry", crs=4326)
    poi["working"] = poi["working"].astype("boolean")
    write(poi, "poi")
    green = gpd.read_parquet(CLEAN / "green.parquet")
    covered = municipalities()[municipalities()["ine_code"].isin(set(green["ine_code"].dropna()))]
    if bbox:
        green = green.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
        poi = poi.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]
    f = edge_factors(edges, green, poi, config, has_green=len(green) > 0, covered=covered)
    n, e = index_nodes(nodes, f)
    out_dir.mkdir(parents=True, exist_ok=True)
    n.to_parquet(out_dir / "nodes.parquet", index=False)
    e = e.assign(geom=e.geometry.to_wkb())
    cols = ["u", "v", "length_m", "highway", "traffic", "green_pct", "near_fountain", "near_bench", "near_aed",
            "fountain_id", "bench_id", "aed_id", "geom"]
    pd.DataFrame(e[cols]).to_parquet(out_dir / "edges.parquet", index=False)
    return {"nodes": len(n), "edges": len(e), "osm_poi": len(new_poi),
            "seconds": round(time.perf_counter() - t0, 1)}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "28065"
    config = yaml.safe_load((CONFIG_DIR / "routing.yaml").read_text(encoding="utf-8"))
    if target == "all":
        print(build_graph(PBF, None, DATA_DIR / "graph" / "region", config))
    else:
        row = municipalities()[municipalities()["ine_code"] == target]
        if row.empty:
            sys.exit(f"Municipio {target} no encontrado")
        out = DATA_DIR / "graph" / ZONE_NAMES.get(target, target)
        print(build_graph(PBF, [float(v) for v in row.total_bounds], out, config))
