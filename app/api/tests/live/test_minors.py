"""Menores de la revision y la verificacion de LB2-1 (16/10): cada uno con su prueba."""
import copy
import json
import logging
from datetime import datetime, timedelta

import httpx

import schemas as s
import settings
from live.air import AirFeed, parse_air_csv, register_air
from live.forecast import ForecastFeed
from live.store import LiveStore, validate_realtime
from mini_data import ORIGIN, build_mini_data
from repository import Repository
from routing.store import GraphStore
from services.recommend import recommend
from test_air import AY, CM
from test_forecast import CENTERS, DOC, KEY, Aemet, Clock, feed_at

NOW = datetime(2026, 10, 16, 10, 0)


def shifted_doc():
    """Muestra de AEMET movida dos dias (elaborada el 16/10 a las 08:00) para cuadrar con el aire del 16/10."""
    text = json.dumps(DOC, ensure_ascii=False)
    for old, new in (("2026-10-16", "2026-10-18"), ("2026-10-15", "2026-10-17"), ("2026-10-14", "2026-10-16")):
        text = text.replace(old, new)
    doc = json.loads(text)
    doc["elaborado"] = "2026-10-16T08:00:00"
    return doc


class ShiftedAemet(Aemet):
    def __call__(self, request):
        r = super().__call__(request)
        if "/horaria/" in str(request.url):
            return r
        ine = str(request.url).rsplit("/", 1)[1]
        doc = shifted_doc()
        doc["id"] = ine
        return httpx.Response(200, content=json.dumps([doc], ensure_ascii=False).encode("iso-8859-15"),
                              headers={"content-type": "text/plain;charset=ISO-8859-15"})


def live_store(now, forecast_ines):
    cfg = settings.load("realtime")
    aemet = ShiftedAemet()

    def handler(request):
        url = str(request.url)
        if url == cfg["sources"]["air_cm"]["url"]:
            return httpx.Response(200, content=CM)
        if url == cfg["sources"]["air_ay"]["url"]:
            return httpx.Response(200, content=AY)
        return aemet(request)
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)), now=lambda: now)
    register_air(store, cfg)
    store.refresh("air_cm")
    store.refresh("air_ay")
    store.forecast = ForecastFeed(store, cfg, codes=forecast_ines, centers=lambda: CENTERS, key=KEY)
    store.forecast.pilots = list(forecast_ines)
    for _ in forecast_ines:
        store.forecast.step()
    return store


def request(**kw):
    base = dict(origin=ORIGIN, activity="walk", window_start=NOW, window_end=NOW + timedelta(hours=3),
                duration_min=45, max_distance_m=1000)
    return s.RecommendRequest(**{**base, **kw})


# --- V7: el camino en vivo de extremo a extremo -------------------------------------------------------------------
def test_recommend_uses_live_air_and_forecast(tmp_path):
    base = build_mini_data(tmp_path / "data", forecast=False, air=False)     # nada en realtime.duckdb
    repo = Repository(base, live=live_store(NOW, ["28065"]))
    rec = recommend(request(), repo, GraphStore(), now=NOW).results[0]
    assert rec.hours[0].temperature_c is not None                            # AEMET en memoria
    assert rec.hours[0].aqi_category == "fair"                               # Getafe 09:00, NO2 46
    labels = [d.label for d in rec.sources]
    assert "Previsión horaria (AEMET)" in labels and any("estación Getafe" in x for x in labels)


# --- M2/6 y M1: prevision del vecino visible, recalculada y con la propia pedida -----------------------------------
def test_neighbour_forecast_is_labelled_and_own_requested(tmp_path):
    base = build_mini_data(tmp_path / "data", forecast=False, air=False)
    store = live_store(NOW, ["28058"])                                       # solo Fuenlabrada tiene prevision
    repo = Repository(base, live=store)
    rec = recommend(request(), repo, GraphStore(), now=NOW).results[0]
    assert any(d.label == "Previsión horaria (AEMET) · Previsión de Fuenlabrada" for d in rec.sources)
    assert "28065" in store.forecast.requested                               # M1: la propia, con prioridad
    store.forecast.data["28065"] = store.forecast.data["28058"]              # llega la propia
    repo.forecast(["28065"], NOW, NOW + timedelta(hours=1))
    assert "28065" not in repo.forecast_notes                                 # M2: la nota no se queda


# --- M3: el set de pedidos se lee con lock -------------------------------------------------------------------------
def test_requested_set_is_guarded_by_lock():
    feed, _ = feed_at(datetime(2026, 10, 14, 13))
    assert feed.lock.acquire(blocking=False)
    try:
        import threading
        done = threading.Event()
        threading.Thread(target=lambda: (feed.request(["28006"]), done.set()), daemon=True).start()
        assert not done.wait(0.2)                                            # request espera al lock
    finally:
        feed.lock.release()
    assert done.wait(2) and "28006" in feed.requested


# --- M4: parar espera a una descarga de AEMET y no cierra un cliente en uso ---------------------------------------
def test_stop_waits_for_two_aemet_steps():
    store = LiveStore(settings.load("realtime"))
    assert store.stop_timeout_s() >= 2 * settings.load("realtime")["sources"]["forecast"]["timeout_s"]


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


# --- V5: el log no dice que municipio ha pedido una persona --------------------------------------------------------
def test_log_hides_user_requested_municipality(caplog):
    caplog.set_level(logging.INFO)
    feed, _ = feed_at(datetime(2026, 10, 14, 13), Aemet(status={"28006": 500}))
    feed.request(["28006"])
    feed.step()
    ours = " ".join(r.getMessage() for r in caplog.records if r.name == "gomad.api")
    assert "sin descargar" in ours and "28006" not in ours
