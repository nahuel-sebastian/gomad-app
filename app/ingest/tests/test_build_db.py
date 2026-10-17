import duckdb
import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import Point, box

import build_db

TEST_RULES = {"activities": [
    {"id": "swim", "label": "Nadar", "icon": "pool", "outdoor": None, "rules": [
        {"source": "eiel_deporte", "field": "facility_type", "in": ["PISCINAS CUBIERTAS"], "suitability": 1.0},
        {"source": "nmc_deporte", "field": "name", "contains": ["piscina"], "suitability": 0.9}]},
    {"id": "padel", "label": "Pádel", "icon": "sports_tennis", "outdoor": None, "rules": [
        {"source": "eiel_deporte", "sport": "PADEL", "suitability": 1.0},
        {"source": "nmc_deporte", "field": "name", "contains": ["pádel", "padel"], "suitability": 0.8}]},
]}


def sample_destinations():
    return pd.DataFrame([
        {"id": "eiel_deporte:1", "source": "eiel_deporte", "name": "Piscina cubierta", "facility_type": "PISCINAS CUBIERTAS", "sports": []},
        {"id": "eiel_deporte:2", "source": "eiel_deporte", "name": "Polideportivo", "facility_type": "OTROS", "sports": ["PADEL"]},
        {"id": "nmc_deporte:3", "source": "nmc_deporte", "name": "Pistas de PÁDEL Norte", "facility_type": None, "sports": []},
        {"id": "nmc_deporte:4", "source": "nmc_deporte", "name": "Campo de fútbol", "facility_type": None, "sports": []},
    ])


def test_apply_activities():
    r = build_db.apply_activities(sample_destinations(), TEST_RULES)
    assert set(zip(r.destination_id, r.activity)) == {
        ("eiel_deporte:1", "swim"), ("eiel_deporte:2", "padel"), ("nmc_deporte:3", "padel")}


def test_atomic_replace(tmp_path):
    target = tmp_path / "x.duckdb"
    target.write_bytes(b"old version")

    def fails(con):
        raise RuntimeError("fuente rota")

    with pytest.raises(RuntimeError):
        build_db.atomic(target, fails)
    assert target.read_bytes() == b"old version"                # el anterior se mantiene (arquitectura §3.3)
    build_db.atomic(target, lambda con: con.execute("CREATE TABLE t AS SELECT 1 AS a"))
    assert duckdb.connect(str(target), read_only=True).execute("SELECT a FROM t").fetchone() == (1,)


def test_aqi_moving_averages():
    hours = pd.date_range("2026-10-13 01:00", periods=30, freq="h")
    readings = pd.DataFrame({"station_id": "28065014", "magnitude": 14, "ts": hours,
                             "value": [float(i) for i in range(30)], "flag": "V"})
    con = duckdb.connect()
    con.register("air_reading", readings)
    build_db.create_aqi_hourly(con)
    row = con.execute("SELECT mean, n_hours FROM aqi_hourly WHERE pollutant='O3' AND ts = ?",
                      [hours[-1].to_pydatetime()]).fetchone()
    assert row == (sum(range(22, 30)) / 8, 8)                    # media de las 8 ultimas horas


