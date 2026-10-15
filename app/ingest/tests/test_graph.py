import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import LineString, Point, Polygon

from common import DATA_DIR
from graph import edge_factors, index_nodes

CONFIG = {"traffic_by_highway": {"primary": 1.0, "footway": 0.0}, "default_traffic": 0.3, "poi_radius_m": 25}


def test_index_nodes_contiguous():
    edges = pd.DataFrame({"u": [900, 901], "v": [901, 902]})
    nodes = pd.DataFrame({"id": [902, 900, 901], "lon": [0.0, 0.1, 0.2], "lat": [0.0, 0.0, 0.0]})
    n, e = index_nodes(nodes, edges)
    assert sorted(n["node"]) == [0, 1, 2]
    assert set(e["u"]) | set(e["v"]) <= set(n["node"])


def test_edge_factors():
    # dos tramos de ~100 m en Getafe; el primero cruza un parque en su mitad
    a, b, c = (-3.7300, 40.3050), (-3.7288, 40.3050), (-3.7276, 40.3050)
    edges = gpd.GeoDataFrame({"highway": ["footway", "primary"]},
                             geometry=[LineString([a, b]), LineString([b, c])], crs=4326)
    park = gpd.GeoDataFrame(geometry=[Polygon([(-3.7300, 40.3040), (-3.7294, 40.3040),
                                               (-3.7294, 40.3060), (-3.7300, 40.3060)])], crs=4326)
    fountain = gpd.GeoDataFrame({"type": ["fountain"]}, geometry=[Point(-3.7282, 40.30505)], crs=4326)
    f = edge_factors(edges, park, fountain, CONFIG, has_green=True)
    assert f.loc[0, "green_pct"] == pytest.approx(0.5, abs=0.05)
    assert f.loc[1, "green_pct"] == pytest.approx(0.0, abs=0.01)
    assert list(f["traffic"]) == [0.0, 1.0]
    assert list(f["near_fountain"]) == [False, True]
    assert (f["length_m"] > 90).all() and (f["length_m"] < 110).all()


def test_without_vpla_green_is_nan():
    e = gpd.GeoDataFrame({"highway": ["footway"]}, geometry=[LineString([(-3.73, 40.3), (-3.729, 40.3)])], crs=4326)
    empty = gpd.GeoDataFrame(geometry=[], crs=4326)
    f = edge_factors(e, empty, gpd.GeoDataFrame({"type": []}, geometry=[], crs=4326), CONFIG, has_green=False)
    assert f["green_pct"].isna().all()


@pytest.mark.slow
def test_getafe_graph_exists():
    e = pd.read_parquet(DATA_DIR / "graph" / "getafe" / "edges.parquet")
    n = pd.read_parquet(DATA_DIR / "graph" / "getafe" / "nodes.parquet")
    assert len(e) > 1000 and (e["length_m"] > 0).all()
    assert e[["u", "v"]].max().max() < len(n)
    assert e["green_pct"].notna().mean() > 0.9          # Getafe esta en VPLA
