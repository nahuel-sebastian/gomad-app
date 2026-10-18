"""Ruta por distancia objetivo, circular o de ida (RF-22, fila 5)."""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from routing.graph import RouteNotFound, bounded_distances

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
