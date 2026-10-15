from datetime import datetime

import pytest

from engine.rules import (CATEGORIES, HourContext, aqi_category, evaluate_outdoor, pollutant_category,
                          validate_rules)
from settings import load

BANDS = load("ica_thresholds")["bands"]

# Reglas de PRUEBA (no son las decididas; esas van en config/rules.yaml tras DEC-05/06/07b)
RULES = {
    "air": {"general": "poor", "sensitive": "moderate"},
    "heat": {"max_feels_like_c": 30.0},
    "rain": {"max_precip_prob": 50},
}


@pytest.mark.parametrize("value,expected", [
    (0, "good"), (40, "good"), (40.4, "good"), (40.6, "fair"), (41, "fair"),
    (90, "fair"), (91, "moderate"), (120, "moderate"), (121, "poor"),
    (230, "poor"), (231, "very_poor"), (341, "extremely_poor"), (1000, "extremely_poor"),
])
def test_no2_band_limits(value, expected):
    assert pollutant_category("NO2", value, BANDS) == expected


@pytest.mark.parametrize("value,expected", [(50, "good"), (51, "fair"), (130, "moderate"),
                                            (131, "poor"), (241, "very_poor")])
def test_o3_band_limits(value, expected):
    assert pollutant_category("O3", value, BANDS) == expected


def test_above_max_is_discarded():
    assert pollutant_category("NO2", 1001, BANDS) is None


def test_missing_value_is_none():
    assert pollutant_category("PM10", None, BANDS) is None


def test_aqi_is_worst_category():
    assert aqi_category({"NO2": 30, "O3": 135, "PM10": None}, BANDS) == "poor"


def test_aqi_without_any_data():
    assert aqi_category({"NO2": None, "O3": None}, BANDS) is None


def ctx(**kw):
    base = dict(hour=datetime(2026, 7, 15, 18), temperature_c=25.0, feels_like_c=25.0,
                precip_prob=0.0, aqi_category="good")
    base.update(kw)
    return HourContext(**base)


def test_moderate_air_blocks_sensitive_not_general():
    assert evaluate_outdoor(ctx(aqi_category="moderate"), "sensitive", RULES).outdoor_ok is False
    assert evaluate_outdoor(ctx(aqi_category="moderate"), "general", RULES).outdoor_ok is True


def test_lucia_high_ozone():
    r = evaluate_outdoor(ctx(aqi_category="poor"), "sensitive", RULES)
    assert r.outdoor_ok is False
    assert any("aire" in reason.lower() for reason in r.reasons)


def test_carmen_36_degrees():
    r = evaluate_outdoor(ctx(temperature_c=36.0, feels_like_c=37.0), "general", RULES)
    assert r.outdoor_ok is False
    assert any("calor" in reason.lower() for reason in r.reasons)


def test_rain():
    assert evaluate_outdoor(ctx(precip_prob=80), "general", RULES).outdoor_ok is False


def test_disabled_rule_does_not_block():
    rules = {**RULES, "heat": {"max_feels_like_c": None}}
    assert evaluate_outdoor(ctx(feels_like_c=45.0), "general", rules).outdoor_ok is True


def test_profile_without_rule_uses_general():
    assert evaluate_outdoor(ctx(aqi_category="poor"), "stroller", RULES).outdoor_ok is False


def test_no_data_at_all_is_undetermined():
    r = evaluate_outdoor(ctx(feels_like_c=None, temperature_c=None, precip_prob=None, aqi_category=None),
                         "general", RULES)
    assert r.outdoor_ok is None


def test_categories_in_order():
    assert CATEGORIES[0] == "good" and CATEGORIES[-1] == "extremely_poor"


def test_half_rounds_up():
    # la tabla del BOE es de enteros: 40,5 se redondea a 41 (no al par, como hace round())
    assert pollutant_category("NO2", 40.5, BANDS) == "fair"
    assert pollutant_category("NO2", 120.5, BANDS) == "poor"


def test_profile_with_null_air_rule_disables_it():
    rules = {**RULES, "air": {"general": "poor", "stroller": None}}
    assert evaluate_outdoor(ctx(aqi_category="poor"), "stroller", rules).outdoor_ok is True
    assert evaluate_outdoor(ctx(aqi_category="poor"), "general", rules).outdoor_ok is False


def test_air_metadata_keys_are_not_profiles():
    rules = {**RULES, "air": {"general": "poor", "source": "BOE-A-2020-10426"}}
    assert evaluate_outdoor(ctx(aqi_category="poor"), "source", rules).outdoor_ok is False


def test_valid_rules_pass_validation():
    validate_rules(RULES)
    validate_rules({"air": {"general": "poor", "senior": None, "source": "BOE"},
                    "heat": {"max_feels_like_c": None, "source": None, "own_criterion": False},
                    "rain": {"max_precip_prob": None, "own_criterion": True}})


@pytest.mark.parametrize("rules", [
    {"air": {"general": "bad"}},
    {"air": {"general": "poor", "senior": "Desfavorable"}},
    {"heat": {"max_feels_like_c": "treinta"}},
    {"rain": {"max_precip_prob": 150}},
    {"rain": {"max_precip_prob": -1}},
])
def test_invalid_rules_fail_validation(rules):
    with pytest.raises(ValueError):
        validate_rules(rules)
