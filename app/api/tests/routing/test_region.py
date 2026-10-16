"""Validacion de S-R1 con el grafo regional: rutas reales < 5 s en capital, San Lorenzo y un municipio sin mobiliario."""
import time

import pytest

import schemas as s
from repository import Repository
from routing.graph import load_graph
from routing.store import GraphStore, Zone
from services.route import route
from settings import DATA_DIR

pytestmark = pytest.mark.slow
REGION = DATA_DIR / "graph" / "region"
# (origen, destino) a 1-2 km dentro de cada municipio
SAMPLES = {
    "madrid_28079": ((-3.7038, 40.4168), (-3.6846, 40.4153)),       # Sol -> Retiro
    "san_lorenzo_28131": ((-4.1476, 40.5891), (-4.1393, 40.5822)),  # Monasterio -> estacion
    "algete_28009": ((-3.4979, 40.5966), (-3.5085, 40.5998)),       # sin mobiliario en OSM
}


@pytest.fixture(scope="module")
def region_store():
    if not (REGION / "edges.parquet").exists():
        pytest.skip("sin grafo regional")
    g = load_graph(REGION)
    return GraphStore([Zone("region", g, (g.lon.min(), g.lat.min(), g.lon.max(), g.lat.max()))])


@pytest.fixture(scope="module")
def repo():
    return Repository(DATA_DIR)


@pytest.mark.parametrize("name", SAMPLES)
def test_region_routes_under_5s(region_store, repo, name):
    (olon, olat), (dlon, dlat) = SAMPLES[name]
    req = s.RouteRequest(origin=s.Coordinate(lon=olon, lat=olat), destination=s.Coordinate(lon=dlon, lat=dlat))
    t0 = time.perf_counter()
    res = route(req, repo, region_store)
    elapsed = time.perf_counter() - t0
    print(f"\n{name}: {elapsed:.2f} s, {res.healthy.distance_m:.0f} m, verde {res.healthy.green_pct}, "
          f"puntos {len(res.healthy.pois)}")
    assert not res.direct.approximate and not res.healthy.approximate
    assert elapsed < 5.0


def test_store_prefers_smallest_zone():
    store = GraphStore.load(DATA_DIR / "graph")
    if "region" not in {z.name for z in store.zones}:
        pytest.skip("sin grafo regional")
    zone, _, _ = store.locate([SAMPLES["madrid_28079"][0], SAMPLES["madrid_28079"][1]], 300)
    assert zone.name == "madrid"
    zone, _, _ = store.locate(list(SAMPLES["algete_28009"]), 300)
    assert zone.name == "region"
