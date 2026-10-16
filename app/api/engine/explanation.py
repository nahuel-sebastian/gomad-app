"""Explicaciones en lenguaje llano con plantillas (RF-10, V-M2). Sin IA: solo cifras que ya estan en la respuesta."""
from dataclasses import dataclass, field
from datetime import datetime

from engine.rules import CATEGORY_LABEL

FACTOR_LABEL = {"proximity": "cercanía", "suitability": "adecuación a la actividad", "green": "zona verde",
                "air": "calidad del aire", "weather": "tiempo"}


def fmt_number(value, decimals=1):
    return f"{value:.{decimals}f}".replace(".", ",")


def fmt_distance(meters):
    if meters < 1000:
        return f"{round(meters / 10) * 10:.0f} m"
    return f"{fmt_number(meters / 1000)} km"


def fmt_minutes(minutes):
    return f"{max(1, round(minutes))} min"


def fmt_hour(dt):
    return dt.strftime("%H:%M")


def fmt_date(dt):
    return dt.strftime("%d/%m a las %H:%M")


def factor_text(factor, value, *, distance_m=None, green=None, aqi_category=None, precip_prob=None, covered=False):
    if factor == "proximity":
        return f"Cercanía: a {fmt_distance(distance_m)}"
    if factor == "suitability":
        return f"Adecuación a la actividad: {fmt_number(value)} sobre 10"
    if factor == "green":
        return "Verde: sin datos en este municipio" if green is None else f"Verde: {round(green * 100)} % de zona verde alrededor"
    if factor == "air":
        if covered:
            return "Aire: no cuenta en un sitio cubierto"
        return "Aire: sin medición reciente" if aqi_category is None else f"Aire: {CATEGORY_LABEL[aqi_category].lower()}"
    if factor == "weather":
        if covered:
            return "Tiempo: no cuenta en un sitio cubierto"
        return "Tiempo: sin previsión" if precip_prob is None else f"Lluvia: {round(precip_prob)} % de probabilidad"
    raise ValueError(f"Factor desconocido: {factor}")


@dataclass
class ExplanationInput:
    name: str
    distance_m: float
    duration_min: float
    score: float
    factors: list                      # [(factor, valor 0-10 o None, peso efectivo)]
    first: object | None               # HourResult de la primera hora de la ventana
    best: object | None                # HourResult de la mejor hora
    indoor_alternative: bool = False
    activity_label: str | None = None  # «Sorprendeme»: actividad propuesta
    own_criterion_rule: bool = False   # la regla que bloquea la primera hora no tiene fuente oficial
    sources: list = field(default_factory=list)   # [(etiqueta, fecha o None)]
    approximate_distance: bool = False


def _lower_first(text):
    return text[:1].lower() + text[1:]


def explain(x):
    parts = []
    blocked = x.first is not None and x.first.outdoor_ok is False
    reasons = "; ".join(_lower_first(r) for r in x.first.reasons) if blocked else ""
    mark = " (umbral de criterio propio)" if blocked and x.own_criterion_rule else ""
    if x.best is None:
        parts.append(f"Ahora no se recomienda al aire libre en toda la ventana elegida ({reasons}{mark})" if blocked
                     else "Sin datos para elegir la mejor hora")
    elif blocked and x.best.hour != x.first.hour:
        parts.append(f"Ahora no: mejor a las {fmt_hour(x.best.hour)} ({reasons}{mark})")
    else:
        parts.append(f"Mejor hora: {fmt_hour(x.best.hour)}")
    approx = " aprox." if x.approximate_distance else ""
    where = f"{x.name}, a {fmt_distance(x.distance_m)}{approx} ({fmt_minutes(x.duration_min)} a pie)"
    if x.activity_label:
        where = f"Para {x.activity_label.lower()}: {where}"
    parts.append(f"{where}; nota {fmt_number(x.score)} sobre 10")
    ranked = sorted(((w * v, f) for f, v, w in x.factors if v is not None and w > 0), reverse=True)
    dominant = [f for contribution, f in ranked[:2] if contribution > 0]
    if dominant:
        parts.append("Destaca por " + " y ".join(FACTOR_LABEL[f] for f in dominant))
    if x.indoor_alternative:
        parts.append("Es un sitio cubierto: alternativa por lluvia, calor o mal aire")
    if x.sources:
        parts.append("Fuentes: " + "; ".join(f"{label} ({fmt_date(d)})" if d else label for label, d in x.sources))
    return ". ".join(parts) + "."


def route_description(distance_m, duration_min, green_pct, traffic_m, counts, approximate=False):
    if approximate:
        return (f"Línea recta de {fmt_distance(distance_m)} ({fmt_minutes(duration_min)} a pie, aproximada): "
                "no hay red peatonal cargada para este trayecto.")
    parts = [fmt_distance(distance_m), f"{fmt_minutes(duration_min)} a pie",
             "sin datos de zona verde" if green_pct is None else f"{round(green_pct)} % por zona verde",
             f"{fmt_distance(traffic_m)} junto a tráfico" if traffic_m > 0 else "sin tramos con tráfico"]
    for key, one, many in (("fountain", "fuente", "fuentes"), ("bench", "banco", "bancos"),
                           ("aed", "desfibrilador", "desfibriladores")):
        n = counts.get(key, 0)
        if n:
            parts.append(f"{n} {one if n == 1 else many}")
    return ", ".join(parts)
