"""Prevision horaria del aire de Copernicus CAMS via Open-Meteo (fila 2): categoria ICA de las horas futuras.

Una sola peticion trae los 179 municipios (los puntos de app/config/forecast_points.csv, nunca la ubicacion de la
persona); Open-Meteo devuelve una lista en el mismo orden. Al descargar se calcula una vez la categoria ICA de cada
municipio y hora con las mismas reglas que el aire medido (live/air.py): media movil de period_hours por
contaminante (O3 8 h, PM 24 h, NO2 1 h) con min_coverage y bandas de ica_thresholds.yaml; la peor manda.
La peticion lleva past_days=1 para que las medias de las primeras horas de hoy esten completas.
El valor horario de CAMS en t se toma como la hora que acaba en t, igual que h01..h24 del aire medido.
"""
import json
import logging
import math
import threading
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path

from engine.rules import aqi_category
from live.store import PortalError

log = logging.getLogger("gomad.api")

# variable horaria de Open-Meteo -> contaminante del ICA (comprobado contra la API real el 17/10/2026, ug/m3)
VARIABLES = {"ozone": "O3", "nitrogen_dioxide": "NO2", "pm10": "PM10", "pm2_5": "PM2_5"}


def _parse_item(item):
    h = item["hourly"]
    times = [datetime.fromisoformat(t) for t in h["time"]]
    out = {}
    for var, pollutant in VARIABLES.items():
        values = h.get(var) or []
        out[pollutant] = {ts: float(v) for ts, v in zip(times, values) if v is not None}
    return out


def parse_response(raw, points):
    """{ine: {contaminante: {hora: valor}}}. La lista viene en el orden de los puntos; si no cuadra, ValueError."""
    doc = json.loads(raw)
    items = doc if isinstance(doc, list) else [doc]
    if len(items) != len(points):
        raise ValueError(f"CAMS devolvio {len(items)} puntos de {len(points)}")
    return {p[0]: _parse_item(item) for p, item in zip(points, items)}


def _moving_means(values, hours, needed):
    """{hora: media} de la ventana [t - (hours-1) h, t], solo si tiene al menos `needed` valores."""
    span = timedelta(hours=hours - 1)
    window, total, out = deque(), 0.0, {}
    for ts in sorted(values):
        window.append((ts, values[ts]))
        total += values[ts]
        while window[0][0] < ts - span:
            total -= window.popleft()[1]
        if len(window) >= needed:
            out[ts] = total / len(window)
    return out


def categories(series, ica):
    """{hora: categoria ICA} de un municipio: la peor de los contaminantes con media valida en esa hora."""
    by_ts = {}
    for pollutant, values in series.items():
        hours = ica["period_hours"].get(pollutant)
        if hours is None:
            continue
        clean = {ts: v for ts, v in values.items() if v is not None}
        needed = math.ceil(ica["min_coverage"] * hours)
        for ts, mean in _moving_means(clean, hours, needed).items():
            by_ts.setdefault(ts, {})[pollutant] = mean
    out = {}
    for ts, means in sorted(by_ts.items()):
        category = aqi_category(means, ica["bands"])
        if category is not None:
            out[ts] = category
    return out


class AirForecastFeed:
    """Como ForecastFeed (live/forecast.py): una peticion por ttl_s como mucho y espera GLOBAL creciente tras fallo."""

    def __init__(self, store, cfg, points, ica, cache_path=None):
        self.store, self.src, self.ica = store, cfg["sources"]["air_forecast"], ica
        self.points = list(points)
        self.cache_path = Path(cache_path) if cache_path else None
        self.data = {}                  # ine -> ({hora: categoria}, descargada)
        self.fetched_at = None
        self.next_try = None
        self.failures = 0
        self.last_error = None
        self.lock = threading.Lock()

    def url(self):
        lats = ",".join(f"{p[2]:.4f}" for p in self.points)
        lons = ",".join(f"{p[3]:.4f}" for p in self.points)
        return f"{self.src['url']}&latitude={lats}&longitude={lons}"

    def step(self):
        """Como mucho una peticion. Devuelve que ha hecho (para pruebas y logs)."""
        now = self.store.now().replace(microsecond=0)
        if self.next_try is not None and now < self.next_try:
            return "wait"
        if self.failures == 0 and self.fetched_at is not None \
                and (now - self.fetched_at).total_seconds() < self.src["ttl_s"]:
            return "idle"
        try:
            if self.store.snapshot:
                raw, _ = self.store.http_get("air_forecast", None, key="cams.json")
            else:
                raw, _ = self.store.http_get("air_forecast", self.url())
            parsed = parse_response(raw, self.points)
        except Exception as e:      # nunca la URL ni el mensaje (llevan las coordenadas): solo codigo o tipo
            result = str(e.status) if isinstance(e, PortalError) else "error"
            self.last_error = f"HTTP {e.status}" if isinstance(e, PortalError) else type(e).__name__
            self.failures += 1
            wait = min(self.src["retry_s"] * 2 ** (self.failures - 1), self.src["retry_max_s"])
            self.next_try = now + timedelta(seconds=wait)
            log.warning("prevision de aire sin descargar: %s (reintento en %d s)", self.last_error, wait)
            return result
        data = {ine: (categories(series, self.ica), now) for ine, series in parsed.items()}
        with self.lock:
            self.data = data
        self.fetched_at, self.next_try, self.failures, self.last_error = now, None, 0, None
        self.save_cache()
        return f"ok:{len(data)}"

    def get(self, ine):
        """({hora: categoria}, descargada) o None si no hay o pasa de max_age_h (salvo en modo grabado)."""
        with self.lock:
            have = self.data.get(ine)
        if have is None:
            return None
        if not self.store.snapshot and self.store.now() - have[1] > timedelta(hours=self.src["max_age_h"]):
            return None
        return have

    # --- cache de arranque (data/live/air_forecast.json) ------------------------------------------------------
    def save_cache(self):
        if self.cache_path is None:
            return
        out = {ine: {"issued": issued.isoformat(), "hours": [[ts.isoformat(), c] for ts, c in sorted(cats.items())]}
               for ine, (cats, issued) in self.data.items()}
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(out), encoding="utf-8")
            tmp.replace(self.cache_path)
        except OSError as e:                            # p. ej. volumen de datos en solo lectura
            log.warning("cache de prevision de aire sin guardar: %s", type(e).__name__)

    def load_cache(self):
        """Carga la cache descartando lo descargado hace mas de max_age_h. Devuelve cuantos municipios carga."""
        if self.cache_path is None or not self.cache_path.exists():
            return 0
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("cache de prevision de aire ilegible: %s", type(e).__name__)
            return 0
        if not isinstance(data, dict):
            return 0
        now, loaded = self.store.now(), {}
        for ine, item in data.items():
            try:
                issued = datetime.fromisoformat(item["issued"])
                cats = {datetime.fromisoformat(ts): c for ts, c in item["hours"]}
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            if now - issued <= timedelta(hours=self.src["max_age_h"]):
                loaded[ine] = (cats, issued)
        with self.lock:
            self.data.update(loaded)
        if loaded:                                      # la cache cuenta para el TTL: no se repite en el arranque
            self.fetched_at = max(v[1] for v in loaded.values())
        return len(loaded)
