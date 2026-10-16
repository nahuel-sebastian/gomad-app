"""Wrapper de la prevision horaria de AEMET por municipio, con cola, cuota y cache de arranque (DEC-13, DEC-15).

AEMET da 429 a unas 6 peticiones/min y cada municipio son 2 (URL con clave -> URL firmada de datos): no se pide en
cada consulta. Un hilo de fondo llama a step() y recorre la cola: 1.o los municipios pedidos por las personas,
2.o los pilotos, 3.o el resto por codigo. La clave va solo en la cabecera api_key; nunca en logs ni errores.
"""
import json
import logging
import math
import os
import threading
from datetime import datetime, timedelta
from pathlib import Path

import settings
from live.store import PortalError

log = logging.getLogger("gomad.api")


def aemet_key():
    """AEMET_API_KEY del entorno (Compose: env_file) o, si no esta, de app/.env."""
    key = os.environ.get("AEMET_API_KEY")
    if key:
        return key
    path = settings.APP_DIR / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            name, sep, value = line.partition("=")
            if sep and name.strip() == "AEMET_API_KEY":
                return value.strip().strip('"').strip("'") or None
    return None


def decode(raw, content_type=""):
    # AEMET sirve ISO-8859-15 (Content-Type); las muestras de pruebas pueden venir en UTF-8
    if "8859-15" in content_type.lower():
        return raw.decode("iso-8859-15")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("iso-8859-15")


def _float(v):
    s = str(v).strip().replace(",", ".") if v is not None else ""
    if s.lower() == "ip":            # inapreciable
        return 0.0
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _hourly(items, day):
    out = {}
    for e in items or []:
        p = str(e.get("periodo", ""))
        if len(p) == 2 and p.isdigit():
            out[day + timedelta(hours=int(p))] = _float(e.get("value"))
    return out


def _by_band(items, day):
    """probPrecipitacion por franjas de 6 h ('1420' = 14 a 20): cada hora toma la de su franja."""
    out = {}
    for e in items or []:
        p = str(e.get("periodo", ""))
        if len(p) == 4 and p.isdigit():
            start, end = int(p[:2]), int(p[2:]) or 24
            end = end if end > start else end + 24
            for h in range(start, end):
                out[day + timedelta(hours=h)] = _float(e.get("value"))
    return out


def parse_forecast(doc):
    """({hora: (temp, feels_like, precip_prob, precip)}, elaborado). Solo horas con temperatura."""
    days = [(datetime.fromisoformat(d["fecha"][:10]), d) for d in doc["prediccion"]["dia"]]
    # las franjas se unen entre dias: la 2002 de hoy cubre las 00 y 01 de manana (como la ingesta)
    prob = {}
    for day, d in days:
        prob.update(_by_band(d.get("probPrecipitacion"), day))
    series = {}
    for day, d in days:
        temp, feels = _hourly(d.get("temperatura"), day), _hourly(d.get("sensTermica"), day)
        precip = _hourly(d.get("precipitacion"), day)
        for ts, t in temp.items():
            if t is not None:
                series[ts] = (t, feels.get(ts), prob.get(ts), precip.get(ts))
    issued = doc.get("elaborado")
    return series, datetime.fromisoformat(issued) if issued else None


class RateLimiter:
    """Como mucho per_min peticiones en cualquier ventana de 60 s (reloj inyectable)."""

    def __init__(self, per_min, now):
        self.per_min, self.now, self.times = per_min, now, []

    def allow(self, n=1):
        t = self.now()
        self.times = [s for s in self.times if t - s < timedelta(seconds=60)]
        if len(self.times) + n > self.per_min:
            return False
        self.times += [t] * n
        return True


