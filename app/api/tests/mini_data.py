"""Datos minimos con el mismo esquema que app/data (comprobado el 16/10) para pruebas rapidas sin datos reales."""
from datetime import datetime, timedelta

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import shapely
from shapely.geometry import LineString, box

NOW = datetime(2026, 10, 16, 10, 0)            # hora local de Madrid sin zona
ORIGIN = {"lat": 40.3050, "lon": -3.7300}      # nodo 0 del grafo mini

# id, source, name, type, covered, ine_code, lon, lat, green, {actividad: suitability}
DESTINATIONS = [
    ("eiel_parques:1", "eiel_parques", "Parque Uno", "park", False, "28065", -3.7289, 40.3050, 0.8, {"walk": 1.0, "run": 0.8}),
    ("nmc_parques:1", "nmc_parques", "PARQUE UNO", "park", False, "28065", -3.72887, 40.30503, 0.8, {"walk": 1.0}),
    ("nmc_parques:2", "nmc_parques", "Parque Dos", "park", False, "28065", -3.7300, 40.3100, None, {"walk": 1.0}),
    ("eiel_deporte:1", "eiel_deporte", "Polideportivo Cubierto", "facility", True, "28065", -3.7250, 40.3050, 0.1, {"gym": 1.0}),
    ("ay_parques:1", "ay_parques", "Parque Capital", "park", False, "28079", -3.7300, 40.3080, None, {"walk": 0.9}),
    ("nmc_parques:3", "nmc_parques", "Parque Lejano", "park", False, "28065", -3.7300, 40.3500, 0.5, {"walk": 1.0}),
    ("eiel_deporte:2", "eiel_deporte", "Pista de Atletismo", "facility", False, "28065", -3.7310, 40.3055, 0.3, {"run": 1.0}),
    ("vpla_redes:1", "vpla_redes", "Parques Municipales y Urbanos", "park", False, "28065", -3.7300, 40.3070, 0.9, {"walk": 0.9}),
]
ADDRESSES = [   # ine_code, municipality, street_code, street_type, street, street_norm, number, letter, lon, lat
    ("28065", "Getafe", "065A0460", "Calle", "Madrid", "madrid", 10, "", -3.7314934, 40.3056775),
    ("28065", "Getafe", "065A0460", "Calle", "Madrid", "madrid", 12, "", -3.7314000, 40.3057500),
    ("28065", "Getafe", "065A0460", "Calle", "Madrid", "madrid", None, "", -3.7316000, 40.3050000),
    ("28065", "Getafe", "065A0100", "Calle", "de la Constitución", "de la constitucion", 5, "", -3.7290000, 40.3060000),
    ("28079", "Madrid", "079A0001", "Calle", "Gran Vía", "gran via", 1, "", -3.7019000, 40.4196000),
    ("28065", "Getafe", "065A0200", "Calle", "de las Rozas", "de las rozas", 3, "", -3.7280000, 40.3060000),
    ("28127", "Las Rozas de Madrid", "127A0001", "Calle", "Real", "real", 1, "", -3.8700000, 40.4900000),
]
# ine_code, category, key, value, unit, year, source (Task 35). Getafe con valores; Madrid sin VPLA -> green NULL;
# health_centres 0 en Madrid es inventado (solo para probar «no hay» en el encaje de la Task 37)
INDICATORS = [
    ("28065", "sport", "sport_facilities", 19.0, "instalaciones", None, "nmc_deporte"),
    ("28065", "nature", "green_m2_per_inhabitant", 172.788, "m²/hab.", 2025, "vpla_redes"),
    ("28065", "health", "health_centres", 9.0, "centros", None, "sanitarios"),
    ("28065", "health", "aed_per_1000", 1.366, "por 1.000 hab.", None, "desfibriladores"),
    ("28065", "education", "schools", 105.0, "centros", None, "educativos"),
    ("28065", "connectivity", "good_3g_pct", None, "%", 2023, "eiel_nucleos"),
    ("28079", "nature", "green_m2_per_inhabitant", None, "m²/hab.", 2025, "vpla_redes"),
    ("28079", "health", "health_centres", 0.0, "centros", None, "sanitarios"),
    # C3 (Task 173): fuente por fila; Las Rozas sin VPLA con verde de OSM y deporte de dos fuentes
    ("28127", "nature", "green_m2_per_inhabitant", 290.7, "m²/hab.", None, "osm"),
    ("28127", "sport", "sport_facilities_per_1000", 0.5, "por 1.000 hab.", None, "nmc_deporte,osm"),
]
MUNICIPALITY_BOXES = {"28065": ("GETAFE", box(-3.80, 40.25, -3.65, 40.34)),
                      "28079": ("MADRID", box(-3.85, 40.34, -3.55, 40.55)),
                      "28127": ("ROZAS DE MADRID (LAS)", box(-3.95, 40.45, -3.86, 40.56))}