@pytest.mark.slow
def test_build_main_real(tmp_path):
    path = build_db.build_main(tmp_path / "gomad.duckdb", rules=TEST_RULES)
    con = duckdb.connect(str(path), read_only=True)
    assert con.execute("SELECT count(*) FROM municipality").fetchone()[0] == 179
    assert con.execute("SELECT count(*) FROM destination WHERE ine_code IS NULL").fetchone()[0] == 0
    without_vpla = con.execute("SELECT count(*) FROM destination d JOIN municipality m USING (ine_code) "
                               "WHERE NOT m.in_vpla AND d.green IS NOT NULL").fetchone()[0]
    osm_path = build_db.CLEAN / "osm_green.parquet"
    if not osm_path.exists():
        assert without_vpla == 0                                 # sin VPLA ni OSM -> green NULL, no 0
    else:
        # Task 111: sin VPLA, verde de OSM solo en los municipios que tienen algun poligono verde de OSM
        from graph import osm_green_coverage
        munis = gpd.read_parquet(build_db.CLEAN / "municipality.parquet")
        covered = set(osm_green_coverage(munis, set(munis.loc[munis["in_vpla"], "ine_code"]),
                                         gpd.read_parquet(osm_path))["ine_code"])
        got = {c for (c,) in con.execute("SELECT DISTINCT d.ine_code FROM destination d JOIN municipality m "
                                         "USING (ine_code) WHERE NOT m.in_vpla AND d.green IS NOT NULL").fetchall()}
        assert got <= covered and "28079" in got
    assert con.execute("SELECT count(*) FROM destination_activity WHERE activity='swim'").fetchone()[0] > 0
    if (build_db.CLEAN / "osm_poi.parquet").exists():
        # C2b: mobiliario de OSM fuera de la capital; en la capital, sin los tipos que da el Ayuntamiento
        assert con.execute("SELECT count(*) FROM route_poi WHERE source='osm' AND ine_code='28065'").fetchone()[0] > 0
        assert con.execute("SELECT count(*) FROM route_poi WHERE source='osm' AND ine_code='28079' "
                           "AND type IN ('bench', 'fountain', 'dog_area')").fetchone()[0] == 0
        assert con.execute("SELECT count(*) - count(DISTINCT id) FROM route_poi").fetchone()[0] == 0


# Task 111: municipios de juguete de 2 km (EPSG:25830): A con VPLA, B y C sin VPLA; un destino en el centro de cada uno
X0, Y0 = 440000, 4470000
MUNIS = gpd.GeoDataFrame({"ine_code": ["28001", "28002", "28003"], "in_vpla": [True, False, False]},
                         geometry=[box(X0 + i * 2000, Y0, X0 + (i + 1) * 2000, Y0 + 2000) for i in range(3)], crs=25830)
CENTERS = [(X0 + 1000 + i * 2000, Y0 + 1000) for i in range(3)]
DESTS = gpd.GeoDataFrame({"id": ["a", "b", "c"], "ine_code": ["28001", "28002", "28003"]},
                         geometry=[Point(c) for c in CENTERS], crs=25830).to_crs(4326)


def half(i):
    """Rectangulo que cubre la mitad izquierda del circulo de GREEN_RADIUS_M del destino i."""
    x, y = CENTERS[i]
    return box(x - 400, y - 400, x, y + 400)


def zones(*geoms):
    return gpd.GeoDataFrame(geometry=list(geoms), crs=25830).to_crs(4326)


def test_green_fraction_without_osm_unchanged():
    for kw in ({}, {"osm_green": None}):
        g = build_db.green_fraction(DESTS, zones(half(0)), MUNIS, **kw)
        assert g[0] == pytest.approx(0.5, abs=0.02)
        assert pd.isna(g[1]) and pd.isna(g[2])                  # NaN -> NULL al pasar a DuckDB


def test_green_fraction_osm_fills_without_vpla():
    osm = zones(half(1), box(CENTERS[0][0] - 400, Y0 + 600, CENTERS[0][0] + 400, Y0 + 1400))
    g = build_db.green_fraction(DESTS, zones(half(0)), MUNIS, osm_green=osm)
    assert g[0] == pytest.approx(0.5, abs=0.02)                  # con VPLA no cambia aunque OSM lo cubra entero
    assert g[1] == pytest.approx(0.5, abs=0.02)


def test_green_fraction_osm_only_where_municipality_has_osm():
    g = build_db.green_fraction(DESTS, zones(half(0)), MUNIS, osm_green=zones(half(1)))
    assert pd.isna(g[2])                                         # C sin VPLA y sin poligonos OSM: sin dato, no 0


def test_green_fraction_osm_overlapping_counts_once():
    g = build_db.green_fraction(DESTS, zones(half(0)), MUNIS, osm_green=zones(half(1), half(1)))
    assert g[1] == pytest.approx(0.5, abs=0.02)


def test_load_osm_green_missing_is_none(tmp_path):
    assert build_db.load_osm_green(tmp_path / "no.parquet") is None


