"""GeoParquet -> app/data/gomad.duckdb y app/data/realtime.duckdb (arquitectura §3.3).

Escribe un fichero nuevo y lo sustituye de golpe: la API (solo lectura) nunca ve un fichero a medias.
Uso: python -m build_db main | realtime | all
"""
import datetime as dt
import json
import os
import sys
import unicodedata

import duckdb
import geopandas as gpd
import pandas as pd
import yaml

from common import CLEAN, CONFIG_DIR, DATA_DIR, RAW

GREEN_RADIUS_M = 300   # criterio propio (DEC-07)
PERIODS = {1: ("SO2", 1), 8: ("NO2", 1), 14: ("O3", 8), 10: ("PM10", 24), 9: ("PM2_5", 24)}


def atomic(target, fill_fn):
    tmp = target.with_suffix(".tmp.duckdb")
    tmp.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp))
    try:
        fill_fn(con)
        con.close()
        os.replace(tmp, target)
    except Exception:
        con.close()
        tmp.unlink(missing_ok=True)
        raise
    return target


def _plain(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()


def apply_activities(destinations, rules):
    """Tabla actividad -> destino de config/activities.yaml. Comparaciones sin mayusculas ni tildes."""
    rows = []
    for act in rules["activities"]:
        for rule in act["rules"]:
            sub = destinations[destinations["source"] == rule["source"]]
            if "sport" in rule:
                sub = sub[sub["sports"].map(lambda xs: xs is not None and rule["sport"] in list(xs))]
            if "in" in rule:
                values = {_plain(v) for v in rule["in"]}
                sub = sub[sub[rule["field"]].map(lambda v: _plain(v) in values)]
            if "contains" in rule:
                keys = [_plain(c) for c in rule["contains"]]
                sub = sub[sub[rule["field"]].map(lambda v: any(k in _plain(v) for k in keys))]
            if "type" in rule:
                sub = sub[sub["type"] == rule["type"]]
            rows += [(i, act["id"], rule["suitability"]) for i in sub["id"]]
    r = pd.DataFrame(rows, columns=["destination_id", "activity", "suitability"])
    return r.groupby(["destination_id", "activity"], as_index=False)["suitability"].max()


def green_fraction(destinations, green, municipalities):
    """Fraccion del circulo de GREEN_RADIUS_M m cubierta por zona verde (EPSG:25830). NULL si el municipio no esta en VPLA."""
    d = destinations.to_crs(25830)
    circles = gpd.GeoDataFrame({"id": d["id"]}, geometry=d.buffer(GREEN_RADIUS_M), crs=25830)
    inter = gpd.overlay(circles, green.to_crs(25830)[["geometry"]], how="intersection", keep_geom_type=True)
    area = inter.dissolve(by="id").area if len(inter) else pd.Series(dtype=float)
    frac = (area / circles.set_index("id").area).reindex(d["id"]).fillna(0.0).clip(0, 1)
    in_vpla = d["ine_code"].map(municipalities.set_index("ine_code")["in_vpla"]).fillna(False).to_numpy(dtype=bool)
    return frac.where(in_vpla, None).to_numpy()


def create_aqi_hourly(con):
    # una ventana con nombre propio por contaminante: DuckDB no admite repetir el nombre en un UNION
    parts = []
    for magnitude, (pollutant, hours) in PERIODS.items():
        parts.append(f"""
          SELECT station_id, ts, '{pollutant}' AS pollutant,
                 avg(value) OVER w{magnitude} AS mean, count(value) OVER w{magnitude} AS n_hours
          FROM air_reading WHERE magnitude = {magnitude}
          WINDOW w{magnitude} AS (PARTITION BY station_id ORDER BY ts
                       RANGE BETWEEN INTERVAL {hours - 1} HOURS PRECEDING AND CURRENT ROW)""")
    con.execute("CREATE TABLE aqi_hourly AS " + " UNION ALL ".join(parts))


def _source_dates():
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8"))
    # las entradas que no se han vuelto a descargar desde Task 2 conservan las claves en espanol
    return pd.DataFrame([{"source": k,
                          "downloaded": v.get("downloaded") or v.get("descargado"),
                          "modified": v.get("modified") or v.get("last_modified")}
                         for k, v in manifest.items()], columns=["source", "downloaded", "modified"])


def build_main(target=DATA_DIR / "gomad.duckdb", rules=None):
    rules = rules or yaml.safe_load((CONFIG_DIR / "activities.yaml").read_text(encoding="utf-8"))
    municipalities = gpd.read_parquet(CLEAN / "municipality.parquet")
    population = pd.read_parquet(CLEAN / "population.parquet")
    population = population[population.year == population.year.max()][["ine_code", "population"]]
    destinations = gpd.read_parquet(CLEAN / "destination_raw.parquet")
    destinations = destinations[destinations["ine_code"].notna()].copy()
    destinations["green"] = green_fraction(destinations, gpd.read_parquet(CLEAN / "green.parquet"), municipalities)
    destinations["lon"], destinations["lat"] = destinations.geometry.x, destinations.geometry.y
    destinations["updated"] = dt.datetime.now()
    activities = apply_activities(destinations, rules)
    stations = gpd.read_parquet(CLEAN / "air_station.parquet")
    poi = gpd.read_parquet(CLEAN / "poi.parquet")

    def fill(con):
        con.execute("INSTALL spatial; LOAD spatial;")
        m = municipalities.merge(population, on="ine_code", how="left").assign(wkb=lambda x: x.geometry.to_wkb())
        con.register("m", pd.DataFrame(m.drop(columns="geometry")))
        con.execute("CREATE TABLE municipality AS SELECT ine_code, name, population, in_eiel, in_vpla, "
                    "ST_GeomFromWKB(wkb) AS geom FROM m")
        cols = ["id", "source", "name", "type", "covered", "accessible", "condition", "owner", "water", "url",
                "ine_code", "lon", "lat", "green", "updated"]
        con.register("d", pd.DataFrame(destinations[cols]))
        con.execute("CREATE TABLE destination AS SELECT * FROM d")
        con.register("a", activities)
        con.execute("CREATE TABLE destination_activity AS SELECT * FROM a")
        con.register("s", pd.DataFrame(stations.assign(lon=stations.geometry.x, lat=stations.geometry.y)
                                       .drop(columns="geometry")))
        con.execute("CREATE TABLE air_station AS SELECT * FROM s")
        con.register("p", pd.DataFrame(poi.assign(lon=poi.geometry.x, lat=poi.geometry.y).drop(columns="geometry")))
        con.execute("CREATE TABLE route_poi AS SELECT * FROM p")
        con.register("f", _source_dates())
        con.execute("CREATE TABLE source_date AS SELECT * FROM f")
    return atomic(target, fill)


def build_realtime(target=DATA_DIR / "realtime.duckdb"):
    since = dt.datetime.now() - dt.timedelta(days=3)

    def fill(con):
        con.execute(f"CREATE TABLE air_reading AS SELECT * FROM read_parquet('{CLEAN}/air_reading/*.parquet') "
                    f"WHERE ts >= TIMESTAMP '{since:%Y-%m-%d %H:%M:%S}'")
        create_aqi_hourly(con)
        con.execute(f"CREATE TABLE forecast AS SELECT * FROM read_parquet('{CLEAN}/forecast/*.parquet')")
    return atomic(target, fill)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("main", "all"):
        print(build_main())
    if what in ("realtime", "all"):
        print(build_realtime())
