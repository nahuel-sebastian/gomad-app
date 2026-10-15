import re
from datetime import datetime

from engine.explanation import (ExplanationInput, explain, factor_text, fmt_distance, fmt_minutes, fmt_number,
                                route_description)
from engine.slots import HourResult

H = lambda h: datetime(2026, 7, 15, h)


def carmen(**kw):
    first = HourResult(H(17), None, False, ["Calor: sensación térmica de 36 °C"])
    best = HourResult(H(20), 8.2, True)
    base = dict(name="Parque Uno", distance_m=1234.0, duration_min=16.4, score=8.26,
                factors=[("proximity", 7.0, 0.3), ("green", 8.0, 0.2), ("air", 10.0, 0.15), ("weather", None, 0.0)],
                first=first, best=best)
    return ExplanationInput(**{**base, **kw})


def test_formats():
    assert fmt_number(8.26) == "8,3" and fmt_distance(840) == "840 m" and fmt_distance(1234) == "1,2 km"
    assert fmt_minutes(16.4) == "16 min" and fmt_minutes(0.2) == "1 min"


def test_carmen_now_no_better_later():
    text = explain(carmen())
    assert text.startswith("Ahora no: mejor a las 20:00 (calor: sensación térmica de 36 °C)")


def test_numbers_in_sentence_come_from_object():
    text = explain(carmen())
    assert set(re.findall(r"\d+(?:,\d+)?", text)) == {"20", "00", "36", "1,2", "16", "8,3", "10"}
    assert "Destaca por zona verde y cercanía" in text or "Destaca por cercanía y zona verde" in text


def test_best_hour_now():
    text = explain(carmen(first=HourResult(H(20), 8.2, True), best=HourResult(H(20), 8.2, True)))
    assert text.startswith("Mejor hora: 20:00")


def test_no_viable_hour():
    text = explain(carmen(best=None))
    assert text.startswith("Ahora no se recomienda al aire libre en toda la ventana elegida (calor")


def test_own_criterion_is_marked():
    assert "(umbral de criterio propio)" in explain(carmen(own_criterion_rule=True))
    assert "criterio propio" not in explain(carmen())


def test_surprise_activity_indoor_and_sources():
    text = explain(carmen(activity_label="Nadar", indoor_alternative=True,
                          sources=[("Previsión horaria (AEMET)", datetime(2026, 7, 15, 12, 1)), ("Aire", None)],
                          approximate_distance=True))
    assert "Para nadar: Parque Uno, a 1,2 km aprox. (16 min a pie)" in text
    assert "Es un sitio cubierto" in text
    assert text.endswith("Fuentes: Previsión horaria (AEMET) (15/07 a las 12:01); Aire.")


def test_factor_texts():
    assert factor_text("proximity", 7.0, distance_m=850) == "Cercanía: a 850 m"
    assert factor_text("green", None, green=None) == "Verde: sin datos en este municipio"
    assert factor_text("green", 6.5, green=0.65) == "Verde: 65 % de zona verde alrededor"
    assert factor_text("air", 8.0, aqi_category="fair") == "Aire: razonablemente buena"
    assert factor_text("air", None) == "Aire: sin medición reciente"
    assert factor_text("air", None, covered=True) == "Aire: no cuenta en un sitio cubierto"
    assert factor_text("weather", 7.0, precip_prob=30) == "Lluvia: 30 % de probabilidad"
    assert factor_text("suitability", 9.0) == "Adecuación a la actividad: 9,0 sobre 10"


def test_route_description():
    text = route_description(2430, 32.4, 68.2, 350, {"fountain": 2, "bench": 1, "aed": 0})
    assert text == "2,4 km, 32 min a pie, 68 % por zona verde, 350 m junto a tráfico, 2 fuentes, 1 banco"
    assert "sin datos de zona verde" in route_description(500, 7, None, 0, {})
    assert "sin tramos con tráfico" in route_description(500, 7, None, 0, {})
    assert route_description(800, 11, None, 0, {}, approximate=True).startswith("Línea recta de 800 m")
