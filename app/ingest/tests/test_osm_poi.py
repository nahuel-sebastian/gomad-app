import pandas as pd
import pytest
import yaml

import common
import osm_poi
from graph import osm_pois, read_osm
from osm_poi import furniture_frame, read_furniture

OUT = {"fountain": {"drinking_water": ["no"], "operational_status": ["closed"]}}


def _mini_osm(tmp_path, extra_nodes=""):
    # banco, fuente sin agua potable, panaderia (no es mobiliario) y un parque infantil como via cerrada
    osm = tmp_path / "mini.osm"
    nodes = (
        '<node id="1" version="1" lat="40.300" lon="-3.730"><tag k="amenity" v="bench"/></node>'
        '<node id="2" version="1" lat="40.301" lon="-3.731"><tag k="amenity" v="drinking_water"/>'
        '<tag k="drinking_water" v="no"/></node>'
        '<node id="3" version="1" lat="40.302" lon="-3.732"><tag k="shop" v="bakery"/></node>'
        + "".join(f'<node id="{i}" version="1" lat="{lat}" lon="{lon}"/>' for i, (lon, lat) in enumerate(
            [(-3.72, 40.30), (-3.719, 40.30), (-3.719, 40.301), (-3.72, 40.301)], start=10))
        + extra_nodes)
    ways = ('<way id="20" version="1"><nd ref="10"/><nd ref="11"/><nd ref="12"/><nd ref="13"/><nd ref="10"/>'
            '<tag k="leisure" v="playground"/></way>')
    osm.write_text(f'<?xml version="1.0"?><osm version="0.6">{nodes}{ways}</osm>', encoding="utf-8")
    return osm


def test_read_furniture_types(tmp_path):
    p = furniture_frame(read_furniture(_mini_osm(tmp_path), OUT))
    assert len(p) == 3 and p.crs.to_epsg() == 4326
    assert set(p["type"]) == {"bench", "fountain", "playground"}
    assert set(p["source"]) == {"osm"}
    assert list(p.columns) == ["id", "type", "source", "ine_code", "status", "working", "geometry"]


def test_read_furniture_out_of_service(tmp_path):
    p = furniture_frame(read_furniture(_mini_osm(tmp_path), OUT)).set_index("id")
    assert p.loc["osm:node/2", "status"] == "drinking_water=no"
    assert bool(p.loc["osm:node/2", "working"]) is False
    assert p.loc["osm:node/1", "status"] is None
    assert pd.isna(p.loc["osm:node/1", "working"])
    assert str(p["working"].dtype) == "boolean"


def test_read_furniture_matches_graph_reader(tmp_path):
    # mismos ids y tipos que el grafo: fountain_id/bench_id de los tramos casan con route_poi
    osm = _mini_osm(tmp_path)
    mine = furniture_frame(read_furniture(osm, OUT))
    theirs = osm_pois(read_osm(osm, None)[2])
    assert sorted(zip(mine["id"], mine["type"])) == sorted(zip(theirs["id"], theirs["type"]))
    assert mine.set_index("id").geometry.geom_equals(theirs.set_index("id").geometry).all()


def test_out_of_service_config_strings(root):
    cfg = yaml.safe_load((root.parent / "config" / "routing.yaml").read_text(encoding="utf-8"))
    out = cfg["osm_poi"]["out_of_service"]
    assert set(out) == {"fountain"}                               # solo las fuentes tienen estado de servicio
    values = [v for tags in out.values() for vs in tags.values() for v in vs]
    assert values and all(isinstance(v, str) for v in values)   # "no" sin comillas seria False en YAML


def test_out_of_service_only_its_type(tmp_path):
    # un parque infantil con drinking_water=no no esta fuera de servicio
    play = ('<node id="6" version="1" lat="40.303" lon="-3.733"><tag k="leisure" v="playground"/>'
            '<tag k="drinking_water" v="no"/></node>')
    p = furniture_frame(read_furniture(_mini_osm(tmp_path, play), OUT)).set_index("id")
    assert p.loc["osm:node/6", "status"] is None and pd.isna(p.loc["osm:node/6", "working"])
    assert bool(p.loc["osm:node/2", "working"]) is False


@pytest.mark.slow
def test_extract_filters_region(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "CLEAN", tmp_path / "clean")
    lisbon = '<node id="5" version="1" lat="38.72" lon="-9.14"><tag k="amenity" v="bench"/></node>'
    path, n = osm_poi.extract(_mini_osm(tmp_path, lisbon), {"osm_poi": {"out_of_service": OUT}})
    out = pd.read_parquet(path)
    assert path.parent == tmp_path / "clean" and n == len(out) == 3
    assert "osm:node/5" not in set(out["id"])
    assert set(out["ine_code"]) == {"28065"}
