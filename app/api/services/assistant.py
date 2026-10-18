"""POST /assistant/route (F6, fila 4): ruta saludable que pasa por los puntos pedidos y condiciones del motor.

El motor elige los puntos (los mas cercanos de cada tipo), calcula la ruta y comprueba cada condicion con datos
reales; la explicacion la redacta el proveedor con plantillas (written_by_ai = False). Lo que todavia no se puede
comprobar (ruta circular por distancia, desnivel, supermercados) sale como condicion no cumplida con su motivo.
La ubicacion nunca sale de aqui hacia terceros."""
import math
from collections import Counter

import numpy as np

import schemas as s
import settings
from ai.dictionary import validate_assistant_config
from ai.provider import build_provider
from engine.explanation import fmt_distance, fmt_minutes, fmt_number, route_description
from repository import M_PER_DEG_LAT, haversine_m
from routing.graph import RouteNotFound, edge_costs, nearest_nodes, shortest_path, summarize
from routing.loop import loop_route
from services.common import walking_speed_kmh
from services.route import PoiIndex, path_coordinates


class NoDestination(Exception):
    pass


def make_provider(env):
    """Proveedor de F6 con config/assistant.yaml validado y OCI Language si hay credenciales en env (app/.env)."""
    cfg = settings.load("assistant")
    validate_assistant_config(cfg)
    return build_provider(cfg, env)


def _km(meters):
    text = fmt_number(meters / 1000, 2).rstrip("0").rstrip(",")
    return f"{text} km"


class _Point:
    def __init__(self, kind, name, lon, lat, distance_m):
        self.kind, self.name, self.lon, self.lat, self.distance_m = kind, name, lon, lat, distance_m
        self.node = None


def _nearest(repo, origin, kind, rcfg, pool_activity):
    """Punto mas cercano del tipo a menos de search_radius_m de la salida (los fuera de servicio no cuentan)."""
    radius = rcfg["search_radius_m"]
    dlat = radius / M_PER_DEG_LAT
    dlon = dlat / math.cos(math.radians(origin.lat))
    bbox = (origin.lon - dlon, origin.lat - dlat, origin.lon + dlon, origin.lat + dlat)
    is_destination = kind in rcfg["destination_kinds"]
    rows = repo.map_points(bbox, [kind] if is_destination else [], [] if is_destination else [kind],
                           rcfg["candidates"], pool_activity)
    best = None
    for _, _, name, _, working, lon, lat in rows:
        if working is False:
            continue
        d = float(haversine_m(origin.lon, origin.lat, lon, lat))
        if d <= radius and (best is None or d < best.distance_m):
            best = _Point(kind, name, float(lon), float(lat), d)
    return best


def _order(origin, points):
    """Vecino mas cercano desde la salida (R2 del plan)."""
    ordered, current, left = [], (origin.lon, origin.lat), list(points)
    while left:
        nxt = min(left, key=lambda p: float(haversine_m(current[0], current[1], p.lon, p.lat)))
        ordered.append(nxt)
        left.remove(nxt)
        current = (nxt.lon, nxt.lat)
    return ordered


def _dedupe(coords):
    coords = [c for i, c in enumerate(coords) if i == 0 or c != coords[i - 1]]
    return coords if len(coords) >= 2 else coords * 2


def _ending(point, rcfg):
    return rcfg["endings"][point.kind].format(name=point.name or rcfg["labels"][point.kind])


class _Plan:
    """Ruta sobre la red: coordenadas desde la salida, tramos, longitud, si vuelve a la salida, resultado de
    loop_route (o None) y motivo si loop_route fallo, y como acaba (punto pedido, punto automatico o la salida)."""

    def __init__(self, coords, edges, distance, closed, loop=None, loop_error=None, end=None, end_auto=False):
        self.coords, self.edges, self.distance, self.closed = coords, edges, distance, closed
        self.loop, self.loop_error, self.end, self.end_auto = loop, loop_error, end, end_auto


def _chain(g, origin_node, reachable, costs):
    """Tramos saludables salida -> puntos en orden; un punto sin conexion se queda sin nodo (no cuenta)."""
    edges, current = [], origin_node
    for p in reachable:
        try:
            edges += shortest_path(g, current, p.node, costs)
            current = p.node
        except RouteNotFound:
            p.node = None
    return edges, current


