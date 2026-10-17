from graph import read_osm
from osm_green import read_green_areas

TAGS = {"leisure": ["park"]}


def _mini_osm(tmp_path):
    # extracto minimo en XML: un parque (via cerrada) y un edificio; solo el parque es verde
    osm = tmp_path / "mini.osm"
    nodes = "".join(f'<node id="{i}" version="1" lat="{lat}" lon="{lon}"/>' for i, (lon, lat) in enumerate(
        [(-3.73, 40.30), (-3.729, 40.30), (-3.729, 40.301), (-3.73, 40.301)], start=1))
    ways = ('<way id="10" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/>'
            '<tag k="leisure" v="park"/></way>'
            '<way id="11" version="1"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="1"/>'
            '<tag k="building" v="yes"/></way>')
    osm.write_text(f'<?xml version="1.0"?><osm version="0.6">{nodes}{ways}</osm>', encoding="utf-8")
    return osm


def test_read_green_areas_only_green_tags(tmp_path):
    g = read_green_areas(_mini_osm(tmp_path), TAGS)
    assert len(g) == 1 and g.crs.to_epsg() == 4326
    assert set(g.columns) == {"osm_id", "geometry"}
    assert g.geometry.iloc[0].area > 0


def test_read_green_areas_matches_graph_reader(tmp_path):
    # misma lectura que graph.read_osm: las rutas y los destinos usan los mismos poligonos
    osm = _mini_osm(tmp_path)
    mine = read_green_areas(osm, TAGS)
    theirs = read_osm(osm, None, TAGS)[3]
    assert list(mine["osm_id"]) == list(theirs["osm_id"])
    assert mine.geometry.geom_equals(theirs.geometry).all()


def test_read_green_areas_empty_tags(tmp_path):
    g = read_green_areas(_mini_osm(tmp_path), {})
    assert len(g) == 0 and g.crs.to_epsg() == 4326
