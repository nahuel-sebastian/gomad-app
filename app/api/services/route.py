"""POST /route (arquitectura §4.4): directa y saludable en paralelo sobre el grafo de la zona.

Fuera de la red o desconectado: linea recta marcada approximate y aviso. Nunca un 500 por una ruta imposible."""
import math
from collections import Counter

import numpy as np
import shapely

import schemas as s
import settings
from engine.explanation import route_description
from repository import M_PER_DEG_LAT, haversine_m
from routing.graph import RouteNotFound, edge_costs, shortest_path, summarize
from services.common import data_source, walking_speed_kmh

POI_TYPES = set(s.RoutePoi.model_fields["type"].annotation.__args__)
NO_NETWORK = "No hay red peatonal cargada para este trayecto: se muestra la línea recta (aproximada)."
DISCONNECTED = "Origen y destino no están conectados por la red peatonal: se muestra la línea recta (aproximada)."


def path_coordinates(g, origin_node, edges):
    """[lon, lat] de la ruta en orden; cada tramo se gira segun el nodo por el que se entra (su geom va de u a v)."""
    coords = [[float(g.lon[origin_node]), float(g.lat[origin_node])]]
    current = origin_node
    for e in edges:
        line = list(g.geom(e).coords)
        if g.u[e] == current:
            current = int(g.v[e])
        else:
            line.reverse()
            current = int(g.u[e])
        coords.extend([float(x), float(y)] for x, y in line[1:])
    return coords


class PoiIndex:
    """Puntos de route_poi (solo working IS NOT FALSE) de la caja de unas rutas, con indice espacial en metros
    locales: una consulta a DuckDB por peticion y STRtree para no medir miles de bancos contra la linea."""

    def __init__(self, repo, coord_lists, radius_m):
        lons = np.array([c[0] for coords in coord_lists for c in coords])
        lats = np.array([c[1] for coords in coord_lists for c in coords])
        self.cos0 = math.cos(math.radians(float(lats.mean())))
        pad_lat = radius_m / M_PER_DEG_LAT
        pad_lon = pad_lat / self.cos0
        cols = repo.route_pois(lons.min() - pad_lon, lats.min() - pad_lat, lons.max() + pad_lon, lats.max() + pad_lat)
        keep = np.isin(cols["type"], list(POI_TYPES)) if len(cols) and len(cols["id"]) else np.zeros(0, dtype=bool)
        self.cols = {k: np.asarray(v)[keep] for k, v in cols.items()} if keep.any() else {}
        self.radius_m = radius_m
        self.tree = shapely.STRtree(shapely.points(self._xy(self.cols["lon"], self.cols["lat"]))) if self.cols else None

    def _xy(self, lons, lats):
        return np.column_stack([np.asarray(lons, dtype=float) * M_PER_DEG_LAT * self.cos0,
                                np.asarray(lats, dtype=float) * M_PER_DEG_LAT])

    def along(self, coords):
        if self.tree is None:
            return []
        xy = self._xy([c[0] for c in coords], [c[1] for c in coords])
        # un segmento por consulta: la caja de la linea entera de una ruta larga traeria miles de candidatos
        segments = shapely.linestrings(np.stack([xy[:-1], xy[1:]], axis=1))
        _, hits = self.tree.query(segments, predicate="dwithin", distance=self.radius_m)
        hits = sorted(set(hits.tolist()))
        c = self.cols
        return [s.RoutePoi(type=str(c["type"][i]), coordinate=s.Coordinate(lat=float(c["lat"][i]), lon=float(c["lon"][i])),
                           source=str(c["source"][i])) for i in hits]


def pois_along(repo, coords, radius_m):
    """Puntos de route_poi (solo working IS NOT FALSE) a menos de radius_m de la linea de la ruta."""
    return PoiIndex(repo, [coords], radius_m).along(coords)


def _straight(kind, origin, destination, speed):
    d = float(haversine_m(origin.lon, origin.lat, destination.lon, destination.lat))
    minutes = d / 1000 / speed * 60
    return s.RouteVariant(kind=kind, geometry=s.LineString(type="LineString", coordinates=[
        [origin.lon, origin.lat], [destination.lon, destination.lat]]), distance_m=round(d, 1),
        duration_min=round(minutes, 1), green_pct=None, traffic_m=0.0, pois=[], approximate=True,
        description=route_description(d, minutes, None, 0, {}, approximate=True))


