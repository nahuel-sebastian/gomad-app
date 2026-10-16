"""Filtros duros: se puede recomendar actividad al aire libre a esta hora y con este perfil?

Umbrales leidos de config/ (ica_thresholds.yaml verificado; rules.yaml decidido por el equipo).
"""
import csv
import math
from dataclasses import dataclass, field
from datetime import datetime

CATEGORIES = ("good", "fair", "moderate", "poor", "very_poor", "extremely_poor")
# textos oficiales del BOE para mostrar a la persona
CATEGORY_LABEL = {"good": "Buena", "fair": "Razonablemente buena", "moderate": "Regular",
                  "poor": "Desfavorable", "very_poor": "Muy desfavorable",
                  "extremely_poor": "Extremadamente desfavorable"}
# claves de rules.yaml -> air que no son perfiles
AIR_META_KEYS = ("source", "own_criterion", "own_criterion_profiles")
# zonas meteosalud de la Comunidad de Madrid (Plan de Sanidad 2026, Anexo I); sus umbrales van en rules.yaml
HEAT_ZONES = ("722801", "722802", "722803")
MUNICIPALITY_COUNT = 179   # ambito del proyecto: todos los municipios de la Comunidad (CLAUDE.md §2.2)


def pollutant_category(pollutant, value, bands):
    if value is None:
        return None
    # la tabla del BOE es de enteros: redondeo al entero mas proximo, .5 hacia arriba (round() va al par)
    v = math.floor(value + 0.5)
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
    day_max_temp_c: float | None = None     # Tmax prevista del dia de esta hora (maximo de forecast.temp)
    heat_threshold_c: float | None = None   # umbral de calor de la zona meteosalud del municipio (DEC-06)


@dataclass
class RuleResult:
    outdoor_ok: bool | None
    reasons: list[str] = field(default_factory=list)


def is_heat_day(ctx):
    """DEC-06: dia de calor si la Tmax prevista del dia supera (estricto) el umbral de su zona."""
    return (ctx.day_max_temp_c is not None and ctx.heat_threshold_c is not None
            and ctx.day_max_temp_c > ctx.heat_threshold_c)


def at_heat_risk(profile, companions, rules):
    heat = rules.get("heat") or {}
    return profile in heat.get("risk_profiles", []) or any(c in heat.get("risk_companions", []) for c in companions)


def _fmt_c(value):
    # 38 -> «38»; 37.4 -> «37,4» (coma decimal, como explanation.fmt_number)
    return f"{value:.1f}".rstrip("0").rstrip(".").replace(".", ",")


def evaluate_outdoor(ctx, profile, rules, companions=()):
    reasons, evaluated = [], 0
    air = rules.get("air") or {}
    # perfil con clave propia: su valor manda (null = regla desactivada); sin clave, el de general
    limit = air[profile] if profile in air and profile not in AIR_META_KEYS else air.get("general")
    if limit and ctx.aqi_category is not None:
        evaluated += 1
        if CATEGORIES.index(ctx.aqi_category) >= CATEGORIES.index(limit):
            reasons.append(f"Calidad del aire {CATEGORY_LABEL[ctx.aqi_category].lower()}")
    heat = rules.get("heat") or {}
    if heat and ctx.day_max_temp_c is not None and ctx.heat_threshold_c is not None:
        evaluated += 1
        start, end = heat["avoid_hours"]
        if is_heat_day(ctx) and at_heat_risk(profile, companions, rules) and start <= ctx.hour.hour < end:
            reasons.append(f"Día de calor (máx. prevista {_fmt_c(ctx.day_max_temp_c)} °C, umbral de tu zona "
                           f"{_fmt_c(ctx.heat_threshold_c)} °C): mejor evitar de {start:02d}:00 a {end:02d}:00")
    max_rain = (rules.get("rain") or {}).get("max_precip_prob")
    if max_rain is not None and ctx.precip_prob is not None:
        evaluated += 1
        if ctx.precip_prob > max_rain:
            reasons.append(f"Lluvia: {ctx.precip_prob:.0f} % de probabilidad")
    if reasons:
        return RuleResult(False, reasons)
    return RuleResult(True if evaluated else None, [])


def _check_number(value, name, low=None, high=None):
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"rules.yaml: {name} debe ser un número o null, no {value!r}")
    if (low is not None and value < low) or (high is not None and value > high):
        raise ValueError(f"rules.yaml: {name} fuera de rango ({value})")


def validate_rules(rules, zones=None, config_dir=None):
    """Comprueba rules.yaml al cargarlo, para que un error de configuracion no salga como 500 en una peticion.

    zones: tabla de heat_zones.csv (ine_code -> zona); si se pasa, debe cubrir los 179 municipios.
    config_dir: si se pasa (arranque de la API), la tabla se lee de config_dir / heat.zone_table."""
    air = rules.get("air") or {}
    for profile, category in air.items():
        if profile in AIR_META_KEYS or category is None:
            continue
        if category not in CATEGORIES:
            raise ValueError(f"rules.yaml: air.{profile} = {category!r} no es una categoría del ICA {CATEGORIES}")
    heat = rules.get("heat")
    if heat and zones is None and config_dir is not None and isinstance(heat.get("zone_table"), str):
        zones = load_heat_zones(config_dir / heat["zone_table"])
    _validate_heat(heat, zones)
    _check_number((rules.get("rain") or {}).get("max_precip_prob"), "rain.max_precip_prob", 0, 100)


def _validate_heat(heat, zones):
    if not heat:
        return       # sin seccion heat: regla desactivada (la app lo avisa)
    if not isinstance(heat.get("zone_table"), str):
        raise ValueError("rules.yaml: heat.zone_table debe ser el nombre del CSV de zonas (heat_zones.csv)")
    defined = heat.get("zones") or {}
    if set(defined) != set(HEAT_ZONES):
        raise ValueError(f"rules.yaml: heat.zones debe tener exactamente las zonas {HEAT_ZONES}, no {sorted(defined)}")
    for code, zone in defined.items():
        limit = (zone or {}).get("max_temp_c")
        if limit is None:
            raise ValueError(f"rules.yaml: heat.zones.{code}.max_temp_c es obligatorio")
        _check_number(limit, f"heat.zones.{code}.max_temp_c", 0, 60)
    hours = heat.get("avoid_hours")
    if (not isinstance(hours, list) or len(hours) != 2
            or any(isinstance(h, bool) or not isinstance(h, int) or not 0 <= h <= 24 for h in hours)
            or hours[0] >= hours[1]):
        raise ValueError(f"rules.yaml: heat.avoid_hours debe ser [inicio, fin] con 0 <= inicio < fin <= 24, no {hours!r}")
    if zones is not None:
        if len(zones) != MUNICIPALITY_COUNT:
            raise ValueError(f"heat_zones.csv: {len(zones)} municipios, deben ser {MUNICIPALITY_COUNT}")
        unknown = sorted({z for z in zones.values() if z not in defined})
        if unknown:
            raise ValueError(f"heat_zones.csv: zonas sin umbral en rules.yaml: {unknown}")


def load_heat_zones(path):
    """heat_zones.csv -> {ine_code: zone_code}."""
    with open(path, encoding="utf-8", newline="") as f:
        return {row["ine_code"].strip(): row["zone_code"].strip() for row in csv.DictReader(f)}
