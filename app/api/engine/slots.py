"""Evaluacion hora a hora y mejor franja (RF-08, RF-09)."""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from engine.rules import HourContext, evaluate_outdoor
from engine.scoring import air_factor, compute_score, weather_factor

# tope de la ventana: la prevision horaria de AEMET cubre ~48 h (3 dias); mas alla no hay datos
MAX_WINDOW_HOURS = 72


@dataclass
class HourResult:
    hour: datetime
    score: float | None
    outdoor_ok: bool | None
    reasons: list[str] = field(default_factory=list)
    ctx: HourContext | None = None


def window_hours(start, end, now=None):
    # con now, las horas ya pasadas no se ofrecen (la hora en curso si)
    if now is not None and now.tzinfo is not None:
        # la ventana va en hora local de Madrid sin zona (schemas.py): se convierte now igual
        now = now.astimezone(ZoneInfo("Europe/Madrid")).replace(tzinfo=None)
    if now is not None and now > start:
        start = now
    h = start.replace(minute=0, second=0, microsecond=0)
    hours = []
    while h < end and len(hours) < MAX_WINDOW_HOURS:
        hours.append(h)
        h += timedelta(hours=1)
    return hours


def evaluate_hours(contexts, window, covered, profile, rules, fixed_factors, weights):
    results = []
    for hour in window:
        c = contexts.get(hour)
        if c is None:
            results.append(HourResult(hour, None, None, ["Sin previsión para esta hora"]))
            continue
        if covered:
            ok, reasons = None, []
        else:
            r = evaluate_outdoor(c, profile, rules)
            ok, reasons = r.outdoor_ok, r.reasons
        if ok is False:
            results.append(HourResult(hour, None, False, reasons, c))
            continue
        factors = {**fixed_factors,
                   "air": None if covered else air_factor(c.aqi_category),
                   "weather": None if covered else weather_factor(c.precip_prob)}
        score = compute_score(factors, weights)
        if not score.effective_weights:
            # ningun factor con peso tiene datos: sin nota, nunca un 0 silencioso
            results.append(HourResult(hour, None, ok, ["Sin datos para los factores que has priorizado"], c))
            continue
        results.append(HourResult(hour, score.value, ok, reasons, c))
    return results


def best_hour(results):
    candidates = [r for r in results if r.score is not None]
    # a igual nota, la hora mas temprana
    return max(candidates, key=lambda r: (r.score, -r.hour.timestamp())) if candidates else None


def needs_indoor(results):
    with_data = [r for r in results if r.ctx is not None]
    return bool(with_data) and all(r.outdoor_ok is False for r in with_data)