def _km(lon1, lat1, lon2, lat2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


class ForecastFeed:
    def __init__(self, store, cfg, codes, centers=None, cache_path=None, key=None):
        self.store, self.src = store, cfg["sources"]["forecast"]
        self.pilots = [str(p) for p in self.src["pilots"]]
        self.codes = sorted(str(c) for c in codes)
        self.centers = centers or (lambda: [])          # () -> [(ine, nombre, lon, lat)]
        self.cache_path = Path(cache_path) if cache_path else None
        self.key = key
        self.limiter = RateLimiter(self.src["requests_per_min"], store.now)
        self.data = {}                                  # ine -> (serie, elaborado)
        self.attempt = {}                               # ine -> ultimo intento
        self.retry = {}                                 # ine -> hora del reintento tras un 429
        self.requested = set()
        self.lock = threading.Lock()                    # requested lo tocan las peticiones y el hilo de fondo
        self.last_error = None

    # --- cola ------------------------------------------------------------------------------------------------
    def request(self, ines):
        with self.lock:
            self.requested |= {str(i) for i in ines}

    def _log_name(self, ine):
        # privacidad: el municipio que ha pedido una persona no va al log (es su ubicacion aproximada)
        with self.lock:
            return "un municipio pedido" if ine in self.requested else ine

    def _due(self, ine, now):
        if ine in self.retry:
            return now >= self.retry[ine]
        last = self.attempt.get(ine)
        if last is not None and (now - last).total_seconds() < self.src["ttl_s"]:
            return False
        have = self.data.get(ine)
        return have is None or have[1] is None or now - have[1] > timedelta(hours=self.src["refetch_after_h"])

    def next_due(self):
        now, seen = self.store.now(), set()
        with self.lock:
            requested = sorted(self.requested)
        for ine in [*requested, *self.pilots, *self.codes]:
            if ine not in seen and self._due(ine, now):
                return ine
            seen.add(ine)
        return None

    def step(self):
        """Como mucho una descarga (2 peticiones) si la cuota lo permite. Devuelve que ha hecho (para pruebas y logs)."""
        ine = self.next_due()
        if ine is None:
            return "idle"
        if not self.limiter.allow(2):
            return "wait"
        now = self.store.now()
        try:
            self.data[ine] = self._fetch(ine)
        except PortalError as e:
            self.last_error = f"HTTP {e.status}"
            log.warning("prevision de %s sin descargar: HTTP %s", self._log_name(ine), e.status)
            if e.status == 429 and ine not in self.retry:
                self.retry[ine] = now + timedelta(seconds=self.src["retry_429_s"])   # un reintento
                return f"429:{ine}"
            self.retry.pop(ine, None)
            self.attempt[ine] = now                     # a la siguiente vuelta
            return f"{e.status}:{ine}"
        except Exception as e:                          # red, JSON roto: solo el tipo, nunca el mensaje
            self.last_error = type(e).__name__
            log.warning("prevision de %s sin descargar: %s", self._log_name(ine), self.last_error)
            self.retry.pop(ine, None)
            self.attempt[ine] = now
            return f"error:{ine}"
        self.retry.pop(ine, None)
        self.attempt[ine] = now
        with self.lock:
            self.requested.discard(ine)
        self.save_cache()
        return f"ok:{ine}"

    def _fetch(self, ine):
        if self.store.snapshot:
            raw, content_type = self.store.http_get("forecast", None, key=f"{ine}.json")
        else:
            if not self.key:
                raise RuntimeError("falta AEMET_API_KEY")
            meta, _ = self.store.http_get("forecast", self.src["url"].format(ine=ine), headers={"api_key": self.key})
            meta = json.loads(meta)
            if meta.get("estado") != 200 or not meta.get("datos"):
                raise PortalError("forecast", meta.get("estado"))
            raw, content_type = self.store.http_get("forecast", meta["datos"])
        doc = json.loads(decode(raw, content_type))
        return parse_forecast(doc[0] if isinstance(doc, list) else doc)

    # --- lectura ---------------------------------------------------------------------------------------------
    def _fresh(self, ine, now):
        have = self.data.get(ine)
        if have is None or have[1] is None:
            return None
        if self.store.snapshot:          # demo sin red: lo grabado se sirve (la app dice «datos grabados»)
            return have
        return have if now - have[1] <= timedelta(hours=self.src["max_age_h"]) else None

    def get(self, ine):
        """(serie, elaborado, nota) o None. Sin prevision propia: la del municipio mas cercano con prevision."""
        now = self.store.now()
        own = self._fresh(ine, now)
        if own is not None:
            return own[0], own[1], None
        centers = {c[0]: c for c in self.centers()}
        if ine not in centers:
            return None
        _, _, lon, lat = centers[ine]
        best = None
        for other, (_, name, olon, olat) in centers.items():
            have = self._fresh(other, now) if other != ine else None
            if have is None:
                continue
            km = _km(lon, lat, olon, olat)
            if km <= self.src["forecast_fallback_km"] and (best is None or km < best[0]):
                best = (km, have, name)
        if best is None:
            return None
        return best[1][0], best[1][1], f"Previsión de {best[2]}"

    # --- cache de arranque (data/live/forecast.json) ----------------------------------------------------------
    def save_cache(self):
        if self.cache_path is None:
            return
        out = {ine: {"issued": issued.isoformat(), "series": [[ts.isoformat(), *v] for ts, v in sorted(s.items())]}
               for ine, (s, issued) in self.data.items() if issued is not None}
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.cache_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(out), encoding="utf-8")
            tmp.replace(self.cache_path)
        except OSError as e:                            # p. ej. volumen de datos en solo lectura
            log.warning("cache de prevision sin guardar: %s", type(e).__name__)

    def load_cache(self):
        """Carga la cache descartando lo elaborado hace mas de max_age_h. Devuelve cuantos municipios carga."""
        if self.cache_path is None or not self.cache_path.exists():
            return 0
        try:
            data = json.loads(self.cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("cache de prevision ilegible: %s", type(e).__name__)
            return 0
        now, loaded = self.store.now(), 0
        for ine, item in data.items():
            try:
                issued = datetime.fromisoformat(item["issued"])
                series = {datetime.fromisoformat(r[0]): tuple(r[1:]) for r in item["series"]}
            except (KeyError, TypeError, ValueError):
                continue
            if now - issued <= timedelta(hours=self.src["max_age_h"]):
                self.data[ine] = (series, issued)
                self.attempt[ine] = now
                loaded += 1
        return loaded
