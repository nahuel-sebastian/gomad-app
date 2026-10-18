"""Ruta por distancia objetivo, circular o de ida, con puntos de paso opcionales (RF-22, fila 5).

Interfaz publica (la usa la integracion con el asistente F6, services/assistant.py):

    loop_route(g, origin, target_m, costs, cfg, *, loop=True, waypoints=(), snap_m=0.0,
               traffic_threshold=0.5, clock=time.perf_counter) -> LoopRoute

    g          routing.graph.Graph de la zona (GraphStore.locate devuelve zona, nodos y distancias de enganche)
    origin     nodo de origen (int)
    target_m   distancia objetivo en metros (> 0; si no, ValueError)
    costs      coste saludable por tramo: edge_costs(g, pesos, routing["cost_floor"]) (el mismo de /route)
    cfg        settings.load("routing")["loop"]
    loop       True = vuelve al origen; False = solo ida
    waypoints  nodos por los que pasar, en ese orden (p. ej. el parque o supermercado mas cercano)
    snap_m     metros del punto real al nodo de origen; se suman (x 2 si es circular) a length_m
    traffic_threshold  routing["traffic_display_threshold"], para summary["traffic_m"]

    LoopRoute: edges (ids de tramo en orden), coordinates ([[lon, lat], ...] desde el nodo de origen; sin el
    tramo de enganche), length_m, target_m, within_tolerance (|length_m - target_m| <= tolerance x target_m),
    deviation_pct, waypoints (list[Waypoint(node, lon, lat, requested)] en orden de paso; requested=False =
    elegido por el motor), summary (summarize(): distance_m, green_pct, traffic_m, fountains, benches, aeds),
    warning (texto para la persona usuaria si no cumple; None si cumple), attempts.

    Excepciones: RouteNotFound si un punto de paso no esta conectado con el origen por la red peatonal.
    Si no hay ruta dentro de la tolerancia devuelve la mas cercana con within_tolerance=False y warning:
    nunca finge que cumple. Determinista (sin azar). No registra nada en logs. El tiempo total (subgrafo
    incluido) queda por debajo de time_budget_s salvo el primer intento, que siempre se hace.

    loop_route NO saca los puntos de ruta (route_poi: fuentes, bancos, papeleras... que muestra el mapa);
    summary solo trae los recuentos del grafo. Quien la integre los saca como /route:
    services.route.PoiIndex(repo, [coordinates], routing["poi_radius_m"]).along(coordinates).

Metodo: subgrafo recortado alrededor del origen; tramos saludables encadenados origen -> puntos pedidos ->
punto(s) automaticos a ~objetivo/3 elegidos por distancia de red y rumbo -> (origen); los tramos ya
recorridos se penalizan (reuse_penalty) y se reintenta reescalando y girando el rumbo dentro de time_budget_s.
"""
import math
import time
from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from routing.graph import RouteNotFound, _xy, bounded_distances, summarize
from services.route import path_coordinates

MIN_COST = 1e-6     # scipy trata un peso 0 como "sin tramo"


def _pairs(a, b, value, edge_ids):
    """Un par (a, b) por tramo duplicado: el de menor value. Devuelve a, b, value e id global ordenados por clave."""
    order = np.lexsort((value, b, a))
    a, b, value, edge_ids = a[order], b[order], value[order], edge_ids[order]
    first = np.ones(len(a), dtype=bool)
    first[1:] = (a[1:] != a[:-1]) | (b[1:] != b[:-1])
    return a[first], b[first], value[first], edge_ids[first]


def _symmetric(a, b, n):
    """CSR simetrico con data = indice del par; permite rehacer los pesos sin reconstruir la estructura."""
    k = np.arange(len(a))
    m = csr_matrix((np.concatenate([k, k]) + 1, (np.concatenate([a, b]), np.concatenate([b, a]))), shape=(n, n))
    return m.indices, m.indptr, m.data - 1


