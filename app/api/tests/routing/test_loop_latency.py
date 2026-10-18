"""Latencia de la ruta por distancia objetivo en el grafo real (RNF: ruta < 5 s). Se salta si no hay grafo."""
import time

import pytest

import settings
from routing.graph import RouteNotFound, edge_costs, load_graph, nearest_node
from routing.loop import loop_route
from settings import DATA_DIR

pytestmark = pytest.mark.slow
PLACES = {"getafe": (-3.7319, 40.3057), "madrid": (-3.7038, 40.4168)}
CASES = [(place, km, loop) for place in PLACES for km, loop in ((5, True), (15, True), (5, False))]


@pytest.fixture(scope="module")
def g():
    for name in ("region", "madrid", "getafe"):
        d = DATA_DIR / "graph" / name
        if (d / "edges.parquet").exists():
            t0 = time.perf_counter()
            graph = load_graph(d)
            print(f"\n{name}: carga {time.perf_counter() - t0:.1f} s, {len(graph.lon)} nodos")
            return graph
    pytest.skip("sin grafo")


@pytest.mark.parametrize("place,km,loop", CASES)
def test_loop_route_under_5s(g, place, km, loop):
    routing = settings.load("routing")
    try:
        origin = nearest_node(g, *PLACES[place], routing["snap_max_m"])
    except RouteNotFound:
        pytest.skip(f"{place} fuera de este grafo")
    t0 = time.perf_counter()
    costs = edge_costs(g, routing["default_route_weights"], routing["cost_floor"])
    r = loop_route(g, origin, km * 1000, costs, routing["loop"], loop=loop,
                   traffic_threshold=routing["traffic_display_threshold"])
    elapsed = time.perf_counter() - t0
    print(f"{place} {km} km {'circular' if loop else 'ida'}: {elapsed:.2f} s, {r.length_m:.0f} m "
          f"({r.deviation_pct:+.1f} %), intentos {r.attempts}, verde {r.summary['green_pct']}, "
          f"fuentes {r.summary['fountains']}, bancos {r.summary['benches']}")
    assert elapsed < 5.0
    assert r.within_tolerance == (abs(r.deviation_pct) <= 10)
    assert r.within_tolerance or r.warning          # nunca finge que cumple
