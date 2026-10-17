"""Prevision de aire de Copernicus CAMS via Open-Meteo (fila 2, Tasks 90-91)."""
import copy
import json
import logging
import pathlib
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

import settings
from live.store import LiveStore, validate_realtime

SAMPLE = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "cams_sample.json")
                    .read_text("utf-8"))                     # Getafe, Madrid y San Lorenzo, 16-19/10/2026 (real)
POINTS = [("28065", "Getafe", 40.2991, -3.6734), ("28079", "Madrid", 40.4654, -3.6965),
          ("28131", "San Lorenzo De El Escorial", 40.6187, -4.1304)]
NOW = datetime(2026, 10, 16, 10, 0)


# --- Task 90: lectura y categorias ----------------------------------------------------------------------------------
def test_parse_sample():
    from live.air_forecast import parse_response
    out = parse_response(json.dumps(SAMPLE).encode(), POINTS)
    assert set(out) == {"28065", "28079", "28131"}
    assert set(out["28065"]) == {"O3", "NO2", "PM10", "PM2_5"}
    hours = sorted(out["28065"]["O3"])
    assert len(hours) == 96 and hours[0] == datetime(2026, 10, 16, 0)
    assert out["28065"]["O3"][hours[0]] == SAMPLE[0]["hourly"]["ozone"][0]
    assert out["28131"]["PM10"][hours[5]] == SAMPLE[2]["hourly"]["pm10"][5]


def test_parse_rejects_wrong_length():
    from live.air_forecast import parse_response
    with pytest.raises(ValueError):
        parse_response(json.dumps(SAMPLE).encode(), POINTS[:2])


def test_categories_moving_means_and_nulls():
    from live.air_forecast import categories
    ica = settings.load("ica_thresholds")
    t0 = datetime(2026, 10, 16, 0)
    hours = [t0 + timedelta(hours=i) for i in range(30)]
    series = {"NO2": {h: 30.0 for h in hours},
              "O3": {h: (120.0 if i >= 22 else 10.0) for i, h in enumerate(hours)},
              "PM10": {h: 45.0 for h in hours}}
    series["NO2"][hours[3]] = None                           # un hueco no rompe
    cats = categories(series, ica)
    assert cats[hours[-1]] == "moderate"                     # O3 media 8 h = 120 (fair <=100, moderate <=130)
    assert cats[hours[0]] == "good"                          # PM10 sin 18 h de cobertura: solo NO2 y O3
    assert cats[hours[20]] == "moderate"                     # PM10 media 24 h (21 h >= 18) = 45 -> moderate
    assert hours[3] not in cats                              # sin NO2 y O3/PM sin cobertura: sin categoria
    assert cats[hours[4]] == "good"


def test_realtime_has_air_forecast():
    cfg = settings.load("realtime")
    validate_realtime(cfg)
    src = cfg["sources"]["air_forecast"]
    assert src["ttl_s"] >= 3600 and src["points"] == "forecast_points.csv"
    assert "past_days=1" in src["url"] and "latitude" not in src["url"]


def test_categories_match_measured_rules():
    """Misma categoria que live.air.air_categories (reglas del aire medido) sobre la serie real de Getafe."""
    from live.air import air_categories
    from live.air_forecast import categories, parse_response
    ica = settings.load("ica_thresholds")
    series = parse_response(json.dumps(SAMPLE).encode(), POINTS)["28065"]
    magnitude = {"NO2": 8, "PM2_5": 9, "PM10": 10, "O3": 14}
    readings = [("x", magnitude[p], ts, v) for p, values in series.items() for ts, v in values.items()]
    hours = sorted(series["O3"])
    measured = dict(air_categories([readings], hours[0], hours[-1], ica, 0)["x"])
    assert categories(series, ica) == measured
