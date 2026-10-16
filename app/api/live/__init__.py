"""Datos en vivo (DEC-15): wrappers por fuente (air, forecast) y LiveStore como mediador con cache en memoria."""
from live.air import register_air
from live.forecast import ForecastFeed, load_points
from live.store import LiveStore

import settings


def build_live(cfg, client, snapshot_dir=None, cache_path=None, air_seed_dir=None):
    """LiveStore con todas las fuentes en vivo registradas (lo usa el arranque de la API).

    La prevision (Open-Meteo, DEC-16) se pide para los puntos de config/forecast_points.csv, nunca para la
    ubicacion de la persona. air_seed_dir: clean/air_reading de la ingesta, para las medias de 24 h tras reiniciar.
    """
    store = LiveStore(cfg, client, snapshot_dir=snapshot_dir)
    register_air(store, cfg, seed_dir=air_seed_dir)
    points = load_points(settings.CONFIG_DIR / cfg["sources"]["forecast"]["points"])
    store.forecast = ForecastFeed(store, cfg, points, cache_path=cache_path)
    store.forecast.load_cache()
    store.add_task(store.forecast.step)
    return store
