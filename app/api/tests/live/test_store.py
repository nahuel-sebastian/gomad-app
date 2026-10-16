"""LiveStore (B2 Task 40): cache en memoria con TTL y validez maxima; nunca se sirve un dato mas viejo que max_age_h."""
import threading
import time
from datetime import datetime, timedelta

import httpx
import pytest

import settings
from live.store import LiveStore, validate_realtime

NOW = datetime(2026, 10, 16, 12, 0)


class Clock:
    def __init__(self, t=NOW):
        self.t = t

    def __call__(self):
        return self.t


def cfg(**air):
    return {"tick_s": 5, "sources": {"air_cm": {"url": "https://example.org/aire.csv", "ttl_s": 600,
                                                "max_age_h": 3, "timeout_s": 1, **air}}}


def counting_fetch(values):
    """fetch falso: devuelve (valor, observed_at) de la lista o lanza la excepcion que haya en ella."""
    calls = []

    def fetch(store):
        calls.append(store.now())
        item = values[min(len(calls), len(values)) - 1]
        if isinstance(item, Exception):
            raise item
        return item
    return fetch, calls


def test_within_ttl_does_not_refetch():
    clock = Clock()
    store = LiveStore(cfg(), now=clock)
    fetch, calls = counting_fetch([("v1", NOW), ("v2", NOW)])
    store.register("air_cm", fetch)
    assert store.refresh("air_cm") is True
    clock.t = NOW + timedelta(seconds=599)
    assert store.refresh("air_cm") is False and len(calls) == 1
    clock.t = NOW + timedelta(seconds=601)
    assert store.refresh("air_cm") is True and store.get("air_cm").value == "v2"


def test_portal_down_recent_value_is_stale():
    clock = Clock()
    store = LiveStore(cfg(), now=clock)
    fetch, _ = counting_fetch([("v1", NOW), httpx.ConnectError("caido")])
    store.register("air_cm", fetch)
    store.refresh("air_cm")
    clock.t = NOW + timedelta(hours=2)
    store.refresh("air_cm")
    entry = store.get("air_cm")
    assert entry.value == "v1" and entry.status == "stale" and entry.last_error == "ConnectError"


def test_portal_down_old_value_is_none():
    clock = Clock()
    store = LiveStore(cfg(), now=clock)
    fetch, _ = counting_fetch([("v1", NOW), httpx.ConnectError("caido")])
    store.register("air_cm", fetch)
    store.refresh("air_cm")
    clock.t = NOW + timedelta(hours=4)
    store.refresh("air_cm")
    assert store.get("air_cm") is None                       # max_age_h 3: nunca el valor viejo
    assert store.entry("air_cm").status == "stale"           # el estado sigue disponible para diagnostico


def test_old_observation_even_if_just_fetched_is_none():
    store = LiveStore(cfg(), now=Clock())
    store.register("air_cm", lambda s: ("v", NOW - timedelta(hours=3, minutes=10)))
    store.refresh("air_cm")
    assert store.get("air_cm") is None                       # cuenta la hora del dato, no la de la descarga


def test_slow_portal_does_not_block_get():
    store = LiveStore(cfg(ttl_s=1), now=Clock())
    release = threading.Event()
    fetches = iter([lambda: ("v1", NOW), lambda: (release.wait(5), ("v2", NOW))[1]])
    store.register("air_cm", lambda s: next(fetches)())
    store.refresh("air_cm")
    store._entries["air_cm"].fetched_at = NOW - timedelta(seconds=10)      # TTL vencido
    worker = threading.Thread(target=store.refresh, args=("air_cm",))
    worker.start()
    t0 = time.perf_counter()
    assert store.get("air_cm").value == "v1"
    assert time.perf_counter() - t0 < 0.5
    release.set()
    worker.join(5)
    assert store.get("air_cm").value == "v2"


def test_concurrent_refresh_single_request():
    store = LiveStore(cfg(), now=Clock())
    release, started, calls = threading.Event(), threading.Event(), []

    def fetch(s):
        calls.append(1)
        started.set()
        release.wait(5)
        return "v", NOW
    store.register("air_cm", fetch)
    worker = threading.Thread(target=store.refresh, args=("air_cm",))
    worker.start()
    started.wait(5)
    assert store.refresh("air_cm") is False                  # ya hay una descarga en marcha
    release.set()
    worker.join(5)
    assert len(calls) == 1


def test_snapshot_mode_never_opens_connections(tmp_path):
    (tmp_path / "air_cm").mkdir()
    (tmp_path / "air_cm" / "data").write_bytes(b"grabado")

    def no_network(request):
        raise AssertionError(f"conexion abierta a {request.url}")
    client = httpx.Client(transport=httpx.MockTransport(no_network))
    store = LiveStore(cfg(), client=client, now=Clock(), snapshot_dir=tmp_path)
    store.register("air_cm", lambda s: (s.http_get("air_cm", "https://example.org/aire.csv")[0], NOW - timedelta(days=2)))
    assert store.refresh("air_cm") is True
    assert store.snapshot and store.get("air_cm").value == b"grabado"    # demo sin red: se sirve lo grabado


def test_http_get_uses_client_and_timeout():
    seen = {}

    def handler(request):
        seen["url"], seen["timeout"] = str(request.url), request.extensions["timeout"]["read"]
        return httpx.Response(200, content=b"ok", headers={"content-type": "text/csv; charset=utf-8"})
    store = LiveStore(cfg(), client=httpx.Client(transport=httpx.MockTransport(handler)), now=Clock())
    content, content_type = store.http_get("air_cm", "https://example.org/aire.csv")
    assert content == b"ok" and "utf-8" in content_type
    assert seen == {"url": "https://example.org/aire.csv", "timeout": 1}


def test_realtime_yaml_without_max_age_names_source():
    bad = cfg()
    del bad["sources"]["air_cm"]["max_age_h"]
    with pytest.raises(ValueError, match="air_cm.*max_age_h"):
        validate_realtime(bad)
    validate_realtime(settings.load("realtime"))             # el YAML real es valido
