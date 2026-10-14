"""Filtros duros: se puede recomendar actividad al aire libre a esta hora y con este perfil?

Umbrales leidos de config/ (ica_thresholds.yaml verificado; rules.yaml decidido por el equipo).
"""
from dataclasses import dataclass, field
from datetime import datetime

CATEGORIES = ("good", "fair", "moderate", "poor", "very_poor", "extremely_poor")
# textos oficiales del BOE para mostrar a la persona
CATEGORY_LABEL = {"good": "Buena", "fair": "Razonablemente buena", "moderate": "Regular",
                  "poor": "Desfavorable", "very_poor": "Muy desfavorable",
                  "extremely_poor": "Extremadamente desfavorable"}


def pollutant_category(pollutant, value, bands):
    if value is None:
        return None
    v = round(value)
    for category, limit in zip(CATEGORIES, bands[pollutant]):
        if v <= limit:
            return category
    return None  # por encima del maximo: dato erroneo (Resolucion de 2020)


def aqi_category(values, bands):
    cats = [pollutant_category(p, v, bands) for p, v in values.items() if p in bands]
    cats = [c for c in cats if c is not None]
    return max(cats, key=CATEGORIES.index) if cats else None


@dataclass
class HourContext:
    hour: datetime
    temperature_c: float | None
    feels_like_c: float | None
    precip_prob: float | None
    aqi_category: str | None


@dataclass
class RuleResult:
    outdoor_ok: bool | None
    reasons: list[str] = field(default_factory=list)


def evaluate_outdoor(ctx, profile, rules):
    reasons, evaluated = [], 0
    air = rules.get("air") or {}
    limit = air.get(profile) or air.get("general")
    if limit and ctx.aqi_category is not None:
        evaluated += 1
        if CATEGORIES.index(ctx.aqi_category) >= CATEGORIES.index(limit):
            reasons.append(f"Calidad del aire {CATEGORY_LABEL[ctx.aqi_category].lower()}")
    max_heat = (rules.get("heat") or {}).get("max_feels_like_c")
    if max_heat is not None and ctx.feels_like_c is not None:
        evaluated += 1
        if ctx.feels_like_c > max_heat:
            reasons.append(f"Calor: sensación térmica de {ctx.feels_like_c:.0f} °C")
    max_rain = (rules.get("rain") or {}).get("max_precip_prob")
    if max_rain is not None and ctx.precip_prob is not None:
        evaluated += 1
        if ctx.precip_prob > max_rain:
            reasons.append(f"Lluvia: {ctx.precip_prob:.0f} % de probabilidad")
    if reasons:
        return RuleResult(False, reasons)
    return RuleResult(True if evaluated else None, [])
