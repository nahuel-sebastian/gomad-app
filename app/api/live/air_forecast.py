"""Prevision horaria del aire de Copernicus CAMS via Open-Meteo (fila 2): categoria ICA de las horas futuras.

Una sola peticion trae los 179 municipios (los puntos de app/config/forecast_points.csv, nunca la ubicacion de la
persona); Open-Meteo devuelve una lista en el mismo orden. Al descargar se calcula una vez la categoria ICA de cada
municipio y hora con las mismas reglas que el aire medido (live/air.py): media movil de period_hours por
contaminante (O3 8 h, PM 24 h, NO2 1 h) con min_coverage y bandas de ica_thresholds.yaml; la peor manda.
La peticion lleva past_days=1 para que las medias de las primeras horas de hoy esten completas.
El valor horario de CAMS en t se toma como la hora que acaba en t, igual que h01..h24 del aire medido.
"""
import json
import math
from collections import deque
from datetime import datetime, timedelta

from engine.rules import aqi_category

# variable horaria de Open-Meteo -> contaminante del ICA (comprobado contra la API real el 17/10/2026, ug/m3)
VARIABLES = {"ozone": "O3", "nitrogen_dioxide": "NO2", "pm10": "PM10", "pm2_5": "PM2_5"}


def _parse_item(item):
    h = item["hourly"]
    times = [datetime.fromisoformat(t) for t in h["time"]]
    out = {}
    for var, pollutant in VARIABLES.items():
        values = h.get(var) or []
        out[pollutant] = {ts: float(v) for ts, v in zip(times, values) if v is not None}
    return out


def parse_response(raw, points):
    """{ine: {contaminante: {hora: valor}}}. La lista viene en el orden de los puntos; si no cuadra, ValueError."""
    doc = json.loads(raw)
    items = doc if isinstance(doc, list) else [doc]
    if len(items) != len(points):
        raise ValueError(f"CAMS devolvio {len(items)} puntos de {len(points)}")
    return {p[0]: _parse_item(item) for p, item in zip(points, items)}


def _moving_means(values, hours, needed):
    """{hora: media} de la ventana [t - (hours-1) h, t], solo si tiene al menos `needed` valores."""
    span = timedelta(hours=hours - 1)
    window, total, out = deque(), 0.0, {}
    for ts in sorted(values):
        window.append((ts, values[ts]))
        total += values[ts]
        while window[0][0] < ts - span:
            total -= window.popleft()[1]
        if len(window) >= needed:
            out[ts] = total / len(window)
    return out


def categories(series, ica):
    """{hora: categoria ICA} de un municipio: la peor de los contaminantes con media valida en esa hora."""
    by_ts = {}
    for pollutant, values in series.items():
        hours = ica["period_hours"].get(pollutant)
        if hours is None:
            continue
        clean = {ts: v for ts, v in values.items() if v is not None}
        needed = math.ceil(ica["min_coverage"] * hours)
        for ts, mean in _moving_means(clean, hours, needed).items():
            by_ts.setdefault(ts, {})[pollutant] = mean
    out = {}
    for ts, means in sorted(by_ts.items()):
        category = aqi_category(means, ica["bands"])
        if category is not None:
            out[ts] = category
    return out
