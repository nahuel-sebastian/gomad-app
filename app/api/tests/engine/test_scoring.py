import pytest

from engine.scoring import (FACTORS, air_factor, compute_score, normalize_weights, proximity_factor,
                            weather_factor)

# Pesos de PRUEBA (los reales salen de DEC-07 -> config/weights.yaml)
DEFAULTS = {"proximity": 0.2, "suitability": 0.2, "green": 0.2, "air": 0.2, "weather": 0.2}


def test_proximity():
    assert proximity_factor(0, 3000) == 1.0
    assert proximity_factor(1500, 3000) == pytest.approx(0.5)
    assert proximity_factor(4000, 3000) == 0.0


def test_air_is_monotonic():
    values = [air_factor(c) for c in ("good", "fair", "moderate", "poor", "very_poor", "extremely_poor")]
    assert values == sorted(values, reverse=True)
    assert values[0] == 1.0 and values[-1] == 0.0
    assert air_factor(None) is None


def test_weather():
    assert weather_factor(0) == 1.0 and weather_factor(100) == 0.0 and weather_factor(None) is None


def test_perfect_score_is_10():
    assert compute_score({f: 1.0 for f in FACTORS}, DEFAULTS).value == pytest.approx(10.0)


def test_missing_factor_renormalizes():
    s = compute_score({"proximity": 1.0, "suitability": 1.0, "green": None, "air": 1.0, "weather": 1.0}, DEFAULTS)
    assert s.value == pytest.approx(10.0)
    assert s.by_factor["green"] is None
    assert "green" not in s.effective_weights
    assert sum(s.effective_weights.values()) == pytest.approx(1.0)


def test_all_zero_weights_fall_back():
    weights, warnings = normalize_weights({f: 0.0 for f in FACTORS}, DEFAULTS)
    assert weights == pytest.approx(DEFAULTS)
    assert warnings


def test_weights_are_normalized():
    weights, _ = normalize_weights({"proximity": 1, "suitability": 1, "green": 0, "air": 0, "weather": 0}, DEFAULTS)
    assert weights["proximity"] == pytest.approx(0.5) and sum(weights.values()) == pytest.approx(1.0)


def test_two_people_same_place_different_answer():
    """Guion de la demo (criterio 2.2): mover pesos cambia el orden."""
    near_grey = {"proximity": 1.0, "suitability": 0.8, "green": 0.1, "air": 0.6, "weather": 1.0}
    far_green = {"proximity": 0.4, "suitability": 0.8, "green": 1.0, "air": 0.9, "weather": 1.0}
    hurry, _ = normalize_weights({"proximity": 1, "suitability": 0.2, "green": 0, "air": 0, "weather": 0}, DEFAULTS)
    nature, _ = normalize_weights({"proximity": 0.1, "suitability": 0.2, "green": 1, "air": 1, "weather": 0}, DEFAULTS)
    assert compute_score(near_grey, hurry).value > compute_score(far_green, hurry).value
    assert compute_score(far_green, nature).value > compute_score(near_grey, nature).value


def test_no_factor_available():
    s = compute_score({f: None for f in FACTORS}, DEFAULTS)
    assert s.value == 0.0 and s.effective_weights == {}
