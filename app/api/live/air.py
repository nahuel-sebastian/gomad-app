"""Wrapper del aire medido: aire_dia (CKAN Comunidad) y ay_aire (Ayuntamiento), mismo formato H/V.

Reescribe en la API lo que hacen ingest/normalize/air.py y build_db.create_aqi_hourly (ningun servicio importa
codigo de otro): formato largo con la validacion del origen, medias moviles del ICA y categoria por hora.
"""
import csv
import io
import logging
import math
from datetime import datetime, timedelta
from pathlib import Path

import pyarrow.parquet as pq

from engine.rules import aqi_category

log = logging.getLogger("gomad.api")

# magnitudes del fichero -> contaminante del ICA (descripcion oficial del fichero, umbrales.md §1.2)
POLLUTANTS = {1: "SO2", 8: "NO2", 9: "PM2_5", 10: "PM10", 14: "O3"}
VALID_FLAGS = ("V", "T")     # V valido, T temporal pendiente de validar; N y vacio fuera


def _float(text):
    s = (text or "").strip().replace(",", ".")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def decode(raw):
    # los CSV propios del CKAN llevan BOM UTF-8; por si acaso, Windows-1252 como en la ingesta
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def parse_air_csv(text):
    """[(station_id, magnitude, ts, value)]: ts = fin de la hora (h24 = 00:00 del dia siguiente), fecha de cada fila."""
    out = []
    for row in csv.DictReader(io.StringIO(text), delimiter=";"):
        r = {k.strip().lower(): v for k, v in row.items() if k}
        try:
            magnitude = int(r["magnitud"])
            code = (r["municipio"] or "").strip()
            # «65», «079» o, por si acaso, el INE completo «28079»
            municipality = int(code[2:]) if len(code) == 5 and code.startswith("28") else int(code)
            station = int(r["estacion"])
            day = datetime(int(r["ano"]), int(r["mes"]), int(r["dia"]))
        except (KeyError, TypeError, ValueError):
            continue
        if magnitude not in POLLUTANTS:
            continue
        station_id = f"28{municipality:03d}{station:03d}"       # codigos sin ceros: «65», «079»
        for h in range(1, 25):
            value = _float(r.get(f"h{h:02d}"))
            if value is None or (r.get(f"v{h:02d}") or "").strip().upper() not in VALID_FLAGS:
                continue
            out.append((station_id, magnitude, day + timedelta(hours=h), value))
    return out


class AirFeed:
    """Una red de aire: descarga, pasa a formato largo y guarda un bufer de buffer_h horas para las medias."""

    def __init__(self, source, url, buffer_h):
        self.source, self.url, self.buffer_h = source, url, buffer_h
        self._buffer = {}

    def merge(self, readings, now):
        for station, magnitude, ts, value in readings:
            self._buffer[(station, magnitude, ts)] = value          # lo nuevo sustituye a lo viejo (T -> V)
        oldest = now - timedelta(hours=self.buffer_h)
        self._buffer = {k: v for k, v in self._buffer.items() if k[2] >= oldest}
        return sorted((s, m, ts, v) for (s, m, ts), v in self._buffer.items())

    def fetch(self, store):
        content, _ = store.http_get(self.source, self.url)
        parsed = parse_air_csv(decode(content))
        if store.snapshot and parsed:
            # demo sin red: lo grabado se reproduce como si fuera de ahora (la app dice «datos grabados»)
            now = store.now().replace(minute=0, second=0, microsecond=0)
            shift = now - max(r[2] for r in parsed)
            parsed = [(st, m, ts + shift, v) for st, m, ts, v in parsed]
        readings = self.merge(parsed, store.now())
        observed = max((r[2] for r in readings), default=None)
        return readings, observed


# prefijo de los parquet que deja la ingesta en clean/air_reading/ (<fuente>_<dia>.parquet)
SEED_PREFIX = {"air_cm": "aire_dia", "air_ay": "ay_aire"}


def seed_readings(seed_dir, source, since):
    """Lecturas ya normalizadas por la ingesta desde `since`: arranque en frio con las medias de 24 h completas."""
    rows = []
    for path in sorted(Path(seed_dir).glob(f"{SEED_PREFIX[source]}_*.parquet")):
        try:
            t = pq.read_table(path, columns=["station_id", "magnitude", "ts", "value"]).to_pydict()
        except Exception as e:      # un parquet roto no impide arrancar
            log.warning("semilla de aire ilegible (%s): %s", path.name, type(e).__name__)
            continue
        for station, magnitude, ts, value in zip(t["station_id"], t["magnitude"], t["ts"], t["value"]):
            ts = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts     # ns -> pandas.Timestamp
            if ts is not None and ts >= since and value is not None and int(magnitude) in POLLUTANTS:
                rows.append((station, int(magnitude), ts, float(value)))
    return rows


def register_air(store, cfg, seed_dir=None):
    for name in ("air_cm", "air_ay"):
        feed = AirFeed(name, cfg["sources"][name]["url"], cfg["air_buffer_h"])
        if seed_dir is not None:
            now = store.now()
            feed.merge(seed_readings(seed_dir, name, now - timedelta(hours=feed.buffer_h)), now)
        store.register(name, feed.fetch)


def drop_stale_stations(readings, now, max_age_h):
    """Solo las estaciones cuya ultima medicion tiene como mucho max_age_h (el tope es por estacion, no por red)."""
    last = {}
    for station, _, ts, _ in readings:
        last[station] = max(ts, last.get(station, ts))
    oldest = now - timedelta(hours=max_age_h)
    return [r for r in readings if last[r[0]] >= oldest]


def air_categories(readings_lists, start, end, ica, valid_h):
    """Misma salida que Repository.air_categories: {estacion: [(hora, categoria)]} entre start - valid_h y end.

    Media movil de period_hours por contaminante en [ts - (h-1) h, ts], solo si cubre min_coverage de las horas.
    """
    series = {}
    for readings in readings_lists:
        for station, magnitude, ts, value in readings:
            series.setdefault((station, POLLUTANTS[magnitude]), {})[ts] = value
    needed = {p: math.ceil(ica["min_coverage"] * h) for p, h in ica["period_hours"].items()}
    lo = start - timedelta(hours=valid_h)
    measured = {}
    for (station, pollutant), values in series.items():
        if pollutant not in needed:
            continue
        span = timedelta(hours=ica["period_hours"][pollutant] - 1)
        for ts in values:
            if not lo <= ts <= end:
                continue
            window = [v for t, v in values.items() if ts - span <= t <= ts]
            if len(window) >= needed[pollutant]:
                measured.setdefault(station, {}).setdefault(ts, {})[pollutant] = sum(window) / len(window)
    out = {}
    for station, by_ts in measured.items():
        cats = [(ts, aqi_category(v, ica["bands"])) for ts, v in sorted(by_ts.items())]
        cats = [(ts, c) for ts, c in cats if c is not None]
        if cats:
            out[station] = cats
    return out
