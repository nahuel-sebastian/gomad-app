"""Prevision de AEMET en vivo (B2 Task 42): cola con prioridad, cuota de 4/min, 429, cache de arranque y respaldo."""
import copy
import json
import logging
import pathlib
from datetime import datetime, timedelta

import httpx

import settings
from live.forecast import ForecastFeed, RateLimiter, parse_forecast
from live.store import LiveStore
from repository import Repository

DOC = json.loads((pathlib.Path(__file__).resolve().parents[1] / "data" / "aemet_28065.json").read_text("utf-8"))[0]
ISSUED = datetime(2026, 10, 14, 12, 1, 10)
KEY = "clave-secreta-de-prueba"
CENTERS = [("28065", "Getafe", -3.7329, 40.3057), ("28058", "Fuenlabrada", -3.7929, 40.2842),   # ~5,5 km
           ("28079", "Madrid", -3.7035, 40.4169), ("28131", "San Lorenzo de El Escorial", -4.1474, 40.5914),
           ("28006", "Alcobendas", -3.6298, 40.5354)]


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


class Aemet:
    """Portal falso de AEMET: dos pasos (URL con api_key -> datos) y respuestas por municipio."""

    def __init__(self, status=None):
        self.status = status or {}       # ine -> codigo HTTP del primer paso
        self.calls = []

    def __call__(self, request):
        url = str(request.url)
        self.calls.append(url)
        if "/horaria/" in url:
            ine = url.rsplit("/", 1)[1]
            assert request.headers.get("api_key") == KEY and KEY not in url
            code = self.status.get(ine, 200)
            if code != 200:
                return httpx.Response(code, json={"descripcion": "Too Many Requests"})
            return httpx.Response(200, json={"estado": 200, "datos": f"https://opendata.aemet.es/opendata/sh/{ine}"})
        ine = url.rsplit("/", 1)[1]
        doc = copy.deepcopy(DOC)
        doc["id"] = ine
        body = json.dumps([doc], ensure_ascii=False).encode("iso-8859-15")
        return httpx.Response(200, content=body, headers={"content-type": "text/plain;charset=ISO-8859-15"})


def feed_at(now, portal=None, codes=None, **kw):
    clock = Clock(now)
    cfg = settings.load("realtime")
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(portal or Aemet())), now=clock)
    feed = ForecastFeed(store, cfg, codes=codes or [c[0] for c in CENTERS], centers=lambda: CENTERS, key=KEY, **kw)
    return feed, clock


def ines(portal):
    return [u.rsplit("/", 1)[1] for u in portal.calls if "/horaria/" in u]


def test_getafe_sample_hours():
    feed, _ = feed_at(ISSUED + timedelta(hours=1))
    assert feed.step() == "ok:28065"                       # primer piloto
    series, issued, note = feed.get("28065")
    assert issued == ISSUED and note is None
    day = datetime(2026, 10, 14)
    assert min(series) == day + timedelta(hours=9)
    assert [h.hour for h in sorted(series) if h.date() == day.date()] == list(range(9, 24))
    assert [h.hour for h in sorted(series) if h.date() == datetime(2026, 10, 15).date()] == list(range(24))
    assert series[day + timedelta(hours=17)][:2] == (28.0, 28.0)


def test_hour_17_uses_band_1420():
    doc = copy.deepcopy(DOC)
    doc["prediccion"]["dia"][0]["probPrecipitacion"] = [
        {"value": "10", "periodo": "0814"}, {"value": "35", "periodo": "1420"}, {"value": "60", "periodo": "2002"}]
    series, _ = parse_forecast(doc)
    day = datetime(2026, 10, 14)
    assert series[day + timedelta(hours=17)][2] == 35.0 and series[day + timedelta(hours=14)][2] == 35.0
    assert series[day + timedelta(hours=13)][2] == 10.0 and series[day + timedelta(hours=20)][2] == 60.0


def test_ip_is_zero():
    doc = copy.deepcopy(DOC)
    for e in doc["prediccion"]["dia"][0]["precipitacion"]:
        if e["periodo"] == "10":
            e["value"] = "Ip"
    series, _ = parse_forecast(doc)
    assert series[datetime(2026, 10, 14, 10)][3] == 0.0


def test_rate_limit_never_exceeded():
    portal = Aemet()
    feed, clock = feed_at(ISSUED + timedelta(hours=1), portal)
    stamps = []
    for _ in range(120):                                    # 10 min, un paso cada 5 s
        before = len(portal.calls)
        feed.step()
        stamps += [clock.t] * (len(portal.calls) - before)
        clock.t += timedelta(seconds=5)
    assert len(stamps) >= 8
    for t in stamps:
        assert sum(1 for s in stamps if t <= s < t + timedelta(seconds=60)) <= 4


def test_rate_limiter_window():
    clock = Clock(ISSUED)
    limiter = RateLimiter(4, clock)
    assert limiter.allow(2) and limiter.allow(2) and not limiter.allow(1)
    clock.t += timedelta(seconds=61)
    assert limiter.allow(2)


def test_429_retries_once_then_moves_on():
    portal = Aemet(status={"28065": 429})
    feed, clock = feed_at(ISSUED + timedelta(hours=1), portal)
    assert feed.step() == "429:28065"
    clock.t += timedelta(seconds=30)
    assert feed.step() == "ok:28079"                       # mientras espera, sigue con el siguiente
    clock.t += timedelta(seconds=100)                      # pasan los 120 s de retry_429_s
    assert feed.step() == "429:28065"                      # el reintento tambien falla: a la siguiente vuelta
    clock.t += timedelta(seconds=30)
    assert feed.step() == "ok:28131"
    assert ines(portal) == ["28065", "28079", "28065", "28131"]


