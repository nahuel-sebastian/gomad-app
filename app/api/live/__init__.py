"""Datos en vivo (DEC-15): wrappers por fuente (air, forecast) y LiveStore como mediador con cache en memoria."""
from live.air import register_air
from live.store import LiveStore


def build_live(cfg, client, snapshot_dir=None):
    """LiveStore con todas las fuentes en vivo registradas (lo usa el arranque de la API)."""
    store = LiveStore(cfg, client, snapshot_dir=snapshot_dir)
    register_air(store, cfg)
    return store
