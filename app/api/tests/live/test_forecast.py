"""Prevision de Open-Meteo en vivo (DEC-16, Tasks 73-74): una peticion para los 179, espera global y cache."""
import copy
import json
import logging
import pathlib
from datetime import date, datetime, timedelta
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

import settings
from live.forecast import ForecastFeed, load_points, parse_open_meteo, parse_response
from live.store import LiveStore
from repository import Repository

SAMPLE = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "open_meteo_sample.json")
                    .read_text("utf-8"))                     # Getafe, Madrid y San Lorenzo, 16-18/10/2026
POINTS = [("28065", "Getafe", 40.2991, -3.6734), ("28079", "Madrid", 40.4654, -3.6965),
          ("28131", "San Lorenzo De El Escorial", 40.6187, -4.1304)]
NOW = datetime(2026, 10, 16, 10, 0)


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class OpenMeteo:
    """Portal falso: responde con la muestra repetida tantas veces como coordenadas pida la URL."""

    def __init__(self, status=None):
        self.status = list(status or [])        # codigos HTTP de las primeras peticiones
        self.calls = []

    def __call__(self, request):
        self.calls.append(request)
        if self.status:
            code = self.status.pop(0)
            if code != 200:
                return httpx.Response(code, json={"error": True, "reason": "Too many requests"})
        n = len(coords(request)[0])
        body = [copy.deepcopy(SAMPLE[i % len(SAMPLE)]) for i in range(n)]
        return httpx.Response(200, json=body if n > 1 else body[0])


def coords(request):
    q = parse_qs(urlsplit(str(request.url)).query)
    lats = [float(x) for x in q["latitude"][0].split(",")]
    lons = [float(x) for x in q["longitude"][0].split(",")]
    return lats, lons


def feed_at(now, portal=None, points=None, **kw):
    clock = Clock(now)
    cfg = settings.load("realtime")
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(portal or OpenMeteo())), now=clock)
    return ForecastFeed(store, cfg, points or POINTS, **kw), clock


# --- Task 73: lectura de la respuesta -----------------------------------------------------------------------------
def test_sample_parses_three_days():
    series, day_max = parse_open_meteo(SAMPLE[0])
    assert len(series) == 72 and min(series) == datetime(2026, 10, 16, 0) and max(series) == datetime(2026, 10, 18, 23)
    assert series[datetime(2026, 10, 16, 17)] == (26.4, 26.1, 0.0, 0.0, 1.8, "Despejado")
    assert all(isinstance(v[5], str) for v in series.values())          # cielo en espanol
    assert set(day_max) == {date(2026, 10, 16), date(2026, 10, 17), date(2026, 10, 18)}


def test_daily_max_comes_from_daily():
    series, day_max = parse_open_meteo(SAMPLE[0])
    hourly = max(v[0] for ts, v in series.items() if ts.date() == date(2026, 10, 17))
    assert day_max[date(2026, 10, 17)] == 23.3 and hourly == 23.2       # la diaria, no el maximo horario


def test_list_order_matches_points():
    got = parse_response(json.dumps(SAMPLE).encode(), POINTS)
    assert got["28065"][0][datetime(2026, 10, 16, 17)][0] == 26.4
    assert got["28079"][0][datetime(2026, 10, 16, 17)][0] == 26.1
    assert got["28131"][0][datetime(2026, 10, 16, 17)][0] == 20.7
    with pytest.raises(ValueError):
        parse_response(json.dumps(SAMPLE[:2]).encode(), POINTS)          # falta un punto: nada asignado
    one = parse_response(json.dumps(SAMPLE[2]).encode(), POINTS[2:])     # un objeto suelto = un punto
    assert list(one) == ["28131"]


def test_load_points_reads_config_csv():
    pts = load_points(settings.CONFIG_DIR / settings.load("realtime")["sources"]["forecast"]["points"])
    assert len(pts) == 179 and ("28065", "Getafe", 40.2991, -3.6734) in pts


# --- Task 73: descarga ----------------------------------------------------------------------------------------------
def test_one_request_serves_179():
    portal = OpenMeteo()
    pts = load_points(settings.CONFIG_DIR / "forecast_points.csv")
    feed, _ = feed_at(NOW, portal, points=pts)
    assert feed.step() == "ok:179"
    assert len(portal.calls) == 1
    assert all(feed.get(p[0]) is not None for p in pts)


def test_request_carries_only_config_points():
    portal = OpenMeteo()
    feed, _ = feed_at(NOW, portal)
    feed.step()
    request = portal.calls[0]
    lats, lons = coords(request)
    assert lats == [p[2] for p in POINTS] and lons == [p[3] for p in POINTS]
    assert str(request.url).startswith(settings.load("realtime")["sources"]["forecast"]["url"])
    assert not any("key" in h.lower() for h in request.headers)            # sin clave


def test_within_ttl_no_request():
    portal = OpenMeteo()
    feed, clock = feed_at(NOW, portal)
    assert feed.step() == "ok:3"
    clock.t += timedelta(minutes=59)
    assert feed.step() == "idle" and len(portal.calls) == 1
    clock.t += timedelta(minutes=1)
    assert feed.step() == "ok:3" and len(portal.calls) == 2


