from datetime import datetime

from engine.rules import HourContext
from engine.slots import MAX_WINDOW_HOURS, best_hour, evaluate_hours, needs_indoor, window_hours

RULES = {"air": {"general": "poor"}, "heat": {"max_feels_like_c": 30.0}, "rain": {"max_precip_prob": 50}}
WEIGHTS = {"proximity": 0.2, "suitability": 0.2, "green": 0.2, "air": 0.2, "weather": 0.2}
FIXED = {"proximity": 0.8, "suitability": 1.0, "green": 0.7}


def ctx(h, feels=25.0, rain=0.0, aqi="good", day=15):
    return HourContext(datetime(2026, 7, day, h), feels, feels, rain, aqi)


def test_window_hours():
    assert window_hours(datetime(2026, 7, 15, 18, 20), datetime(2026, 7, 15, 21, 0)) == [
        datetime(2026, 7, 15, 18), datetime(2026, 7, 15, 19), datetime(2026, 7, 15, 20)]


def test_window_crosses_midnight():
    w = window_hours(datetime(2026, 7, 15, 22), datetime(2026, 7, 16, 1))
    assert w == [datetime(2026, 7, 15, 22), datetime(2026, 7, 15, 23), datetime(2026, 7, 16, 0)]


def test_carmen_best_late_evening():
    contexts = {c.hour: c for c in [ctx(17, feels=36), ctx(18, feels=34), ctx(19, feels=31), ctx(20, feels=28)]}
    res = evaluate_hours(contexts, list(contexts), False, "general", RULES, FIXED, WEIGHTS)
    assert best_hour(res).hour == datetime(2026, 7, 15, 20)
    assert not needs_indoor(res)


def test_all_unviable_suggests_indoor():
    contexts = {c.hour: c for c in [ctx(17, feels=36), ctx(18, feels=35)]}
    res = evaluate_hours(contexts, list(contexts), False, "general", RULES, FIXED, WEIGHTS)
    assert needs_indoor(res)
    assert best_hour(res) is None


def test_covered_destination_ignores_heat():
    contexts = {c.hour: c for c in [ctx(17, feels=36)]}
    res = evaluate_hours(contexts, list(contexts), True, "general", RULES, FIXED, WEIGHTS)
    assert res[0].outdoor_ok is None and res[0].score is not None


def test_hours_without_forecast():
    contexts = {datetime(2026, 7, 15, 18): ctx(18)}
    window = [datetime(2026, 7, 15, 18), datetime(2026, 7, 15, 19)]
    res = evaluate_hours(contexts, window, False, "general", RULES, FIXED, WEIGHTS)
    assert res[1].score is None and "Sin previsión" in res[1].reasons[0]
    assert best_hour(res).hour == datetime(2026, 7, 15, 18)


def test_worse_air_lowers_score():
    contexts = {c.hour: c for c in [ctx(8, aqi="good"), ctx(9, aqi="moderate")]}
    res = evaluate_hours(contexts, list(contexts), False, "general", RULES, FIXED, WEIGHTS)
    assert res[0].score > res[1].score


def test_no_weighted_factor_available_is_not_a_silent_zero():
    """Cubierto con todo el peso en aire: no hay factor evaluable -> sin nota y con motivo, no 0."""
    contexts = {c.hour: c for c in [ctx(17)]}
    only_air = {"proximity": 0.0, "suitability": 0.0, "green": 0.0, "air": 1.0, "weather": 0.0}
    res = evaluate_hours(contexts, list(contexts), True, "general", RULES, FIXED, only_air)
    assert res[0].score is None and res[0].reasons
    assert best_hour(res) is None


def test_past_hours_are_not_offered():
    w = window_hours(datetime(2026, 7, 15, 9), datetime(2026, 7, 15, 21), now=datetime(2026, 7, 15, 19, 20))
    assert w == [datetime(2026, 7, 15, 19), datetime(2026, 7, 15, 20)]


def test_window_is_capped():
    w = window_hours(datetime(2026, 7, 15, 0), datetime(9999, 1, 1))
    assert len(w) == MAX_WINDOW_HOURS