def _coordinates(g, req, nodes, edges):
    coords = [[req.origin.lon, req.origin.lat], *path_coordinates(g, int(nodes[0]), edges),
              [req.destination.lon, req.destination.lat]]
    # sin puntos repetidos seguidos (origen = nodo, tramos que empiezan donde acaba el anterior)
    coords = [c for i, c in enumerate(coords) if i == 0 or c != coords[i - 1]]
    return coords if len(coords) >= 2 else coords * 2   # origen = destino: LineString de dos puntos iguales


def _variant(kind, g, edges, coords, snaps, routing, speed, pois_index):
    summary = summarize(g, edges, routing["traffic_display_threshold"])
    distance = summary["distance_m"] + float(snaps[0]) + float(snaps[1])
    minutes = distance / 1000 / speed * 60
    pois = pois_index.along(coords)
    green = summary["green_pct"]
    return s.RouteVariant(kind=kind, geometry=s.LineString(type="LineString", coordinates=coords),
                          distance_m=round(distance, 1), duration_min=round(minutes, 1),
                          green_pct=None if green is None else round(green, 1),
                          traffic_m=round(summary["traffic_m"], 1), pois=pois,
                          description=route_description(distance, minutes, green, summary["traffic_m"],
                                                        Counter(p.type for p in pois)))


def route(req, repo, graphs):
    routing, weights_cfg = settings.load("routing"), settings.load("weights")
    labels = (settings.load("sources") or {}).get("labels", {})
    speed = walking_speed_kmh(req.profile, weights_cfg)
    located = graphs.locate([(req.origin.lon, req.origin.lat), (req.destination.lon, req.destination.lat)],
                            routing["snap_max_m"])
    straight = lambda warning: s.RouteResponse(direct=_straight("direct", req.origin, req.destination, speed),
                                               healthy=_straight("healthy", req.origin, req.destination, speed),
                                               warnings=[warning], sources=[])
    if located is None:
        return straight(NO_NETWORK)
    zone, nodes, snaps = located
    g = zone.graph
    weights = req.weights.model_dump() if req.weights else routing["default_route_weights"]
    costs = edge_costs(g, weights, routing["cost_floor"])
    # en serie dentro del hilo de la peticion: un pool compartido con igraph empeoraba la latencia con varias
    # peticiones a la vez (medido: 4 rutas simultaneas en la capital pasaban de 6 s)
    try:
        direct_edges = shortest_path(g, int(nodes[0]), int(nodes[1]), g.length)
        healthy_edges = shortest_path(g, int(nodes[0]), int(nodes[1]), costs)
    except RouteNotFound:
        return straight(DISCONNECTED)
    direct_coords = _coordinates(g, req, nodes, direct_edges)
    healthy_coords = _coordinates(g, req, nodes, healthy_edges)
    pois_index = PoiIndex(repo, [direct_coords, healthy_coords], routing["poi_radius_m"])
    direct = _variant("direct", g, direct_edges, direct_coords, snaps, routing, speed, pois_index)
    healthy = _variant("healthy", g, healthy_edges, healthy_coords, snaps, routing, speed, pois_index)
    warnings = []
    if direct.green_pct is None or healthy.green_pct is None:
        warnings.append("Zona verde: sin datos en parte del recorrido.")
    dates = repo.source_dates()
    sources = [data_source("osm", labels, dates.get("osm"))]
    if healthy.green_pct is not None:
        sources.append(data_source("vpla_redes", labels, dates.get("vpla_redes")))
    for src in sorted({p.source for p in direct.pois + healthy.pois} - {"osm"}):
        sources.append(data_source(src, labels, dates.get(src)))
    if req.weights is None:
        sources.append(data_source("config:routing", labels, None, bool(routing.get("own_criterion"))))
    return s.RouteResponse(direct=direct, healthy=healthy, warnings=warnings, sources=sources)