def test_error_sets_global_growing_wait():
    portal = OpenMeteo(status=[429, 500])
    feed, clock = feed_at(NOW, portal)
    assert feed.step() == "429"
    for _ in range(23):                                                   # 115 s de ticks de 5 s: nada
        clock.t += timedelta(seconds=5)
        assert feed.step() == "wait"
    assert len(portal.calls) == 1
    clock.t += timedelta(seconds=5)                                       # 120 s
    assert feed.step() == "500"
    clock.t += timedelta(seconds=239)
    assert feed.step() == "wait"
    clock.t += timedelta(seconds=1)                                       # 240 s: la espera se duplica
    assert feed.step() == "ok:3" and len(portal.calls) == 3
    clock.t += timedelta(seconds=120)
    assert feed.step() == "idle"                                          # tras el exito, vuelve al TTL


def test_wait_has_a_ceiling():
    feed, clock = feed_at(NOW, OpenMeteo(status=[503] * 20))
    waits = []
    for _ in range(8):
        feed.step()
        waits.append((feed.next_try - clock.t).total_seconds())
        clock.t = feed.next_try
    assert waits[:4] == [120, 240, 480, 960] and max(waits) == 3600


def test_old_forecast_not_served():
    feed, clock = feed_at(NOW)
    feed.step()
    series, issued, day_max = feed.get("28065")
    assert issued == NOW and series and day_max
    clock.t = NOW + timedelta(hours=13)
    assert feed.get("28065") is None


def test_cache_roundtrip_drops_old(tmp_path):
    cache = tmp_path / "live" / "forecast.json"
    feed, _ = feed_at(NOW, cache_path=cache)
    feed.step()
    assert cache.exists()
    data = json.loads(cache.read_text("utf-8"))
    data["28079"]["issued"] = (NOW - timedelta(hours=13)).isoformat()
    cache.write_text(json.dumps(data), "utf-8")
    fresh, _ = feed_at(NOW + timedelta(minutes=5), cache_path=cache)
    assert fresh.load_cache() == 2
    series, issued, day_max = fresh.get("28065")
    assert issued == NOW and series[datetime(2026, 10, 16, 17)][0] == 26.4 and day_max[date(2026, 10, 17)] == 23.3
    assert fresh.get("28079") is None
    assert fresh.step() == "idle"                                         # la cache cuenta para el TTL


def test_snapshot_mode_serves_recorded_forecast(tmp_path):
    """Demo sin red (L-4): la prevision grabada se sirve dias despues; nunca se abre una conexion."""
    (tmp_path / "forecast").mkdir()
    (tmp_path / "forecast" / "open_meteo.json").write_text(json.dumps(SAMPLE), "utf-8")

    def no_network(request):
        raise AssertionError("conexion abierta")
    cfg = settings.load("realtime")
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(no_network)),
                      now=Clock(NOW + timedelta(days=4)), snapshot_dir=tmp_path)
    feed = ForecastFeed(store, cfg, POINTS)
    assert feed.step() == "ok:3"
    assert feed.get("28065") is not None                                  # en modo grabado no caduca


def test_errors_logged_without_url(caplog):
    def broken(request):
        raise httpx.ConnectError(f"fallo en {request.url}")
    caplog.set_level(logging.DEBUG)
    feed, _ = feed_at(NOW, broken)
    assert feed.step() == "error"
    assert feed.last_error == "ConnectError"
    ours = " ".join(r.getMessage() for r in caplog.records if r.name == "gomad.api")
    assert "sin descargar" in ours and "40.2991" not in ours and "latitude" not in ours


# --- Task 74: conexion con el arranque y el repositorio -------------------------------------------------------------
def test_repository_reads_live_forecast(tmp_path):
    feed, _ = feed_at(NOW)
    feed.step()
    feed.store.forecast = feed
    repo = Repository(tmp_path, live=feed.store)                          # sin realtime.duckdb
    start = datetime(2026, 10, 16, 16)
    by, issued = repo.forecast(["28065", "28006"], start, start + timedelta(hours=3))
    assert sorted(by["28065"]) == [start + timedelta(hours=h) for h in range(4)]
    assert by["28065"][start + timedelta(hours=1)] == (26.4, 26.1, 0.0) and issued["28065"] == NOW
    assert repo.forecast_day_max["28065"][date(2026, 10, 17)] == 23.3
    assert "28006" not in by                                              # sin punto: sin prevision


def test_build_live_uses_config_points(tmp_path):
    from live import build_live
    store = build_live(settings.load("realtime"), client=None, cache_path=tmp_path / "forecast.json")
    assert isinstance(store.forecast, ForecastFeed)
    assert len(store.forecast.points) == 179
    assert store.forecast.step in store._tasks


def test_repository_offline_reads_temp_max_day(tmp_path):
    """Sin vivo (GOMAD_LIVE=off, demo sin red): la Tmax diaria sale de la columna temp_max_day de la ingesta."""
    import duckdb
    from mini_data import NOW as MINI_NOW, build_mini_data
    base = build_mini_data(tmp_path / "data")
    repo = Repository(base)
    repo.forecast(["28065"], MINI_NOW, MINI_NOW + timedelta(hours=2))
    assert repo.forecast_day_max == {}                                    # base antigua: sin columna
    con = duckdb.connect(str(base / "realtime.duckdb"))
    con.execute("ALTER TABLE forecast ADD COLUMN temp_max_day DOUBLE")
    con.execute("UPDATE forecast SET temp_max_day = 38.0")
    con.close()
    by, _ = repo.forecast(["28065"], MINI_NOW, MINI_NOW + timedelta(hours=2))
    assert by["28065"] and repo.forecast_day_max["28065"] == {MINI_NOW.date(): 38.0}