class Subgraph:
    """Recorte del grafo alrededor del origen (radio por longitud de red) con el coste saludable de la peticion.

    Un bucle de longitud L no se aleja mas de L/2 del origen: el recorte no pierde rutas validas y cada
    Dijkstra posterior es barato aunque el grafo cargado sea el regional."""

    def __init__(self, g, origin, radius_m, costs):
        self.g = g
        dist = bounded_distances(g, origin, radius_m)
        self.nodes = np.flatnonzero(np.isfinite(dist))
        self.local = np.full(len(g.lon), -1, dtype=np.int64)
        self.local[self.nodes] = np.arange(len(self.nodes))
        n = len(self.nodes)
        lu, lv = self.local[g.u], self.local[g.v]
        inside = np.flatnonzero((lu >= 0) & (lv >= 0) & (lu != lv))
        a, b = np.minimum(lu[inside], lv[inside]), np.maximum(lu[inside], lv[inside])
        # longitudes (distancia mas corta estimada) y costes saludables, cada uno con su tramo mas barato
        la, lb, lw, _ = _pairs(a, b, g.length[inside], inside)
        idx, ptr, perm = _symmetric(la, lb, n)
        self.length_csr = csr_matrix((np.maximum(lw, MIN_COST)[perm], idx, ptr), shape=(n, n))
        self.ca, self.cb, cost, self.cedge = _pairs(a, b, np.maximum(costs[inside], MIN_COST), inside)
        self.cost = cost
        self.c_idx, self.c_ptr, self.c_perm = _symmetric(self.ca, self.cb, n)
        self.keys = self.ca * n + self.cb
        self.n = n

    def contains(self, node):
        return bool(self.local[node] >= 0)

    def length_from(self, node):
        """Distancia por longitud de red desde node a cada nodo global (inf fuera del recorte o sin camino)."""
        out = np.full(len(self.g.lon), np.inf)
        if self.contains(node):
            out[self.nodes] = dijkstra(self.length_csr, directed=True, indices=int(self.local[node]))
        return out

    def path(self, a, b, used, penalty):
        """Tramos (ids globales, en orden) del camino saludable de a a b; los de used cuestan penalty veces mas."""
        if not (self.contains(a) and self.contains(b)):
            raise RouteNotFound("Punto fuera de la red alcanzable")
        if a == b:
            return []
        cost = self.cost
        if used:
            cost = cost.copy()
            cost[np.isin(self.cedge, list(used))] *= penalty
        m = csr_matrix((cost[self.c_perm], self.c_idx, self.c_ptr), shape=(self.n, self.n))
        la, lb = int(self.local[a]), int(self.local[b])
        _, pred = dijkstra(m, directed=True, indices=la, return_predecessors=True)
        if pred[lb] < 0:
            raise RouteNotFound("Los puntos no están conectados por la red peatonal")
        seq = [lb]
        while seq[-1] != la:
            seq.append(int(pred[seq[-1]]))
        seq = np.array(seq[::-1])
        x, y = np.minimum(seq[:-1], seq[1:]), np.maximum(seq[:-1], seq[1:])
        return [int(e) for e in self.cedge[np.searchsorted(self.keys, x * self.n + y)]]


@dataclass
class Waypoint:
    node: int
    lon: float
    lat: float
    requested: bool          # True = pedido (p. ej. el parque del asistente); False = elegido por el motor


@dataclass
class LoopRoute:
    edges: list              # ids globales de tramo, en orden desde el origen
    coordinates: list        # [[lon, lat], ...] desde el nodo de origen
    length_m: float          # tramos + snap_m (x 2 si es circular)
    target_m: float
    within_tolerance: bool
    deviation_pct: float     # (length_m - target_m) / target_m * 100
    waypoints: list          # Waypoint en el orden de paso
    summary: dict            # summarize(): distance_m, green_pct, traffic_m, fountains, benches, aeds
    warning: str | None      # texto para la persona usuaria si no cumple la tolerancia
    attempts: int


def _km(m):
    return f"{m / 1000:.1f}".replace(".", ",")


def _bearings(xy, origin):
    d = xy - xy[origin]
    return np.degrees(np.arctan2(d[:, 0], d[:, 1])) % 360


def _pick(estimate, want, bearings, prefer, exclude, cand_tol):
    """Nodo cuya distancia estimada se acerca a want; entre los de dentro de cand_tol, el de rumbo mas parecido."""
    ok = np.isfinite(estimate)
    ok[list(exclude)] = False
    if not ok.any():
        return None
    gap = np.abs(estimate - want)
    close = ok & (gap <= cand_tol * want)
    if close.any():
        turn = np.abs((bearings - prefer + 180) % 360 - 180)
        return int(np.flatnonzero(close)[np.argmin(turn[close])])
    return int(np.flatnonzero(ok)[np.argmin(gap[ok])])


def _subgraph(g, origin, radius, costs, waypoints, margin, search_factors):
    sub = Subgraph(g, origin, radius, costs)
    if all(sub.contains(w) for w in waypoints):
        return sub
    # punto pedido fuera del radio: se busca a factor x su distancia en linea recta (un factor y, si no
    # aparece, el siguiente) y el subgrafo se amplia hasta margin x su distancia de red
    xy = _xy(g.lon, g.lat, g.cos_lat0)
    straight = max(float(np.hypot(*(xy[w] - xy[origin]))) for w in waypoints)
    far = math.inf
    for factor in search_factors:
        dist = bounded_distances(g, origin, max(radius, factor * straight))
        far = max(float(dist[w]) for w in waypoints)
        if math.isfinite(far):
            break
    if not math.isfinite(far):
        raise RouteNotFound("El punto de paso no está conectado con el origen por la red peatonal")
    return Subgraph(g, origin, max(radius, margin * far), costs)


