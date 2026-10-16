"""Wrapper del aire medido: aire_dia (CKAN Comunidad) y ay_aire (Ayuntamiento), mismo formato H/V.

Reescribe en la API lo que hacen ingest/normalize/air.py y build_db.create_aqi_hourly (ningun servicio importa
codigo de otro): formato largo con la validacion del origen, medias moviles del ICA y categoria por hora.
"""
import csv
import io
import math
from datetime import datetime, timedelta

from engine.rules import aqi_category

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
            municipality, station = int(r["municipio"]), int(r["estacion"])
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
        readings = self.merge(parse_air_csv(decode(content)), store.now())
        observed = max((r[2] for r in readings), default=None)
        return readings, observed


def register_air(store, cfg):
    for name in ("air_cm", "air_ay"):
        feed = AirFeed(name, cfg["sources"][name]["url"], cfg["air_buffer_h"])
        store.register(name, feed.fetch)


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
