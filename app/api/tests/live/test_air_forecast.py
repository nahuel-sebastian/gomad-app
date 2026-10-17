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


# --- Task 91: feed en vivo -------------------------------------------------------------------------------------------
class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class Cams:
    """Portal falso: la muestra repetida tantas veces como coordenadas pida la URL."""

    def __init__(self, status=None):
        self.status, self.calls = list(status or []), []

    def __call__(self, request):
        self.calls.append(request)
        if self.status:
            code = self.status.pop(0)
            if code != 200:
                return httpx.Response(code, json={"error": True})
        n = len(parse_qs(urlsplit(str(request.url)).query)["latitude"][0].split(","))
        body = [copy.deepcopy(SAMPLE[i % len(SAMPLE)]) for i in range(n)]
        return httpx.Response(200, json=body if n > 1 else body[0])


def air_feed_at(now, portal=None, points=None, **kw):
    from live.air_forecast import AirForecastFeed
    clock = Clock(now)
    cfg = settings.load("realtime")
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(portal or Cams())), now=clock)
    return AirForecastFeed(store, cfg, points or POINTS, settings.load("ica_thresholds"), **kw), clock


def test_one_request_for_all_points_and_ttl():
    from live.forecast import load_points
    portal = Cams()
    pts = load_points(settings.CONFIG_DIR / "forecast_points.csv")
    feed, clock = air_feed_at(NOW, portal, points=pts)
    assert feed.step() == "ok:179" and len(portal.calls) == 1
    q = parse_qs(urlsplit(str(portal.calls[0].url)).query)
    assert len(q["latitude"][0].split(",")) == 179 and q["past_days"] == ["1"]
    assert q["hourly"] == ["ozone,nitrogen_dioxide,pm10,pm2_5"]
    cats, issued = feed.get("28065")
    assert datetime(2026, 10, 16, 12) in cats and issued == NOW
    assert feed.step() == "idle" and len(portal.calls) == 1
    clock.t = NOW + timedelta(hours=3)
    assert feed.step() == "ok:179" and len(portal.calls) == 2


def test_failure_waits_globally_and_keeps_data(caplog):
    portal = Cams(status=[200, 429, 503])
    feed, clock = air_feed_at(NOW, portal)
    assert feed.step() == "ok:3"
    clock.t = NOW + timedelta(hours=3)
    with caplog.at_level(logging.WARNING, logger="gomad.api"):
        assert feed.step() == "429"
        assert feed.next_try == clock.t + timedelta(seconds=120)
        assert feed.step() == "wait" and len(portal.calls) == 2
        assert feed.get("28065") is not None                 # se conserva lo anterior
        clock.t = feed.next_try
        assert feed.step() == "503"
        assert feed.next_try == clock.t + timedelta(seconds=240)
    assert feed.last_error == "HTTP 503"
    assert not any("latitude" in r.getMessage() for r in caplog.records)
    clock.t = feed.next_try
    assert feed.step() == "ok:3" and feed.failures == 0


def test_get_respects_max_age():
    feed, clock = air_feed_at(NOW)
    feed.step()
    clock.t = NOW + timedelta(hours=25)
    assert feed.get("28065") is None


def test_cache_roundtrip_and_expiry(tmp_path):
    path = tmp_path / "live" / "air_forecast.json"
    feed, _ = air_feed_at(NOW, cache_path=path)
    feed.step()
    other, clock = air_feed_at(NOW + timedelta(hours=1), cache_path=path)
    assert other.load_cache() == 3
    assert other.get("28079") == feed.get("28079") and other.fetched_at == NOW
    assert other.step() == "idle"                            # la cache cuenta para el TTL
    late, _ = air_feed_at(NOW + timedelta(hours=25), cache_path=path)
    assert late.load_cache() == 0
    path.write_text("no es json", encoding="utf-8")
    assert air_feed_at(NOW, cache_path=path)[0].load_cache() == 0


def test_build_live_registers_air_forecast(tmp_path):
    from live import build_live
    store = build_live(settings.load("realtime"), httpx.Client(transport=httpx.MockTransport(Cams())),
                       cache_path=tmp_path / "live" / "forecast.json")
    assert store.air_forecast.cache_path.name == "air_forecast.json"
    assert store.air_forecast.step in store._tasks
