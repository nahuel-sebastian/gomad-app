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

import indicators
from common import CLEAN, CONFIG_DIR, DATA_DIR, RAW, assign_municipality, ine_code, points, to_float

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


HEALTH_TYPES = ("Centro de salud", "Consultorio de atención primaria")   # literales del dato (DEC-09)
INDICATOR_COLUMNS = ["ine_code", "category", "key", "value", "unit", "year", "source"]


def _count(codes):
    return pd.Series(codes).dropna().value_counts()


def _shp(source):
    return gpd.read_file(next((RAW / source).glob("*.shp")), ignore_geometry=True)   # .prj no fiable


def _by_space(gdf):
    """ine_code por cruce espacial con municipality.geom (puntos fuera de la Comunidad -> sin municipio)."""
    return assign_municipality(gdf.assign(ine_code=None))["ine_code"]


def indicator_values(con, config):
    """Valor de cada indicador de DEC-09, solo en los municipios con filas en su fuente."""
    codes = {c for (c,) in con.execute("SELECT ine_code FROM municipality").fetchall()}
    pop = pd.read_parquet(CLEAN / "population.parquet")
    pop = pop[pop["year"] == config["population_year"]].set_index("ine_code")["population"]
    if pop.empty:
        raise ValueError(f"population.parquet no tiene el año {config['population_year']} (population_year)")

    def per_1000(counts):
        return counts / pop.reindex(counts.index) * 1000

    sport = _count(_shp("nmc_deporte")["CMUN"].map(ine_code))
    catalog = con.execute("SELECT d.ine_code, count(DISTINCT a.activity) AS n FROM destination_activity a "
                          "JOIN destination d ON d.id = a.destination_id GROUP BY 1").df().set_index("ine_code")["n"]
    green = gpd.read_parquet(CLEAN / "green.parquet").groupby("ine_code")["area_m2"].sum()
    vp = gpd.read_file(RAW / "vias_pecuarias" / "vias_pecuarias.geojson").set_crs(25830, allow_override=True)
    vp_code = vp["CD_MUNI"].map(ine_code).where(lambda c: c.isin(codes))
    # 28077 (codigo antiguo de 28901) y 289xx (distritos de Madrid anexionados): por su punto representativo
    lost = vp_code.isna()
    vp_code[lost] = _by_space(gpd.GeoDataFrame(geometry=vp[lost].geometry.representative_point().to_crs(4326)))
    drove = (vp["NM_LONG"].map(to_float) / 1000).groupby(vp_code).sum()
    areas = _by_space(points(gpd.read_file(RAW / "areas_recreativas" / "areas_recreativas.geojson",
                                           ignore_geometry=True), "NM_COOX", "NM_COOY", 25830))
    bus = _by_space(points(_shp("nmc_busparadas"), "UTM_X", "UTM_Y", 25830))
    rail = pd.concat([_shp(s)["CMUN"] for s in ("nmc_estmetro", "nmc_estcerca")]).map(ine_code)
    svc = pd.DataFrame(gpd.read_parquet(CLEAN / "service.parquet").drop(columns="geometry"))
    nuc = gpd.read_file(RAW / "eiel_nucleos" / "eiel_nucleos.geojson", ignore_geometry=True)
    good = (nuc["CALIDADUMT"].fillna("").str.strip().str.upper() == "BUENO").groupby(nuc["MUN"].map(ine_code))
    by = lambda cat: _count(svc.loc[svc["category"] == cat, "ine_code"])
    return {
        "sport_facilities": sport,
        "sport_facilities_per_1000": per_1000(sport),
        "catalog_activities": catalog,
        "green_m2_per_inhabitant": green / pop.reindex(green.index),
        "drove_roads_km": drove,
        "recreation_areas": _count(areas),
        "bus_stops_per_1000": per_1000(_count(bus)),
        "rail_stations": _count(rail),
        "health_centres": _count(svc.loc[(svc["category"] == "health") & svc["subtype"].isin(HEALTH_TYPES), "ine_code"]),
        "pharmacies_per_1000": per_1000(by("pharmacy")),
        "aed_per_1000": per_1000(by("aed")),
        "schools": by("education"),
        "good_3g_pct": good.mean() * 100,
        "social_centres": by("social"),
    }


def indicator_table(config, ine_codes, values):
    """Una fila por municipio e indicador; no_rows: zero -> sin filas = 0, null -> sin filas = NULL."""
    rows = []
    for ind in config["indicators"]:
        if ind["key"] not in values:
            raise ValueError(f"indicators.yaml cita «{ind['key']}», pero no se sabe calcular en build_db")
        series, fill = values[ind["key"]], (0.0 if ind["no_rows"] == "zero" else None)
        for code in ine_codes:
            v = series.get(code)
            rows.append((code, ind["category"], ind["key"], fill if v is None or pd.isna(v) else float(v),
                         ind["unit"], ind["year"], ind["source"][0]))
    t = pd.DataFrame(rows, columns=INDICATOR_COLUMNS)
    t["value"], t["year"] = t["value"].astype("Float64"), t["year"].astype("Int64")   # NULL, no NaN
    return t


def store_indicators(con, table):
    con.register("mi", table)
    con.execute("CREATE TABLE municipality_indicator (ine_code VARCHAR, category VARCHAR, key VARCHAR, "
                "value DOUBLE, unit VARCHAR, year INTEGER, source VARCHAR)")
    con.execute("INSERT INTO municipality_indicator SELECT * FROM mi")
    con.unregister("mi")


def create_municipality_indicator(con, config=None):
    """Tabla municipality_indicator (DEC-09, Task 35) a partir de indicators.yaml."""
    config = config or indicators.load()
    codes = [c for (c,) in con.execute("SELECT ine_code FROM municipality ORDER BY ine_code").fetchall()]
    store_indicators(con, indicator_table(config, codes, indicator_values(con, config)))


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
        create_municipality_indicator(con)
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