def _network_route(req, zone, origin_node, origin_snap, waypoints, rcfg, routing, target_m):
    g = zone.graph
    params = req.params
    weights = rcfg["avoid_traffic_weights"] if "traffic" in params.avoid else routing["default_route_weights"]
    costs = edge_costs(g, weights, routing["cost_floor"])
    reachable = [p for p in waypoints if p.node is not None]
    start = [req.origin.lon, req.origin.lat]
    loop_error = None
    if target_m is not None:
        # fila 5: ruta por distancia objetivo, circular o de ida, por los puntos pedidos (en orden)
        try:
            lr = loop_route(g, origin_node, target_m, costs, routing["loop"], loop=params.loop,
                            waypoints=[p.node for p in reachable], snap_m=origin_snap,
                            traffic_threshold=routing["traffic_display_threshold"])
        except (ValueError, RouteNotFound) as e:
            loop_error = str(e)
        else:
            coords = [start, *lr.coordinates, *([start] if params.loop else [])]
            last = lr.waypoints[-1] if lr.waypoints and not params.loop else None
            end = next((p for p in reachable if last is not None and last.requested and p.node == last.node), None)
            return _Plan(_dedupe(coords), lr.edges, lr.length_m, params.loop, loop=lr, end=end,
                         end_auto=last is not None and not last.requested)
    # sin objetivo (o si loop_route falla): tramos saludables por los puntos y, si es ida y vuelta, vuelta a la salida
    edges, current = _chain(g, origin_node, reachable, costs)
    coords = [start, *path_coordinates(g, origin_node, edges)]
    distance = origin_snap
    last = next((p for p in reversed(reachable) if p.node is not None), None)
    if params.loop:
        try:
            back = shortest_path(g, current, origin_node, costs)
        except RouteNotFound:            # no puede pasar: current salio de la salida por la red
            back = []
        coords = [start, *path_coordinates(g, origin_node, edges + back), start]
        edges = edges + back
        distance += origin_snap
    elif last is not None:              # la ruta de ida acaba en el punto, no en el nodo de la red mas cercano
        distance += float(haversine_m(coords[-1][0], coords[-1][1], last.lon, last.lat))
        coords.append([last.lon, last.lat])
    distance += summarize(g, edges)["distance_m"]
    return _Plan(_dedupe(coords), edges, distance, params.loop, loop_error=loop_error, end=last)


def assistant_route(req, repo, graphs, provider):
    cfg = settings.load("assistant")
    rcfg, texts = cfg["route"], cfg["route"]["texts"]
    routing, weights_cfg = settings.load("routing"), settings.load("weights")
    pool_activity = (settings.load("map") or {}).get("pool_activity")
    params, origin = req.params, req.origin
    speed = walking_speed_kmh(params.activity, weights_cfg)
    target_m = (params.distance_km * 1000 if params.distance_km is not None
                else params.duration_min / 60 * speed * 1000 if params.duration_min is not None else None)

    searchable = [k for k in params.pass_by if k in rcfg["destination_kinds"] or k in rcfg["poi_kinds"]]
    found = {k: _nearest(repo, origin, k, rcfg, pool_activity) for k in searchable}
    waypoints = [p for p in found.values() if p is not None]
    default_key = None
    if not waypoints:
        default = _nearest(repo, origin, rcfg["default_destination"], rcfg, pool_activity)
        if default is None:
            raise NoDestination("No hay ningún punto de paso ni ningún parque cerca de tu ubicación para "
                                "preparar la ruta. Prueba con otra ubicación.")
        waypoints = [default]
        default_key = "default_fallback" if params.pass_by else "default_none"
    waypoints = _order(origin, waypoints)

    located = graphs.locate([(origin.lon, origin.lat)], routing["snap_max_m"])
    if located is not None:
        nodes, _ = nearest_nodes(located[0].graph, [p.lon for p in waypoints], [p.lat for p in waypoints],
                                 routing["snap_max_m"])
        for p, n in zip(waypoints, nodes):
            p.node = int(n) if n >= 0 else None
    # sin red en la salida o en todos los puntos de paso: linea recta (aproximada), como /route
    approximate = located is None or all(p.node is None for p in waypoints)
    if approximate:
        coords = [[origin.lon, origin.lat], *[[p.lon, p.lat] for p in waypoints]]
        distance = sum(float(haversine_m(a[0], a[1], b[0], b[1])) for a, b in zip(coords, coords[1:]))
        minutes = distance / 1000 / speed * 60
        variant = s.RouteVariant(kind="healthy", geometry=s.LineString(type="LineString", coordinates=_dedupe(coords)),
                                 distance_m=round(distance, 1), duration_min=round(minutes, 1), green_pct=None,
                                 traffic_m=0.0, pois=[], approximate=True,
                                 description=route_description(distance, minutes, None, 0, {}, approximate=True))
        plan = _Plan(coords, [], distance, False, end=waypoints[-1])
        visited, along = set(), {}
    else:
        zone, nodes, snaps = located
        g = zone.graph
        plan = _network_route(req, zone, int(nodes[0]), float(snaps[0]), waypoints, rcfg, routing, target_m)
        coords = plan.coords
        summary = summarize(g, plan.edges, routing["traffic_display_threshold"])
        minutes = plan.distance / 1000 / speed * 60
        # los puntos del resumen, con el radio de F3; «pasar por», con el suyo (pass_by_radius_m)
        pois = PoiIndex(repo, [coords], routing["poi_radius_m"]).along(coords)
        green = summary["green_pct"]
        variant = s.RouteVariant(
            kind="healthy", geometry=s.LineString(type="LineString", coordinates=coords),
            distance_m=round(plan.distance, 1), duration_min=round(minutes, 1),
            green_pct=None if green is None else round(green, 1), traffic_m=round(summary["traffic_m"], 1),
            pois=pois, description=route_description(plan.distance, minutes, green, summary["traffic_m"],
                                                      Counter(p.type for p in pois)))
        idx = np.asarray(plan.edges, dtype=np.int64)
        visited = {int(nodes[0]), *g.u[idx].tolist(), *g.v[idx].tolist()}
        along = Counter(p.type for p in PoiIndex(repo, [coords], rcfg["pass_by_radius_m"]).along(coords))

    end = (texts["end_auto"] if plan.end_auto else _ending(plan.end, rcfg) if plan.end is not None
           else texts["end_start"])
    conditions = _conditions(params, variant, target_m, plan, approximate, found, visited, along, end,
                             rcfg, routing, texts)
    key = "summary_approximate" if approximate else "summary_loop" if plan.closed else "summary_one_way"
    summary_text = texts[key].format(end=end, description=variant.description)
    if default_key:
        summary_text = texts[default_key].format(end=_ending(waypoints[-1], rcfg)) + " " + summary_text
    explanation = provider.write_up(conditions, summary_text)
    if plan.loop is not None and plan.loop.warning:
        explanation += " " + plan.loop.warning
    return s.AssistantRouteResponse(route=variant, conditions=conditions, explanation=explanation,
                                    written_by_ai=False)