def test_user_request_jumps_queue():
    feed, _ = feed_at(ISSUED + timedelta(hours=1))
    assert feed.next_due() == "28065"                      # pilotos antes que el resto
    feed.request(["28006"])
    assert feed.next_due() == "28006"
    assert feed.step() == "ok:28006"
    assert feed.next_due() == "28065"


def test_fresh_forecast_not_refetched_until_6h():
    feed, clock = feed_at(ISSUED + timedelta(hours=1), codes=["28065"])
    feed.step()
    assert feed.next_due() == "28079"                      # Getafe ya esta; siguen los otros pilotos
    clock.t = ISSUED + timedelta(hours=7)                  # elaborado hace mas de 6 h y ultimo intento hace 6 h
    assert feed.next_due() == "28065"


def test_issued_13h_ago_not_used():
    feed, clock = feed_at(ISSUED + timedelta(hours=1))
    feed.step()
    clock.t = ISSUED + timedelta(hours=13)
    assert feed.get("28065") is None


def test_nearest_forecast_within_km():
    feed, _ = feed_at(ISSUED + timedelta(hours=1))
    feed.step()                                            # solo Getafe tiene prevision
    series, issued, note = feed.get("28058")               # Fuenlabrada, a ~5,5 km
    assert note == "Previsión de Getafe" and issued == ISSUED and series
    assert feed.get("28006") is None                       # Alcobendas, a mas de 10 km


def test_key_never_in_logs_or_errors(caplog):
    def broken(request):
        raise httpx.ConnectError(f"fallo en {request.url} {request.headers}")
    caplog.set_level(logging.DEBUG)
    feed, _ = feed_at(ISSUED + timedelta(hours=1), broken)
    assert feed.step() == "error:28065"
    assert KEY not in caplog.text and KEY not in str(feed.last_error)
    assert feed.last_error == "ConnectError"


def test_cache_drops_old_on_load(tmp_path):
    cache = tmp_path / "live" / "forecast.json"
    feed, _ = feed_at(ISSUED + timedelta(hours=1), codes=["28065", "28079"], cache_path=cache)
    feed.step()
    feed.step()
    assert cache.exists()
    data = json.loads(cache.read_text("utf-8"))
    data["28079"]["issued"] = (ISSUED - timedelta(hours=12)).isoformat()      # con 13 h al cargar
    cache.write_text(json.dumps(data), "utf-8")
    fresh, _ = feed_at(ISSUED + timedelta(hours=1), codes=["28065", "28079"], cache_path=cache)
    assert fresh.load_cache() == 1
    assert fresh.get("28065")[1] == ISSUED and fresh.get("28079") is None


def test_repository_reads_live_forecast(tmp_path):
    feed, _ = feed_at(ISSUED + timedelta(hours=1))
    feed.step()
    feed.store.forecast = feed
    repo = Repository(tmp_path, live=feed.store)           # sin realtime.duckdb
    start = datetime(2026, 10, 14, 16)
    by, issued = repo.forecast(["28065", "28058", "28006"], start, start + timedelta(hours=3))
    assert sorted(by["28065"]) == [start + timedelta(hours=h) for h in range(4)]
    assert by["28065"][start + timedelta(hours=1)][:2] == (28.0, 28.0) and issued["28065"] == ISSUED
    assert repo.forecast_notes == {"28058": "Previsión de Getafe"}
    assert "28006" not in by and "28006" in feed.requested                     # se pide con prioridad


def test_build_live_registers_forecast_queue(tmp_path):
    """El arranque crea la cola de AEMET con los 179 codigos, la cache de arranque y el paso del hilo de fondo."""
    from live import build_live
    cache = tmp_path / "live" / "forecast.json"
    store = build_live(settings.load("realtime"), client=None, centers=lambda: CENTERS, cache_path=cache, key=KEY)
    assert isinstance(store.forecast, ForecastFeed)
    assert store.forecast.codes == sorted(c[0] for c in CENTERS) and store.forecast.key == KEY
    assert store.forecast.step in store._tasks


def test_build_live_without_municipalities_uses_pilots():
    from live import build_live

    def missing():
        raise FileNotFoundError("sin municipality.parquet")
    store = build_live(settings.load("realtime"), client=None, centers=missing, key=KEY)
    assert store.forecast.codes == ["28065", "28079", "28131"]


def test_portal_error_is_logged_without_key(caplog):
    caplog.set_level(logging.INFO)
    feed, _ = feed_at(ISSUED + timedelta(hours=1), Aemet(status={"28065": 429}))
    feed.step()
    ours = " ".join(r.getMessage() for r in caplog.records if r.name == "gomad.api")   # no el log de httpx
    assert "28065" in ours and "429" in ours
    assert KEY not in caplog.text


def test_snapshot_mode_serves_recorded_forecast(tmp_path):
    """Demo sin red (L-4): la prevision grabada el lunes se sirve el martes; nunca se abre una conexion."""
    (tmp_path / "forecast").mkdir()
    (tmp_path / "forecast" / "28065.json").write_text(json.dumps([DOC], ensure_ascii=False), "utf-8")

    def no_network(request):
        raise AssertionError("conexion abierta")
    cfg = settings.load("realtime")
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(no_network)),
                      now=Clock(ISSUED + timedelta(days=2)), snapshot_dir=tmp_path)
    feed = ForecastFeed(store, cfg, codes=["28065"], key=None)
    assert feed.step() == "ok:28065"
    assert feed.get("28065")[1] == ISSUED                  # 48 h despues: en modo grabado no caduca
