"""LiveStore: cache en memoria de los datos que caducan en horas (aire, prevision), con TTL y validez maxima.

Las peticiones solo leen (get); un hilo de fondo refresca cada fuente. Nunca se sirve un dato cuyo observed_at
sea mas viejo que max_age_h, aunque el portal este caido (DEC-15). Sin persistencia en disco.
"""
import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

log = logging.getLogger("gomad.api")

REQUIRED = ("ttl_s", "max_age_h", "timeout_s")
RETRY_FAILED_S = 60          # tras un fallo se reintenta como mucho cada minuto (o antes si el TTL es menor)


class PortalError(Exception):
    """Respuesta HTTP distinta de 200. Solo lleva la fuente y el codigo: nunca la URL (puede llevar datos)."""

    def __init__(self, source, status):
        super().__init__(f"{source}: HTTP {status}")
        self.source, self.status = source, status


@dataclass
class Entry:
    value: object
    observed_at: datetime | None     # hora del dato (no de la descarga), local sin zona
    fetched_at: datetime             # ultimo intento de descarga
    status: str                      # ok | stale | failed
    last_error: str | None = None    # solo el tipo de error, sin mensaje


def validate_realtime(cfg):
    """Un realtime.yaml erroneo para el arranque, con un mensaje que nombra la fuente."""
    sources = (cfg or {}).get("sources")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("realtime.yaml: falta la seccion «sources»")
    for name, src in sources.items():
        for key in REQUIRED:
            value = (src or {}).get(key)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise ValueError(f"realtime.yaml: a la fuente «{name}» le falta {key} (número > 0)")


class LiveStore:
    def __init__(self, cfg, client=None, now=None, snapshot_dir=None):
        self.cfg = cfg
        self.sources = cfg["sources"]
        self.client = client
        self.now = now or datetime.now
        self.snapshot_dir = Path(snapshot_dir) if snapshot_dir else None
        self._fetchers, self._entries, self._locks, self._tasks = {}, {}, {}, []
        self._stop = threading.Event()
        self._thread = None

    @property
    def snapshot(self):
        return self.snapshot_dir is not None

    def register(self, name, fetch):
        """fetch(store) -> (valor, observed_at). name debe estar en realtime.yaml."""
        if name not in self.sources:
            raise KeyError(f"realtime.yaml no tiene la fuente «{name}»")
        self._fetchers[name] = fetch
        self._locks[name] = threading.Lock()

    def add_task(self, step):
        """Paso periodico extra del hilo de fondo (la cola de AEMET)."""
        self._tasks.append(step)

    def refresh(self, name):
        """Descarga si toca. False si no tocaba o si ya habia una descarga en marcha de esa fuente."""
        lock = self._locks[name]
        if not lock.acquire(blocking=False):
            return False
        try:
            now, old = self.now(), self._entries.get(name)
            ttl = self.sources[name]["ttl_s"]
            if old is not None:
                wait = ttl if old.status == "ok" else min(ttl, RETRY_FAILED_S)
                if (now - old.fetched_at).total_seconds() < wait:
                    return False
            try:
                value, observed_at = self._fetchers[name](self)
            except Exception as e:      # portal caido, timeout, formato roto: se conserva lo ultimo valido
                error = type(e).__name__
                log.warning("fuente %s sin refrescar: %s", name, error)
                if old is not None and old.value is not None:
                    old.status, old.last_error, old.fetched_at = "stale", error, now
                else:
                    self._entries[name] = Entry(None, None, now, "failed", error)
                return False
            self._entries[name] = Entry(value, observed_at, now, "ok")
            return True
        finally:
            lock.release()

    def entry(self, name):
        return self._entries.get(name)

    def get(self, name):
        """Entrada valida o None: sin dato, o dato observado hace mas de max_age_h (salvo en modo instantanea)."""
        e = self._entries.get(name)
        if e is None or e.value is None or e.observed_at is None:
            return None
        if not self.snapshot and e.observed_at < self.now() - timedelta(hours=self.sources[name]["max_age_h"]):
            return None
        return e

    def http_get(self, source, url, headers=None, key="data"):
        """(bytes, content-type). En modo instantanea lee snapshot_dir/<source>/<key> y no abre conexiones."""
        if self.snapshot:
            return (self.snapshot_dir / source / key).read_bytes(), ""
        r = self.client.get(url, headers=headers or {}, timeout=self.sources[source]["timeout_s"])
        if r.status_code != 200:
            raise PortalError(source, r.status_code)
        return r.content, r.headers.get("content-type", "")

    # --- hilo de fondo ---------------------------------------------------------------------------------------
    def _loop(self):
        while not self._stop.is_set():
            for name in list(self._fetchers):
                self.refresh(name)
            for step in self._tasks:
                try:
                    step()
                except Exception as e:      # un paso roto no para el hilo
                    log.warning("tarea en vivo fallida: %s", type(e).__name__)
            self._stop.wait(self.cfg.get("tick_s", 5))

    def start(self):
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="gomad-live", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