def _graph(directory):
    """   0 --(100 m, avenida)-- 1          0 = ORIGIN, 1 = Parque Uno
          |                      |
       (80 m, parque)        (80 m, parque)      4 -- 5 aislados (fuera de la componente principal)
          |                      |
          2 --(60 m, parque)---- 3"""
    directory.mkdir(parents=True)
    nodes = pd.DataFrame({"node": range(6), "osm_id": range(6),
                          "lon": [-3.7300, -3.7289, -3.7300, -3.7289, -3.7000, -3.6990],
                          "lat": [40.3050, 40.3050, 40.3043, 40.3043, 40.3100, 40.3100]})
    rows = [(0, 1, 100, 1.0, 0.0), (0, 2, 80, 0.0, 1.0), (2, 3, 60, 0.0, 1.0), (3, 1, 80, 0.0, 1.0), (4, 5, 85, 0.0, 0.0)]
    edges = pd.DataFrame(rows, columns=["u", "v", "length_m", "traffic", "green_pct"])
    edges["highway"] = "footway"
    for k in ("near_fountain", "near_bench", "near_aed"):
        edges[k] = False
    edges["geom"] = [LineString([(nodes.lon[u], nodes.lat[u]), (nodes.lon[v], nodes.lat[v])]).wkb
                     for u, v in zip(edges.u, edges.v)]
    nodes.to_parquet(directory / "nodes.parquet")
    edges.to_parquet(directory / "edges.parquet")