def _target_condition(params, variant, target_m, plan, approximate, routing, texts):
    tolerance = routing["loop"]["tolerance"]
    pct = f"{round(tolerance * 100)}"
    if params.distance_km is not None:
        name = texts["distance"].format(target=_km(target_m), tolerance=pct)
        shown = _km(variant.distance_m)
        met_text = texts["distance_met"]
    else:
        name = texts["duration"].format(target=fmt_minutes(params.duration_min), tolerance=pct)
        shown = fmt_minutes(variant.duration_min)
        met_text = texts["duration_met"]
    if approximate:
        return s.Condition(condition=name, met=False, detail=texts["no_network"])
    if plan.loop is not None:
        lr = plan.loop
        detail = met_text.format(actual=shown, deviation=fmt_number(lr.deviation_pct, 0)) if lr.within_tolerance \
            else lr.warning
        return s.Condition(condition=name, met=lr.within_tolerance, detail=detail)
    return s.Condition(condition=name, met=False, detail=texts["target_failed"].format(actual=shown))


def _conditions(params, variant, target_m, plan, approximate, found, visited, along, end, rcfg, routing, texts):
    out = []
    if target_m is not None:
        out.append(_target_condition(params, variant, target_m, plan, approximate, routing, texts))
    if params.loop:
        closed = plan.closed and not approximate
        out.append(s.Condition(condition=texts["loop"], met=closed,
                               detail=texts["loop_met"] if closed else texts["no_network"]))
    else:
        out.append(s.Condition(condition=texts["one_way"], met=True, detail=texts["one_way_met"].format(end=end)))
    radius_text = fmt_distance(rcfg["search_radius_m"])
    for kind in params.pass_by:
        name = texts["pass_by"].format(label=rcfg["labels"][kind])
        point = found.get(kind)
        if kind in rcfg["no_data"]:
            met, detail = False, rcfg["no_data"][kind]
        elif point is None:
            met, detail = False, texts["none_nearby"].format(radius=radius_text)
        elif approximate:
            met, detail = False, texts["no_network"]
        elif kind in rcfg["destination_kinds"]:
            met = point.node is not None and point.node in visited
            detail = texts["place_met"].format(end=_ending(point, rcfg)) if met else texts["not_on_route"].format(
                distance=fmt_distance(point.distance_m), radius=rcfg["pass_by_radius_m"])
        else:
            n = along.get(kind, 0)
            met = n > 0
            detail = texts["count_met"].format(n=n, radius=rcfg["pass_by_radius_m"]) if met else \
                texts["not_on_route"].format(distance=fmt_distance(point.distance_m), radius=rcfg["pass_by_radius_m"])
        out.append(s.Condition(condition=name, met=met, detail=detail))
    for kind in params.avoid:
        name = texts["avoid"].format(label=rcfg["labels"][kind])
        if approximate:
            met, detail = False, texts["no_network"]
        elif kind == "traffic":
            share = variant.traffic_m / variant.distance_m if variant.distance_m > 0 else 0.0
            met = share <= rcfg["avoid_traffic_max_share"]
            detail = texts["traffic"].format(traffic=fmt_distance(variant.traffic_m), share=round(share * 100))
        else:                                   # cuestas: sin desnivel hasta la fila 6
            met, detail = False, texts["hills"]
        out.append(s.Condition(condition=name, met=met, detail=detail))
    return out
