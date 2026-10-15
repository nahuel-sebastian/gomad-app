"""POST /route (arquitectura §4.4): directa y saludable en paralelo sobre el grafo de la zona.

Fuera de la red o desconectado: linea recta marcada approximate y aviso. Nunca un 500 por una ruta imposible."""
import math
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import shapely

import schemas as s
import settings
from engine.explanation import route_description
from repository import M_PER_DEG_LAT, haversine_m
from routing.graph import RouteNotFound, edge_costs, shortest_path, summarize
from services.common import data_source, walking_speed_kmh

POOL = ThreadPoolExecutor(max_workers=4)
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


def pois_along(repo, coords, radius_m):
    """Puntos de route_poi (solo working IS NOT FALSE) a menos de radius_m de la linea de la ruta."""
    lons, lats = np.array([c[0] for c in coords]), np.array([c[1] for c in coords])
    cos0 = math.cos(math.radians(float(lats.mean())))
    pad_lat = radius_m / M_PER_DEG_LAT
    pad_lon = pad_lat / cos0
    rows = repo.route_pois(lons.min() - pad_lon, lats.min() - pad_lat, lons.max() + pad_lon, lats.max() + pad_lat)
    rows = [r for r in rows if r[1] in POI_TYPES]
    if not rows:
        return []
    xy = lambda lo, la: np.column_stack([np.asarray(lo) * M_PER_DEG_LAT * cos0, np.asarray(la) * M_PER_DEG_LAT])
    line = shapely.LineString(xy(lons, lats))
    points = shapely.points(xy([r[3] for r in rows], [r[4] for r in rows]))
    near = shapely.distance(line, points) <= radius_m
    return [s.RoutePoi(type=t, coordinate=s.Coordinate(lat=lat, lon=lon), source=src)
            for (_, t, src, lon, lat), ok in zip(rows, near) if ok]


def _straight(kind, origin, destination, speed):
    d = float(haversine_m(origin.lon, origin.lat, destination.lon, destination.lat))
    minutes = d / 1000 / speed * 60
    return s.RouteVariant(kind=kind, geometry=s.LineString(type="LineString", coordinates=[
        [origin.lon, origin.lat], [destination.lon, destination.lat]]), distance_m=round(d, 1),
        duration_min=round(minutes, 1), green_pct=None, traffic_m=0.0, pois=[], approximate=True,
        description=route_description(d, minutes, None, 0, {}, approximate=True))


def _variant(kind, g, req, nodes, snaps, edges, routing, speed, repo):
    coords = [[req.origin.lon, req.origin.lat], *path_coordinates(g, int(nodes[0]), edges),
              [req.destination.lon, req.destination.lat]]
    # sin puntos repetidos seguidos (origen = nodo, tramos que empiezan donde acaba el anterior)
    coords = [c for i, c in enumerate(coords) if i == 0 or c != coords[i - 1]]
    if len(coords) < 2:
        coords = coords * 2         # origen y destino en el mismo punto: LineString de dos puntos iguales
    summary = summarize(g, edges, routing["traffic_display_threshold"])
    distance = summary["distance_m"] + float(snaps[0]) + float(snaps[1])
    minutes = distance / 1000 / speed * 60
    pois = pois_along(repo, coords, routing["poi_radius_m"])
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
    futures = [POOL.submit(shortest_path, g, int(nodes[0]), int(nodes[1]), c) for c in (g.length, costs)]
    try:
        direct_edges, healthy_edges = (f.result() for f in futures)
    except RouteNotFound:
        return straight(DISCONNECTED)
    direct = _variant("direct", g, req, nodes, snaps, direct_edges, routing, speed, repo)
    healthy = _variant("healthy", g, req, nodes, snaps, healthy_edges, routing, speed, repo)
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
