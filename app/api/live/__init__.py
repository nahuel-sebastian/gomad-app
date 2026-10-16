"""Datos en vivo (DEC-15): wrappers por fuente (air, forecast) y LiveStore como mediador con cache en memoria."""
import logging

from live.air import register_air
from live.forecast import ForecastFeed, aemet_key
from live.store import LiveStore

log = logging.getLogger("gomad.api")


def build_live(cfg, client, snapshot_dir=None, centers=None, cache_path=None, key=None, air_seed_dir=None):
    """LiveStore con todas las fuentes en vivo registradas (lo usa el arranque de la API).

    centers: () -> [(ine, nombre, lon, lat)] de los 179 municipios (cola de AEMET y prevision del vecino).
    air_seed_dir: clean/air_reading de la ingesta, para empezar con las medias de 24 h tras reiniciar.
    """
    store = LiveStore(cfg, client, snapshot_dir=snapshot_dir)
    register_air(store, cfg, seed_dir=air_seed_dir)
    centers = centers or (lambda: [])

    def safe_centers():
        try:
            return centers()
        except Exception as e:      # sin municipios cargados: solo los pilotos, sin respaldo por cercania
            log.warning("municipios sin cargar para la prevision: %s", type(e).__name__)
            return []
    codes = [c[0] for c in safe_centers()] or cfg["sources"]["forecast"]["pilots"]
    store.forecast = ForecastFeed(store, cfg, codes, centers=safe_centers, cache_path=cache_path,
                                  key=key if key is not None else aemet_key())
    store.forecast.load_cache()
    store.add_task(store.forecast.step)
    return store
