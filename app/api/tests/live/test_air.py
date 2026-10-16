"""Aire en vivo (B2 Task 41): las dos redes en memoria, mismas categorias que la ruta por lotes (normalize + aqi_hourly)."""
import pathlib
from datetime import datetime, timedelta

import httpx

import settings
from live.air import AirFeed, air_categories, parse_air_csv, register_air
from live.store import LiveStore
from repository import Repository

DATA = pathlib.Path(__file__).resolve().parents[1] / "data"
CM = (DATA / "aire_dia_sample.csv").read_bytes()          # Getafe 28065014, 16/10, horas 1-9 con T
AY = (DATA / "ay_aire_sample.csv").read_bytes()           # Madrid 28079008, 16/10, horas 1-11 con V
ICA = settings.load("ica_thresholds")
DAY = datetime(2026, 10, 16)


def store_at(now, cm=CM, ay=AY):
    urls = {"air_cm": cm, "air_ay": ay}
    cfg = settings.load("realtime")

    def handler(request):
        for name, body in urls.items():
            if str(request.url) == cfg["sources"][name]["url"]:
                return httpx.Response(200, content=body)
        return httpx.Response(404)
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)), now=lambda: now)
    register_air(store, cfg)
    store.refresh("air_cm")
    store.refresh("air_ay")
    return store


def test_sample_categories_match_batch_path():
    readings = parse_air_csv(CM.decode("utf-8-sig"))
    cats = dict(air_categories([readings], DAY, DAY + timedelta(hours=9), ICA, 3)["28065014"])
    # calculado a mano con los valores del CSV (como create_aqi_hourly): NO2 1 h; O3 media de 8 h con >= 6 horas;
    # PM10/PM2.5 necesitan 18 de 24 h y aun no las tienen
    # h03 y h04: NO2 39 -> good y O3 sin 6 horas; h06: O3 (2+5+6+5+2+2)/6 = 3,7 good, NO2 46 -> fair
    assert cats[DAY + timedelta(hours=3)] == "good" and cats[DAY + timedelta(hours=4)] == "good"
    assert cats[DAY + timedelta(hours=6)] == "fair"
    # h09: NO2 46 -> fair; O3 (5+6+5+2+2+2+3+15)/8 = 5 -> good; la peor manda
    assert cats[DAY + timedelta(hours=9)] == "fair"
    assert DAY + timedelta(hours=10) not in cats                                  # horas futuras vacias (N)


def test_capital_station_ids_and_decimal():
    readings = parse_air_csv(AY.decode("utf-8-sig"))
    assert {r[0] for r in readings} == {"28079008"}
    assert {r[1] for r in readings} <= {1, 8, 9, 10, 14}                       # solo las del ICA
    no2 = {r[2]: r[3] for r in readings if r[1] == 8}
    assert no2[DAY + timedelta(hours=11)] == 29.0


def test_t_counts_n_does_not():
    head = "provincia;municipio;estacion;magnitud;punto_muestreo;ano;mes;dia;" + ";".join(
        f"h{h:02d};v{h:02d}" for h in range(1, 25))
    hours = ["7,5;T", "9;N", "12;V"] + [";N"] * 21
    rows = parse_air_csv(head + "\n28;6;4;8;x;2026;10;16;" + ";".join(hours) + "\n")
    assert [(r[0], r[2], r[3]) for r in rows] == [("28006004", DAY + timedelta(hours=1), 7.5),
                                                  ("28006004", DAY + timedelta(hours=3), 12.0)]


def test_yesterday_file_after_midnight_has_no_current_reading():
    # a las 00:30 el fichero regional todavia es el de ayer: sus horas son de ayer, no de hoy
    yesterday = CM.decode("utf-8-sig").replace(";2026;10;16;", ";2026;10;15;").encode()
    store = store_at(datetime(2026, 10, 16, 0, 30), cm=yesterday)
    assert store.entry("air_cm").observed_at == datetime(2026, 10, 15, 9, 0)    # fecha de la fila, no de hoy
    assert store.get("air_cm") is None


def test_last_reading_4h10_is_none():
    # tope de 4 h (decidido el 16/10: la red CM publica con ~3 h de retraso)
    assert store_at(datetime(2026, 10, 16, 13, 10)).get("air_cm") is None     # ultima: 09:00
    assert store_at(datetime(2026, 10, 16, 12, 50)).get("air_cm") is not None


def test_buffer_keeps_24h_and_merges():
    feed = AirFeed("air_cm", "https://example.org", buffer_h=24)
    first = feed.merge(parse_air_csv(CM.decode("utf-8-sig")), now=datetime(2026, 10, 16, 12))
    later = feed.merge([], now=datetime(2026, 10, 17, 8))           # solo quedan las de las ultimas 24 h
    assert len(first) > 0 and all(r[2] >= datetime(2026, 10, 16, 8) for r in later)
    assert len(later) < len(first)


