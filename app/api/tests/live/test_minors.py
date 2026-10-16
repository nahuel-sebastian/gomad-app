"""Menores de la revision y la verificacion de LB2-1 (16/10): cada uno con su prueba. Prevision: Open-Meteo (DEC-16)."""
import copy
import json
import logging
from datetime import datetime, timedelta

import httpx

import schemas as s
import settings
from live.air import AirFeed, parse_air_csv, register_air
from live.forecast import ForecastFeed, load_points
from live.store import LiveStore, validate_realtime
from mini_data import ORIGIN, build_mini_data
from repository import Repository
from routing.store import GraphStore
from services.recommend import recommend
from test_air import AY, CM
from test_forecast import NOW as SAMPLE_NOW, POINTS, SAMPLE, Clock, OpenMeteo, coords, feed_at

NOW = datetime(2026, 10, 16, 10, 0)
assert NOW == SAMPLE_NOW                        # la muestra de Open-Meteo es del 16/10, como el aire


def live_store(now, portal=None, points=None):
    cfg = settings.load("realtime")
    portal = portal or OpenMeteo()

    def handler(request):
        url = str(request.url)
        if url == cfg["sources"]["air_cm"]["url"]:
            return httpx.Response(200, content=CM)
        if url == cfg["sources"]["air_ay"]["url"]:
            return httpx.Response(200, content=AY)
        return portal(request)
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)), now=lambda: now)
    register_air(store, cfg)
    store.refresh("air_cm")
    store.refresh("air_ay")
    store.forecast = ForecastFeed(store, cfg, points or POINTS)
    store.forecast.step()
    return store


def request(**kw):
    base = dict(origin=ORIGIN, activity="walk", window_start=NOW, window_end=NOW + timedelta(hours=3),
                duration_min=45, max_distance_m=1000)
    return s.RecommendRequest(**{**base, **kw})


# --- V7: el camino en vivo de extremo a extremo -------------------------------------------------------------------
def test_recommend_uses_live_air_and_forecast(tmp_path):
    base = build_mini_data(tmp_path / "data", forecast=False, air=False)     # nada en realtime.duckdb
    repo = Repository(base, live=live_store(NOW))
    rec = recommend(request(), repo, GraphStore(), now=NOW).results[0]
    assert rec.hours[0].temperature_c is not None                            # Open-Meteo en memoria
    assert rec.hours[0].precip_prob is not None                       # probabilidad horaria
    assert rec.hours[0].aqi_category == "fair"                               # Getafe 09:00, NO2 46
    labels = [d.label for d in rec.sources]
    assert "Previsión horaria (Open-Meteo)" in labels and any("estación Getafe" in x for x in labels)


# --- DEC-06 con Open-Meteo: el calor se evalua con la Tmax diaria, no con el maximo horario -------------------------
def _hot_portal(daily):
    class Hot(OpenMeteo):
        def __call__(self, request):
            r = super().__call__(request)
            body = json.loads(r.content)
            for item in body if isinstance(body, list) else [body]:
                item["hourly"]["temperature_2m"] = [min(t, 37.0) if t is not None else t
                                                    for t in item["hourly"]["temperature_2m"]]
                item["hourly"]["temperature_2m"][14] = 37.0                  # 16/10 14:00: maximo horario 37
                if daily:
                    item["daily"]["temperature_2m_max"][0] = 38.0            # Tmax diaria del 16/10: 38
                else:
                    item.pop("daily")
            return httpx.Response(200, json=body)
    return Hot()


def test_heat_uses_daily_max(tmp_path):
    base = build_mini_data(tmp_path / "data", forecast=False, air=False)
    hot = recommend(request(), Repository(base, live=live_store(NOW, _hot_portal(True))), GraphStore(), now=NOW)
    assert "Día de calor en tu zona" in hot.warnings                         # 38 > 37,4 (Getafe, zona 722802)
    mild = recommend(request(), Repository(base, live=live_store(NOW, _hot_portal(False))), GraphStore(), now=NOW)
    assert "Día de calor en tu zona" not in mild.warnings                    # sin diaria: maximo horario 37