def test_apply_activities_rule_source_without_rows():
    # Task 111: una regla de una fuente sin filas (osm_sport sin el extracto OSM) rompia con KeyError 'id'
    rules = {"activities": [{"id": "swim", "rules": [
        {"source": "osm_sport", "field": "name", "contains": ["piscina"], "suitability": 0.9},
        {"source": "eiel_deporte", "field": "facility_type", "in": ["PISCINAS CUBIERTAS"], "suitability": 1.0}]}]}
    r = build_db.apply_activities(sample_destinations(), rules)
    assert set(zip(r.destination_id, r.activity)) == {("eiel_deporte:1", "swim")}


# C2b (Task 162): route_poi = fuentes oficiales + mobiliario de OSM, sin duplicados
SKIP = {"28079": ["bench", "fountain", "dog_area"]}


def pois(*rows):
    """rows: (id, type, source, ine_code)."""
    g = gpd.GeoDataFrame(pd.DataFrame(rows, columns=["id", "type", "source", "ine_code"]).assign(
        status=None, working=pd.array([pd.NA] * len(rows), dtype="boolean")),
        geometry=[Point(-3.7, 40.3)] * len(rows), crs=4326)
    return g[["id", "type", "source", "ine_code", "status", "working", "geometry"]]


def test_route_poi_frame_adds_osm():
    poi = pois(("ay_bancos:1", "bench", "ay_bancos", "28079"))
    osm = pois(("osm:node/1", "bench", "osm", "28065"), ("osm:node/2", "playground", "osm", "28079"))
    out = build_db.route_poi_frame(poi, osm, SKIP)
    assert sorted(out["id"]) == ["ay_bancos:1", "osm:node/1", "osm:node/2"]
    assert set(out["source"]) == {"ay_bancos", "osm"} and out.crs.to_epsg() == 4326
    assert str(out["working"].dtype) == "boolean"


def test_route_poi_frame_skips_official_types():
    osm = pois(("osm:node/1", "bench", "osm", "28079"), ("osm:node/2", "fountain", "osm", "28079"),
               ("osm:node/3", "dog_area", "osm", "28079"), ("osm:node/4", "bin", "osm", "28079"),
               ("osm:node/5", "fountain", "osm", "28065"))
    official = pois(("ay_bancos:1", "bench", "ay_bancos", "28079"), ("ay_fuentes:1", "fountain", "ay_fuentes", "28079"),
                    ("ay_areas_caninas:1", "dog_area", "ay_areas_caninas", "28079"))
    out = build_db.route_poi_frame(official, osm, SKIP)
    assert sorted(out["id"]) == ["ay_areas_caninas:1", "ay_bancos:1", "ay_fuentes:1", "osm:node/4", "osm:node/5"]


def test_route_poi_frame_keeps_osm_without_official():
    # sin ay_bancos descargado (capa pesada) la capital conserva los bancos de OSM
    official = pois(("ay_fuentes:1", "fountain", "ay_fuentes", "28079"))
    osm = pois(("osm:node/1", "bench", "osm", "28079"), ("osm:node/2", "fountain", "osm", "28079"))
    out = build_db.route_poi_frame(official, osm, SKIP)
    assert sorted(out["id"]) == ["ay_fuentes:1", "osm:node/1"]


def test_route_poi_frame_no_double_osm():
    # graph.py tambien copia el mobiliario de OSM en poi.parquet: solo cuenta una vez
    poi = pois(("osm:node/1", "bench", "osm", "28065"), ("desfibriladores:9", "aed", "desfibriladores", "28065"))
    osm = pois(("osm:node/1", "bench", "osm", "28065"))
    out = build_db.route_poi_frame(poi, osm, SKIP)
    assert sorted(out["id"]) == ["desfibriladores:9", "osm:node/1"]


def test_route_poi_frame_without_osm_poi():
    poi = pois(("osm:node/1", "bench", "osm", "28065"), ("osm:node/2", "fountain", "osm", "28079"),
               ("ay_fuentes:1", "fountain", "ay_fuentes", "28079"))
    out = build_db.route_poi_frame(poi, None, SKIP)
    assert sorted(out["id"]) == ["ay_fuentes:1", "osm:node/1"]


def test_load_osm_poi_missing_is_none(tmp_path):
    assert build_db.load_osm_poi(tmp_path / "no.parquet") is None
