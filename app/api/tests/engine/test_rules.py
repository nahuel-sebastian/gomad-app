from datetime import datetime

import pytest

from engine.rules import (CATEGORIES, HourContext, aqi_category, evaluate_outdoor, load_heat_zones,
                          pollutant_category, validate_rules)
from settings import CONFIG_DIR, load

BANDS = load("ica_thresholds")["bands"]

# Reglas de PRUEBA (no son las decididas; esas van en config/rules.yaml tras DEC-05/06/07b)
HEAT = {
    "zones": {"722801": {"name": "Sierra de Madrid", "max_temp_c": 35.8},
              "722802": {"name": "Metropolitana y Henares", "max_temp_c": 37.4},
              "722803": {"name": "Sur, Vegas y Oeste", "max_temp_c": 39.2}},
    "zone_table": "heat_zones.csv",
    "risk_profiles": ["senior", "stroller"],
    "risk_companions": ["kids"],
    "avoid_hours": [14, 19],
    "tiebreak": "feels_like",
}
RULES = {
    "air": {"general": "poor", "sensitive": "moderate"},
    "heat": HEAT,
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


def test_rain():
    assert evaluate_outdoor(ctx(precip_prob=80), "general", RULES).outdoor_ok is False


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
                    "heat": None,
                    "rain": {"max_precip_prob": None, "own_criterion": True}})


@pytest.mark.parametrize("rules", [
    {"air": {"general": "bad"}},
    {"air": {"general": "poor", "senior": "Desfavorable"}},
    {"heat": {**HEAT, "zones": {**HEAT["zones"], "722801": {"name": "Sierra", "max_temp_c": "treinta"}}}},
    {"heat": {**HEAT, "avoid_hours": [19, 14]}},
    {"heat": {**HEAT, "avoid_hours": [14, 25]}},
    {"heat": {**HEAT, "zones": {"722801": HEAT["zones"]["722801"]}}},
    {"rain": {"max_precip_prob": 150}},
    {"rain": {"max_precip_prob": -1}},
])
def test_invalid_rules_fail_validation(rules):
    with pytest.raises(ValueError):
        validate_rules(rules)


def test_air_meta_key_own_criterion_profiles_is_not_a_profile():
    rules = {"air": {"general": "poor", "own_criterion": True, "own_criterion_profiles": ["senior"]}}
    validate_rules(rules)                      # no debe tomarlo por un perfil con categoria invalida
    ctx = HourContext(datetime(2026, 7, 15, 10), 20, 20, 0, "poor")
    assert evaluate_outdoor(ctx, "own_criterion_profiles", rules).outdoor_ok is False   # cae a general


def test_real_rules_and_zone_table_are_valid():
    rules = load("rules")
    zones = load_heat_zones(CONFIG_DIR / rules["heat"]["zone_table"])
    validate_rules(rules, zones)
    assert len(zones) == 179 and zones["28065"] == "722802"
    assert rules["heat"]["zones"]["722802"]["max_temp_c"] == 37.4
    assert "max_feels_like_c" not in rules["heat"]


def test_zone_table_must_cover_179():
    with pytest.raises(ValueError):
        validate_rules({"heat": HEAT}, {"28065": "722802"})


def test_zone_table_with_unknown_zone_fails():
    zones = {f"28{i:03d}": "722802" for i in range(1, 180)} | {"28065": "999999"}
    with pytest.raises(ValueError):
        validate_rules({"heat": HEAT}, zones)
