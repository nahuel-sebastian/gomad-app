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
    # la caja de Getafe incluye trozos de Madrid capital y vecinos sin VPLA: alli NaN (sin dato), no 0
    import shapely
    from common import municipalities
    middle = gpd.GeoSeries(shapely.from_wkb(e["geom"]), crs=4326).to_crs(25830).interpolate(0.5, normalized=True)
    muni = gpd.sjoin(gpd.GeoDataFrame(geometry=middle.to_crs(4326)), municipalities()[["ine_code", "geometry"]],
                     predicate="within")
    ine = muni["ine_code"][~muni.index.duplicated()].reindex(e.index)
    assert e.loc[ine == "28065", "green_pct"].notna().mean() > 0.9          # Getafe esta en VPLA
    assert e.loc[ine == "28079", "green_pct"].isna().all()                  # Madrid capital no


def test_overlapping_green_zones_count_once():
    # VPLA tiene poligonos solapados: el tramo que cruza dos a la vez no cuenta doble
    edges = gpd.GeoDataFrame({"highway": ["footway"]},
                             geometry=[LineString([(-3.7300, 40.3050), (-3.7288, 40.3050)])], crs=4326)
    square = [(-3.7300, 40.3040), (-3.7294, 40.3040), (-3.7294, 40.3060), (-3.7300, 40.3060)]
    zones = gpd.GeoDataFrame(geometry=[Polygon(square), Polygon(square)], crs=4326)
    f = edge_factors(edges, zones, gpd.GeoDataFrame({"type": []}, geometry=[], crs=4326), CONFIG, has_green=True)
    assert f.loc[0, "green_pct"] == pytest.approx(0.5, abs=0.05)


def test_green_pct_uses_spatial_index(monkeypatch):
    # sin indice espacial, la caja de Madrid capital (zonas de los vecinos) tardaba > 25 min
    def no_union(*args, **kwargs):
        raise AssertionError("union_all de todas las zonas: sin indice espacial")
    monkeypatch.setattr(gpd.GeoSeries, "union_all", no_union)
    monkeypatch.setattr(gpd.GeoDataFrame, "union_all", no_union)
    e = gpd.GeoDataFrame({"highway": ["footway"]}, geometry=[LineString([(-3.73, 40.305), (-3.7288, 40.305)])], crs=4326)
    park = gpd.GeoDataFrame(geometry=[Polygon([(-3.7300, 40.3040), (-3.7294, 40.3040),
                                               (-3.7294, 40.3060), (-3.7300, 40.3060)])], crs=4326)
    f = edge_factors(e, park, gpd.GeoDataFrame({"type": []}, geometry=[], crs=4326), CONFIG, has_green=True)
    assert f.loc[0, "green_pct"] == pytest.approx(0.5, abs=0.05)


def _two_edges():
    a, b, c = (-3.7300, 40.3050), (-3.7288, 40.3050), (-3.7276, 40.3050)
    return gpd.GeoDataFrame({"highway": ["footway", "footway"]},
                            geometry=[LineString([a, b]), LineString([b, c])], crs=4326)


NO_POI = gpd.GeoDataFrame({"type": []}, geometry=[], crs=4326)


def test_green_is_nan_outside_covered_municipalities():
    # la caja de Madrid capital trae zonas VPLA de los vecinos; en la capital (sin VPLA) es NaN, no 0
    park = gpd.GeoDataFrame(geometry=[Polygon([(-3.7300, 40.3040), (-3.7294, 40.3040),
                                               (-3.7294, 40.3060), (-3.7300, 40.3060)])], crs=4326)
    covered = gpd.GeoDataFrame(geometry=[Polygon([(-3.7310, 40.3000), (-3.7288, 40.3000),
                                                  (-3.7288, 40.3100), (-3.7310, 40.3100)])], crs=4326)
    f = edge_factors(_two_edges(), park, NO_POI, CONFIG, has_green=True, covered=covered)
    assert f.loc[0, "green_pct"] == pytest.approx(0.5, abs=0.05)
    assert pd.isna(f.loc[1, "green_pct"])


def test_broken_fountains_do_not_count():
    # CLAUDE.md §6.1: la ruta solo cuenta working IS NOT FALSE
    poi = gpd.GeoDataFrame({"id": ["f1", "f2"], "type": ["fountain", "fountain"],
                            "working": pd.array([False, pd.NA], dtype="boolean")},
                           geometry=[Point(-3.7294, 40.30505), Point(-3.7282, 40.30505)], crs=4326)
    f = edge_factors(_two_edges(), gpd.GeoDataFrame(geometry=[], crs=4326), poi, CONFIG, has_green=False)
    assert list(f["near_fountain"]) == [False, True]      # f1 cerrada no cuenta; f2 sin dato si
    assert f.loc[1, "fountain_id"] == "f2"


def test_nearest_poi_id_per_edge():
    # una fuente marca varios tramos seguidos: se guarda su id para contarla una sola vez en la ruta
    poi = gpd.GeoDataFrame({"id": ["ay_fuentes:1"], "type": ["fountain"], "working": pd.array([True], dtype="boolean")},
                           geometry=[Point(-3.7288, 40.30505)], crs=4326)
    f = edge_factors(_two_edges(), gpd.GeoDataFrame(geometry=[], crs=4326), poi, CONFIG, has_green=False)
    assert list(f["near_fountain"]) == [True, True]
    assert list(f["fountain_id"]) == ["ay_fuentes:1", "ay_fuentes:1"]
    assert f["bench_id"].isna().all()
