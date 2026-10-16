"""Wrapper de la prevision horaria de Open-Meteo para los 179 municipios, con espera global y cache de arranque.

DEC-16 (16/10): sustituye a AEMET. Una sola peticion por refresco trae los 179 municipios (una coordenada por
municipio, la de app/config/forecast_points.csv); Open-Meteo devuelve una lista en el mismo orden. A Open-Meteo
solo van esos puntos, nunca la ubicacion de la persona (CLAUDE.md 2.8). Tras un fallo (429, red) se espera de forma
GLOBAL y creciente (retry_s, el doble en cada fallo seguido, hasta retry_max_s): nunca una peticion por tick.
"""
import csv
import json
import logging
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

import settings
from live.store import PortalError

log = logging.getLogger("gomad.api")


def load_points(path):
    """[(ine, nombre, lat, lon)] de forecast_points.csv, en el orden del fichero."""
    with Path(path).open(encoding="utf-8") as f:
        return [(r["ine_code"], r["name"], float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)]


def _sky_texts():
    src = settings.load("realtime")["sources"]["forecast"]
    name = Path(src.get("weather_codes", "weather_codes.yaml")).stem
    return {int(k): v for k, v in ((settings.load(name) or {}).get("codes") or {}).items()}


def _num(v):
    return None if v is None else float(v)


def parse_open_meteo(item, sky=None):
    """({hora: (temp, feels_like, precip_prob, precip, wind, sky)}, {dia: tmax}). Solo horas con temperatura."""
    sky = _sky_texts() if sky is None else sky
    h = item["hourly"]
    series = {}
    for i, t in enumerate(h["time"]):
        temp = _num(h["temperature_2m"][i])
        if temp is None:
            continue
        code = h["weather_code"][i]
        series[datetime.fromisoformat(t)] = (
            temp, _num(h["apparent_temperature"][i]), _num(h["precipitation_probability"][i]),
            _num(h["precipitation"][i]), _num(h["wind_speed_10m"][i]),
            sky.get(int(code)) if code is not None else None)
    d = item.get("daily") or {}
    day_max = {date.fromisoformat(t): float(v) for t, v in zip(d.get("time", []), d.get("temperature_2m_max", []))
               if v is not None}
    return series, day_max


def parse_response(raw, points):
    """{ine: (serie, tmax por dia)}. La lista viene en el orden de los puntos; si no cuadra, ValueError."""
    doc = json.loads(raw)
    items = doc if isinstance(doc, list) else [doc]
    if len(items) != len(points):
        raise ValueError(f"Open-Meteo devolvio {len(items)} puntos de {len(points)}")
    sky = _sky_texts()
    return {p[0]: parse_open_meteo(item, sky) for p, item in zip(points, items)}


class ForecastFeed:
    def __init__(self, store, cfg, points, cache_path=None):
        self.store, self.src = store, cfg["sources"]["forecast"]
        self.points = list(points)
        self.cache_path = Path(cache_path) if cache_path else None
        self.data = {}                  # ine -> (serie, descargada, tmax por dia)
        self.fetched_at = None          # ultima descarga correcta
        self.next_try = None            # tras un fallo: no antes de esta hora
        self.failures = 0               # fallos seguidos (la espera se duplica en cada uno)
        self.last_error = None
        self.lock = threading.Lock()

    def url(self):
        lats = ",".join(f"{p[2]:.4f}" for p in self.points)
        lons = ",".join(f"{p[3]:.4f}" for p in self.points)
        return f"{self.src['url']}&latitude={lats}&longitude={lons}"

    def step(self):
        """Como mucho una peticion. Devuelve que ha hecho (para pruebas y logs)."""
        now = self.store.now()
        if self.next_try is not None and now < self.next_try:
            return "wait"
        if self.failures == 0 and self.fetched_at is not None \
                and (now - self.fetched_at).total_seconds() < self.src["ttl_s"]:
            return "idle"
        try:
            if self.store.snapshot:
                raw, _ = self.store.http_get("forecast", None, key="open_meteo.json")
            else:
                raw, _ = self.store.http_get("forecast", self.url())
            parsed = parse_response(raw, self.points)
        except Exception as e:      # nunca la URL ni el mensaje (llevan las coordenadas): solo codigo o tipo
            result = str(e.status) if isinstance(e, PortalError) else "error"
            self.last_error = f"HTTP {e.status}" if isinstance(e, PortalError) else type(e).__name__
            self.failures += 1
            wait = min(self.src["retry_s"] * 2 ** (self.failures - 1), self.src["retry_max_s"])
            self.next_try = now + timedelta(seconds=wait)
            log.warning("prevision sin descargar: %s (reintento en %d s)", self.last_error, wait)
            return result
        with self.lock:
            self.data = {ine: (series, now, day_max) for ine, (series, day_max) in parsed.items()}
        self.fetched_at, self.next_try, self.failures, self.last_error = now, None, 0, None
        self.save_cache()
        return f"ok:{len(parsed)}"

    # --- lectura ---------------------------------------------------------------------------------------------
    def get(self, ine):
        """(serie, descargada, tmax por dia) o None si no hay o pasa de max_age_h (salvo en modo grabado)."""
        with self.lock:
            have = self.data.get(ine)
        if have is None:
            return None
        if not self.store.snapshot and self.store.now() - have[1] > timedelta(hours=self.src["max_age_h"]):
            return None
        return have

    # --- cache de arranque (data/live/forecast.json) ----------------------------------------------------------
    def save_cache(self):
        if self.cache_path is None:
            return
        out = {ine: {"issued": issued.isoformat(),
                     "series": [[ts.isoformat(), *v] for ts, v in sorted(s.items())],
                     "day_max": {d.isoformat(): t for d, t in sorted(day_max.items())}}
               for ine, (s, issued, day_max) in self.data.items()}
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(out), encoding="utf-8")
            tmp.replace(self.cache_path)
        except OSError as e:                            # p. ej. volumen de datos en solo lectura
            log.warning("cache de prevision sin guardar: %s", type(e).__name__)

    def load_cache(self):
        """Carga la cache descartando lo descargado hace mas de max_age_h. Devuelve cuantos municipios carga."""
        if self.cache_path is None or not self.cache_path.exists():
            return 0
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("cache de prevision ilegible: %s", type(e).__name__)
            return 0
        now, loaded = self.store.now(), {}
        for ine, item in data.items():
            try:
                issued = datetime.fromisoformat(item["issued"])
                series = {datetime.fromisoformat(r[0]): tuple(r[1:]) for r in item["series"]}
                day_max = {date.fromisoformat(d): t for d, t in (item.get("day_max") or {}).items()}
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            if now - issued <= timedelta(hours=self.src["max_age_h"]):
                loaded[ine] = (series, issued, day_max)
        with self.lock:
            self.data.update(loaded)
        if loaded:                                      # la cache cuenta para el TTL: no se repite en el arranque
            self.fetched_at = max(v[1] for v in loaded.values())
        return len(loaded)
