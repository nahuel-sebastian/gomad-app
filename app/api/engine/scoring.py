"""Puntuacion ponderada 0-10 (RF-07). Factores normalizados 0-1; None = sin datos (no cuenta)."""
from dataclasses import dataclass

from engine.rules import CATEGORIES

FACTORS = ("proximity", "suitability", "green", "air", "weather")


def normalize_weights(weights, defaults):
    warnings = []
    weights = {f: float((weights or {}).get(f, 0.0)) for f in FACTORS} if weights else dict(defaults)
    total = sum(weights.values())
    if total <= 0:
        warnings.append("Todos los pesos estaban a cero: se usan los pesos por defecto.")
        weights, total = dict(defaults), sum(defaults.values())
    return {f: weights[f] / total for f in FACTORS}, warnings


def proximity_factor(distance_m, max_distance_m):
    if max_distance_m <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance_m / max_distance_m))


def air_factor(category):
    if category is None:
        return None
    return 1.0 - CATEGORIES.index(category) / (len(CATEGORIES) - 1)


def weather_factor(precip_prob):
    if precip_prob is None:
        return None
    return max(0.0, min(1.0, 1.0 - precip_prob / 100.0))


@dataclass
class Score:
    value: float
    by_factor: dict
    effective_weights: dict


def compute_score(factors, weights):
    available = {f: v for f, v in factors.items() if v is not None and weights.get(f, 0) > 0}
    total = sum(weights[f] for f in available)
    if total <= 0:
        return Score(0.0, {f: factors.get(f) for f in FACTORS}, {})
    effective = {f: weights[f] / total for f in available}
    value = 10.0 * sum(effective[f] * available[f] for f in available)
    return Score(round(value, 2), {f: factors.get(f) for f in FACTORS}, effective)