def build_mini_data(base, *, forecast=True, precip=0.0, feels=20.0, air=True, graph=False, forecast_ines=("28065",),
                    no2=30.0):
    """precip: numero o funcion hora_relativa -> probabilidad (para simular lluvia solo a ciertas horas)."""
    base.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(base / "gomad.duckdb"))
    con.execute("""CREATE TABLE destination (id VARCHAR, source VARCHAR, name VARCHAR, type VARCHAR, covered BOOLEAN,
                   accessible BOOLEAN, condition VARCHAR, owner VARCHAR, water BOOLEAN, url VARCHAR, ine_code VARCHAR,
                   lon DOUBLE, lat DOUBLE, green DOUBLE, updated TIMESTAMP)""")
    con.execute("CREATE TABLE destination_activity (destination_id VARCHAR, activity VARCHAR, suitability DOUBLE)")
    for d in DESTINATIONS:
        con.execute("INSERT INTO destination VALUES (?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, ?)", [*d[:9], NOW])
        for activity, suitability in d[9].items():
            con.execute("INSERT INTO destination_activity VALUES (?, ?, ?)", [d[0], activity, suitability])
    con.execute("CREATE TABLE municipality (ine_code VARCHAR, name VARCHAR, population BIGINT, in_eiel BOOLEAN, in_vpla BOOLEAN)")
    con.execute("INSERT INTO municipality VALUES ('28065', 'GETAFE', 193238, false, true), ('28079', 'MADRID', 3506730, false, false), "
                "('28127', 'LAS ROZAS DE MADRID', 99037, false, false)")
    con.execute("CREATE TABLE air_station (id VARCHAR, network VARCHAR, name VARCHAR, ine_code VARCHAR, area_type VARCHAR, lon DOUBLE, lat DOUBLE)")
    con.execute("INSERT INTO air_station VALUES ('28065014', 'CM', 'Getafe', '28065', 'Urbana', -3.7310, 40.3060)")
    con.execute("""CREATE TABLE route_poi (id VARCHAR, type VARCHAR, source VARCHAR, ine_code VARCHAR, status VARCHAR,
                   working BOOLEAN, lon DOUBLE, lat DOUBLE)""")
    con.execute("""INSERT INTO route_poi VALUES
        ('ay_fuentes:1', 'fountain', 'ay_fuentes', '28065', NULL, true, -3.7300, 40.30465),
        ('ay_fuentes:2', 'fountain', 'ay_fuentes', '28065', 'CERRADA_TEMPORALMENT', false, -3.72945, 40.3043),
        ('osm:node/1', 'bench', 'osm', '28065', NULL, NULL, -3.72945, 40.30435)""")
    con.execute("CREATE TABLE source_date (source VARCHAR, downloaded VARCHAR, modified VARCHAR)")
    con.execute("""INSERT INTO source_date VALUES ('eiel_parques', '2026-10-14T15:51:38', NULL),
        ('aire_dia', '2026-10-16T09:10:00', '2026-10-16T09:05:00.123456'),
        ('osm', '2026-10-14T15:42:30', 'Tue, 13 Oct 2026 23:55:22 GMT')""")
    con.execute("""CREATE TABLE municipality_indicator (ine_code VARCHAR, category VARCHAR, key VARCHAR, value DOUBLE,
                   unit VARCHAR, year INTEGER, source VARCHAR)""")
    con.executemany("INSERT INTO municipality_indicator VALUES (?, ?, ?, ?, ?, ?, ?)", INDICATORS)
    con.execute("INSERT INTO source_date VALUES ('nmc_deporte', '2026-10-16T15:56:26', NULL)")
    con.execute("""INSERT INTO route_poi VALUES
        ('ay_areas_caninas:1', 'dog_area', 'ay_areas_caninas', '28079', NULL, NULL, -3.7019, 40.4196)""")
    con.close()
    rt = duckdb.connect(str(base / "realtime.duckdb"))
    rt.execute("""CREATE TABLE forecast (ine_code VARCHAR, ts TIMESTAMP_NS, temp DOUBLE, feels_like DOUBLE,
                  precip_prob DOUBLE, precip DOUBLE, wind INTEGER, sky VARCHAR, issued VARCHAR)""")
    if forecast:
        for ine in forecast_ines:
            for h in range(6):
                p = precip(h) if callable(precip) else precip
                rt.execute("INSERT INTO forecast VALUES (?, ?, ?, ?, ?, 0, 5, 'Despejado', '2026-10-16T08:00:00')",
                           [ine, NOW + timedelta(hours=h), feels, feels, p])
    rt.execute("CREATE TABLE aqi_hourly (station_id VARCHAR, ts TIMESTAMP_NS, pollutant VARCHAR, mean DOUBLE, n_hours BIGINT)")
    if air:
        # NO2 30 -> buena; PM10 45 seria «regular», pero con 15 de 24 h no llega a la cobertura minima
        rt.execute("INSERT INTO aqi_hourly VALUES ('28065014', ?, 'NO2', ?, 1), ('28065014', ?, 'PM10', 45.0, 15)",
                   [NOW - timedelta(hours=1), no2, NOW - timedelta(hours=1)])
    rt.close()
    clean = base / "clean"
    clean.mkdir(exist_ok=True)
    pd.DataFrame(ADDRESSES, columns=["ine_code", "municipality", "street_code", "street_type", "street", "street_norm",
                                     "number", "letter", "lon", "lat"]).astype({"number": "Int64"}).to_parquet(
        clean / "addresses.parquet", index=False)
    pq.write_table(pa.table({"ine_code": list(MUNICIPALITY_BOXES),
                             "name": [n for n, _ in MUNICIPALITY_BOXES.values()],
                             "geometry": [shapely.to_wkb(g) for _, g in MUNICIPALITY_BOXES.values()]}),
                   clean / "municipality.parquet")
    if graph:
        _graph(base / "graph" / "mini")
    return base