def loop_route(g, origin, target_m, costs, cfg, *, loop=True, waypoints=(), snap_m=0.0,
               traffic_threshold=0.5, clock=time.perf_counter):
    if not target_m or target_m <= 0:
        raise ValueError("target_m debe ser positivo")
    t0 = clock()
    tol, penalty = cfg["tolerance"], cfg["reuse_penalty"]
    waypoints = [int(w) for w in waypoints]
    # un enganche enorme puede comerse el objetivo: sin tramos libres, ruta fuera de tolerancia con aviso
    edges_target = max(0.0, target_m - snap_m * (2 if loop else 1))
    radius = target_m * (1 + tol) / (2 if loop else 1)
    sub = _subgraph(g, origin, radius, costs, waypoints, cfg["radius_margin"],
                    cfg["waypoint_search_factors"])
    xy = _xy(g.lon, g.lat, g.cos_lat0)
    bearings = _bearings(xy, origin)
    from_origin = sub.length_from(origin)

    # tramos fijos: origen -> puntos pedidos, en el orden dado (iguales en todos los intentos)
    fixed, used, anchor = [], set(), origin
    for w in waypoints:
        leg = sub.path(anchor, w, used, penalty)
        fixed += leg
        used |= set(leg)
        anchor = w
    from_anchor = from_origin if anchor == origin else sub.length_from(anchor)
    two_free = loop and not waypoints and edges_target > 0

    best, scale, attempts, started = None, cfg["initial_scale"], 0, t0
    for i in range(cfg["max_attempts"]):
        now = clock()
        # no se empieza un intento que, durando como el anterior, pasaria del presupuesto (cuenta el subgrafo)
        if i > 0 and (now - t0) + (now - started) > cfg["time_budget_s"]:
            break
        started = now
        attempts += 1
        heading = cfg["initial_bearing_deg"] + (i // cfg["rescales_per_direction"]) * cfg["bearing_step_deg"]
        edges, legs_used, last, free, est, real = list(fixed), set(used), anchor, [], 0.0, 0.0
        d_last = from_anchor
        if two_free:
            want = edges_target * cfg["leg_fraction"] / scale
            a = _pick(from_origin, want, bearings, heading, {origin}, cfg["candidate_tolerance"])
            if a is not None:
                leg = sub.path(origin, a, legs_used, penalty)
                edges += leg
                legs_used |= set(leg)
                free.append(a)
                est += from_origin[a]
                real += g.length[leg].sum()
                last, d_last = a, sub.length_from(a)
        remaining, x = edges_target - float(g.length[edges].sum()), None
        # circular: la vuelta mas corta desde la ultima ancla ya consume parte de lo que queda
        if remaining - (d_last[origin] if loop else 0.0) > tol * target_m:
            prefer = heading if last == origin else bearings[last] + cfg["turn_deg"]
            estimate = d_last + from_origin if loop else d_last
            x = _pick(estimate, remaining / scale, bearings, prefer, {origin, last}, cfg["candidate_tolerance"])
            if x is not None:
                leg = sub.path(last, x, legs_used, penalty)
                edges += leg
                legs_used |= set(leg)
                real += g.length[leg].sum()
                free.append(x)
                est += estimate[x]
                last = x
        if loop and last != origin:
            leg = sub.path(last, origin, legs_used, penalty)
            edges += leg
            if x is not None:
                real += g.length[leg].sum()   # la vuelta entra en la estimacion de X (d_ancla + d_origen)
        if est > 0 and real > 0:
            scale = real / est
        length = float(g.length[edges].sum()) + snap_m * (2 if loop else 1)
        if best is None or abs(length - target_m) < abs(best[0] - target_m):
            best = (length, edges, free)
        if abs(length - target_m) <= tol * target_m:
            break

    length, edges, free = best
    within = abs(length - target_m) <= tol * target_m
    points = [Waypoint(int(n), float(g.lon[n]), float(g.lat[n]), True) for n in waypoints]
    points += [Waypoint(int(n), float(g.lon[n]), float(g.lat[n]), False) for n in free]
    coords = path_coordinates(g, origin, edges) if edges else [[float(g.lon[origin]), float(g.lat[origin])]] * 2
    warning = None if within else (
        f"No se ha encontrado una ruta de {_km(target_m)} km dentro del ±{round(tol * 100)} %: "
        f"la más cercana mide {_km(length)} km.")
    return LoopRoute(edges=edges, coordinates=coords, length_m=length, target_m=float(target_m),
                     within_tolerance=within, deviation_pct=100 * (length - target_m) / target_m,
                     waypoints=points, summary=summarize(g, edges, traffic_threshold), warning=warning,
                     attempts=attempts)