# --- Privacidad (CLAUDE.md 2.8): la ubicacion de la persona nunca sale hacia Open-Meteo ---------------------------
def test_user_location_never_sent(tmp_path):
    base = build_mini_data(tmp_path / "data", forecast=False, air=False)
    portal = OpenMeteo()
    pts = load_points(settings.CONFIG_DIR / "forecast_points.csv")
    store = live_store(NOW, portal, points=pts)
    repo = Repository(base, live=store)
    origin = {"lat": 40.30512, "lon": -3.73007}
    recommend(request(origin=origin), repo, GraphStore(), now=NOW)
    store.forecast.fetched_at = None                                          # otra descarga tras la consulta
    store.forecast.step()
    assert len(portal.calls) == 2
    for call in portal.calls:
        lats, lons = coords(call)
        assert lats == [p[2] for p in pts] and lons == [p[3] for p in pts]
        assert "40.3051" not in str(call.url) and "-3.7300" not in str(call.url)


# --- M4: parar espera a una descarga de la prevision y no cierra un cliente en uso -------------------------------
def test_stop_waits_for_a_forecast_step():
    store = LiveStore(settings.load("realtime"))
    assert store.stop_timeout_s() >= settings.load("realtime")["sources"]["forecast"]["timeout_s"]


# --- M5: municipio con 5 cifras ------------------------------------------------------------------------------------
def test_station_id_with_five_digit_municipality():
    head = "provincia;municipio;estacion;magnitud;punto_muestreo;ano;mes;dia;" + ";".join(
        f"h{h:02d};v{h:02d}" for h in range(1, 25))
    rows = parse_air_csv(head + "\n28;28079;8;8;x;2026;10;16;12;V" + ";;N" * 23 + "\n")
    assert rows[0][0] == "28079008"


# --- V2: en modo grabado, el aire de otro dia se reproduce como actual ---------------------------------------------
def test_snapshot_air_is_replayed_at_current_time(tmp_path):
    (tmp_path / "air_cm").mkdir()
    (tmp_path / "air_cm" / "data").write_bytes(CM)                          # grabado el 16/10, ultima 09:00
    now = datetime(2026, 10, 20, 11, 20)                                     # demo del martes
    store = LiveStore(settings.load("realtime"), now=lambda: now, snapshot_dir=tmp_path)
    feed = AirFeed("air_cm", "https://example.org", buffer_h=24)
    store.register("air_cm", feed.fetch)
    store.refresh("air_cm")
    readings = store.get("air_cm").value
    assert max(r[2] for r in readings) == datetime(2026, 10, 20, 11, 0)      # la ultima pasa a la hora en curso
    assert len(readings) == len(parse_air_csv(CM.decode("utf-8-sig")))      # no se pierde nada por antiguedad


# --- V3: el reintento tras un fallo sale de realtime.yaml ---------------------------------------------------------
def test_retry_after_failure_from_yaml():
    cfg = copy.deepcopy(settings.load("realtime"))
    assert cfg["retry_failed_s"] == 60
    cfg["retry_failed_s"] = 1
    clock = Clock(NOW)
    store = LiveStore(cfg, now=clock)
    calls = []
    store.register("air_cm", lambda st: (calls.append(1), (_ for _ in ()).throw(httpx.ConnectError("x")))[1])
    store.refresh("air_cm")
    clock.t += timedelta(seconds=2)
    store.refresh("air_cm")
    assert len(calls) == 2


# --- V4: la prevision caduca con su max_age_h (sin clave duplicada) ------------------------------------------------
def test_forecast_uses_its_max_age_h():
    cfg = settings.load("realtime")
    assert "max_issued_age_h" not in cfg["sources"]["forecast"] and cfg["sources"]["forecast"]["max_age_h"] == 12
    validate_realtime(cfg)


# --- V5: el log no lleva coordenadas ni la URL de la prevision -------------------------------------------------
def test_log_hides_forecast_url(caplog):
    caplog.set_level(logging.INFO)
    feed, _ = feed_at(NOW, OpenMeteo(status=[500]))
    feed.step()
    ours = " ".join(r.getMessage() for r in caplog.records if r.name == "gomad.api")
    assert "sin descargar" in ours and "HTTP 500" in ours and "latitude" not in ours