def test_repository_reads_live_air(tmp_path):
    repo = Repository(tmp_path, live=store_at(datetime(2026, 10, 16, 11, 30)))   # sin realtime.duckdb en disco
    cats = repo.air_categories(DAY + timedelta(hours=9), DAY + timedelta(hours=12), ICA, 3)
    assert cats["28065014"][-1] == (DAY + timedelta(hours=9), "fair")
    assert cats["28079008"][-1] == (DAY + timedelta(hours=11), "good")
    assert Repository(tmp_path).air_categories(DAY, DAY + timedelta(hours=12), ICA, 3) == {}   # sin vivo ni disco


def test_repository_live_without_air_is_empty(tmp_path):
    store = store_at(datetime(2026, 10, 16, 18, 0))                     # todo con mas de 3 h
    assert Repository(tmp_path, live=store).air_categories(DAY, DAY + timedelta(hours=18), ICA, 3) == {}


def test_build_live_registers_air():
    """El LiveStore que crea el arranque de la API ya trae las dos redes de aire (sin esto, nunca hay aire)."""
    from live import build_live
    store = build_live(settings.load("realtime"), client=None, snapshot_dir=None)
    assert {"air_cm", "air_ay"} <= set(store._fetchers)


def test_cold_start_seeds_buffer_from_ingest(tmp_path):
    """Tras reiniciar, el bufer de 24 h se siembra con clean/air_reading: el PM10 de ayer cuenta (como en la ruta batch)."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    seed = tmp_path / "air_reading"
    seed.mkdir()
    hours = [datetime(2026, 10, 15, 10) + timedelta(hours=h) for h in range(15)]        # 15/10 10:00 -> 16/10 00:00
    # como los parquet reales de la ingesta: timestamp en nanosegundos (pyarrow devuelve pandas.Timestamp)
    pq.write_table(pa.table({"station_id": ["28065014"] * 15, "magnitude": [10] * 15,
                             "ts": pa.array(hours, pa.timestamp("ns")),
                             "value": [60.0] * 15, "flag": ["V"] * 15}), seed / "aire_dia_20261015.parquet")
    cfg = settings.load("realtime")
    now = datetime(2026, 10, 16, 9, 30)

    def handler(request):
        return httpx.Response(200, content=CM if "comunidad" in str(request.url) else AY)
    store = LiveStore(cfg, client=httpx.Client(transport=httpx.MockTransport(handler)), now=lambda: now)
    register_air(store, cfg, seed_dir=seed)
    store.refresh("air_cm")
    cats = dict(air_categories([store.get("air_cm").value], DAY, DAY + timedelta(hours=9), ICA, 3)["28065014"])
    # PM10 24 h = (15 x 60 + 11+9+1+1+1+2+8+18+35) / 24 = 41,1 -> moderate (sin semilla: solo 9 h, no cuenta -> fair)
    assert cats[DAY + timedelta(hours=9)] == "moderate"
    assert all(type(r[2]) is datetime for r in store.get("air_cm").value)    # nunca pandas.Timestamp


def test_station_older_than_max_age_is_dropped_in_fresh_network(tmp_path):
    """El tope es por estacion: una estacion parada dentro de una red con dato reciente no se sirve."""
    stopped = CM.decode("utf-8-sig")                                              # Getafe: ultima a las 09:00
    fresh_row = AY.decode("utf-8-sig").splitlines()[1].replace("28;079;8;", "28;5;2;")   # 28005002 hasta 11:00
    cm = (stopped.rstrip("\n") + "\n" + fresh_row + "\n").encode()
    now = datetime(2026, 10, 16, 13, 30)                                          # Getafe 4 h 30; 28005002 2 h 30
    repo = Repository(tmp_path, live=store_at(now, cm=cm))
    cats = repo.air_categories(DAY + timedelta(hours=13), DAY + timedelta(hours=14), ICA, 4)
    assert "28065014" not in cats                       # la mas cercana con dato valido la sustituye en /recommend
    assert "28005002" in cats and "28079008" in cats


def test_valid_h_matches_station_max_age():
    """La ultima medicion de la estacion vale para /recommend lo mismo que su tope (sin dudas: la ultima, con su hora)."""
    rt = settings.load("realtime")["sources"]
    assert settings.load("recommend")["air_reading_valid_h"] == rt["air_cm"]["max_age_h"] == rt["air_ay"]["max_age_h"] == 4
