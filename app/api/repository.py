"""Unico punto que conoce DuckDB (arquitectura §4.3). Solo lectura: cada consulta abre y cierra su conexion, asi
una sustitucion atomica de gomad.duckdb o realtime.duckdb (ingest) se ve en la peticion siguiente."""
import email.utils
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import duckdb
import numpy as np

from engine.rules import aqi_category
from live.air import air_categories as live_air_categories, drop_stale_stations

EARTH_RADIUS_M = 6_371_008.8
M_PER_DEG_LAT = 111_320.0
LOCAL_TZ = ZoneInfo("Europe/Madrid")


class DataUnavailable(Exception):
    pass


def haversine_m(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = (np.radians(np.asarray(a, dtype=float)) for a in (lon1, lat1, lon2, lat2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_M * np.arcsin(np.sqrt(a))


def parse_date(text):
    """Fecha de source_date/forecast (ISO o RFC 1123 de las cabeceras HTTP) en hora local de Madrid sin zona."""
    if not text:
        return None
    try:
        d = datetime.fromisoformat(text)
    except ValueError:
        try:
            d = email.utils.parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
    return d.astimezone(LOCAL_TZ).replace(tzinfo=None) if d.tzinfo else d


def _number(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else float(v)


def _naive(ts):
    # TIMESTAMP_NS llega como datetime o pandas.Timestamp segun la version: siempre datetime
    return ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts


def category_at(readings, hour, valid_h):
    """Ultima categoria medida en o antes de `hour` con como mucho valid_h horas de antiguedad; None si no hay."""
    last = None
    for ts, category in readings:
        if ts > hour:
            break
        last = (ts, category)
    if last is None or hour - last[0] > timedelta(hours=valid_h):
        return None
    return last[1]


@dataclass
class Candidate:
    id: str
    source: str
    name: str
    type: str
    covered: bool | None
    ine_code: str
    lon: float
    lat: float
    green: float | None
    activity: str
    suitability: float
    straight_m: float


@dataclass
class Station:
    id: str
    network: str
    name: str
    lon: float
    lat: float


class Repository:
    def __init__(self, data_dir, live=None):
        # live: LiveStore (B2); con el, aire y prevision salen de memoria y no de realtime.duckdb
        self.live = live
        self.forecast_notes = {}     # ine -> «Prevision de <municipio>» cuando se usa la del vecino
        self.main = data_dir / "gomad.duckdb"
        self.realtime = data_dir / "realtime.duckdb"
        self.addresses = data_dir / "clean" / "addresses.parquet"
        self._names = None

    def _query(self, path, sql, params=(), required=False, numpy=False):
        if not path.exists():
            if required:
                raise DataUnavailable("Los datos todavía no están cargados en el servidor.")
            return []
        # un hilo por consulta: con varias peticiones a la vez, los hilos de DuckDB de cada una se pisaban
        con = duckdb.connect(str(path), read_only=True, config={"threads": 1})
        try:
            result = con.execute(sql, list(params))
            return result.fetchnumpy() if numpy else result.fetchall()
        finally:
            con.close()

    def candidates(self, lon, lat, radius_m, activities, setting, per_activity):
        dlat = radius_m / M_PER_DEG_LAT
        dlon = radius_m / (M_PER_DEG_LAT * math.cos(math.radians(lat)))
        covered = {"indoor": "AND d.covered", "outdoor": "AND d.covered IS DISTINCT FROM TRUE"}.get(setting, "")
        marks = ", ".join("?" for _ in activities)
        sql = f"""
            SELECT * FROM (
              SELECT d.id, d.source, d.name, d.type, d.covered, d.ine_code, d.lon, d.lat, d.green,
                     a.activity, a.suitability,
                     2 * {EARTH_RADIUS_M} * asin(sqrt(pow(sin(radians(d.lat - ?) / 2), 2)
                       + cos(radians(?)) * cos(radians(d.lat)) * pow(sin(radians(d.lon - ?) / 2), 2))) AS straight_m
              FROM destination d JOIN destination_activity a ON a.destination_id = d.id
              WHERE a.activity IN ({marks}) AND d.lat BETWEEN ? AND ? AND d.lon BETWEEN ? AND ? {covered})
            WHERE straight_m <= ?
            QUALIFY row_number() OVER (PARTITION BY activity ORDER BY straight_m, id) <= ?
            ORDER BY straight_m, id"""
        params = [lat, lat, lon, *activities, lat - dlat, lat + dlat, lon - dlon, lon + dlon, radius_m, per_activity]
        rows = self._query(self.main, sql, params, required=True)
        return [Candidate(*r[:8], _number(r[8]), *r[9:]) for r in rows]

    def forecast(self, ine_codes, start, end):
        if not ine_codes:
            return {}, {}
        if self.live is not None and getattr(self.live, "forecast", None) is not None:
            return self._live_forecast(ine_codes, start, end)
        marks = ", ".join("?" for _ in ine_codes)
        rows = self._query(self.realtime, f"""SELECT ine_code, ts, temp, feels_like, precip_prob, issued FROM forecast
                                              WHERE ine_code IN ({marks}) AND ts BETWEEN ? AND ? ORDER BY ts""",
                           [*ine_codes, start, end])
        by, issued = {}, {}
        for ine, ts, temp, feels, prob, iss in rows:
            by.setdefault(ine, {})[_naive(ts)] = (_number(temp), _number(feels), _number(prob))
            issued[ine] = parse_date(iss)
        return by, issued

    def _live_forecast(self, ine_codes, start, end):
        """Prevision en memoria (DEC-15). Sin prevision: se pide con prioridad. La del vecino queda en forecast_notes."""
        by, issued, missing = {}, {}, []
        for ine in ine_codes:
            got = self.live.forecast.get(ine)
            if got is None:
                missing.append(ine)
                continue
            series, iss, note = got
            hours = {ts: v[:3] for ts, v in series.items() if start <= ts <= end}
            if hours:
                by[ine], issued[ine] = hours, iss
                if note:
                    self.forecast_notes[ine] = note
        if missing:
            self.live.forecast.request(missing)
        return by, issued

    def stations(self):
        return [Station(*r) for r in self._query(self.main, "SELECT id, network, name, lon, lat FROM air_station",
                                                 required=True)]

    def air_categories(self, start, end, ica, valid_h):
        """{estacion: [(hora, categoria)]} ordenado, con las medias que cumplen la cobertura minima del ICA."""
        if self.live is not None:
            # en vivo (DEC-15): la ultima medicion de cada estacion, solo si cumple max_age_h (por estacion)
            fresh = []
            for name in ("air_cm", "air_ay"):
                e = self.live.get(name)
                if e is not None:
                    fresh.append(drop_stale_stations(e.value, self.live.now(), self.live.sources[name]["max_age_h"]))
            return live_air_categories(fresh, start, end, ica, valid_h)
        rows = self._query(self.realtime, """SELECT station_id, ts, pollutant, mean, n_hours FROM aqi_hourly
                                             WHERE ts BETWEEN ? AND ? ORDER BY station_id, ts""",
                           [start - timedelta(hours=valid_h), end])
        needed = {p: math.ceil(ica["min_coverage"] * h) for p, h in ica["period_hours"].items()}
        measured = {}
        for station, ts, pollutant, mean, n_hours in rows:
            if _number(mean) is None or pollutant not in needed or n_hours is None or n_hours < needed[pollutant]:
                continue
            measured.setdefault(station, {}).setdefault(_naive(ts), {})[pollutant] = float(mean)
        out = {}
        for station, by_ts in measured.items():
            cats = [(ts, aqi_category(values, ica["bands"])) for ts, values in sorted(by_ts.items())]
            cats = [(ts, c) for ts, c in cats if c is not None]
            if cats:
                out[station] = cats
        return out

    def source_dates(self):
        rows = self._query(self.main, "SELECT source, downloaded, modified FROM source_date")
        return {source: parse_date(modified) or parse_date(downloaded) for source, downloaded, modified in rows}

    def municipality_names(self):
        """Nombre para mostrar: el del callejero («Las Rozas de Madrid»); si falta, el de municipality (MAYUSCULAS)."""
        if self._names is None:
            names = dict(self._query(self.main, "SELECT ine_code, name FROM municipality", required=True))
            if self.addresses.exists():
                con = duckdb.connect()
                try:
                    names.update(dict(con.execute("SELECT DISTINCT ine_code, municipality FROM read_parquet(?)",
                                                  [str(self.addresses)]).fetchall()))
                finally:
                    con.close()
            self._names = names
        return self._names

    def route_pois(self, min_lon, min_lat, max_lon, max_lat):
        """{columna: ndarray} (id, type, source, lon, lat): en columnas, sin crear una tupla por punto."""
        return self._query(self.main, """SELECT id, type, source, lon, lat FROM route_poi
                                         WHERE working IS NOT FALSE AND lon BETWEEN ? AND ? AND lat BETWEEN ? AND ?""",
                           [min_lon, max_lon, min_lat, max_lat], required=True, numpy=True)

    def municipality(self, ine_code):
        """(nombre de la tabla, poblacion) o None si el codigo no es de los 179."""
        rows = self._query(self.main, "SELECT name, population FROM municipality WHERE ine_code = ?", [ine_code],
                           required=True)
        return rows[0] if rows else None

    def municipality_indicators(self, ine_code):
        """{key: (value, unit, year, source)} de municipality_indicator (Task 35); value None = «sin datos»."""
        try:
            rows = self._query(self.main, """SELECT key, value, unit, year, source FROM municipality_indicator
                                             WHERE ine_code = ?""", [ine_code], required=True)
        except duckdb.Error as e:                 # base anterior a la Task 35 o con otras columnas
            raise DataUnavailable("Los indicadores de municipio todavía no están cargados en el servidor.") from e
        return {key: (_number(value), unit, year, source) for key, value, unit, year, source in rows}

    def _municipality_query(self, sql, params):
        try:
            return self._query(self.main, sql, params, required=True)
        except duckdb.Error as e:                 # tablas con otra forma: 503 legible, no 500
            raise DataUnavailable("Los datos del municipio no están completos en el servidor.") from e

    def activity_counts(self, ine_code):
        """{actividad: n.º de destinos distintos del municipio} (destination_activity, como catalog_activities)."""
        rows = self._municipality_query("""SELECT a.activity, count(DISTINCT d.id) FROM destination d
                                           JOIN destination_activity a ON a.destination_id = d.id
                                           WHERE d.ine_code = ? GROUP BY a.activity""", [ine_code])
        return dict(rows)

    def poi_count(self, ine_code, poi_type):
        """N.º de puntos de ruta de un tipo en el municipio (los fuera de servicio no cuentan)."""
        rows = self._municipality_query("""SELECT count(*) FROM route_poi
                                           WHERE ine_code = ? AND type = ? AND working IS NOT FALSE""",
                                        [ine_code, poi_type])
        return rows[0][0]
