from datetime import datetime, timedelta

import pytest

from mini_data import NOW, ORIGIN, build_mini_data
from repository import DataUnavailable, Repository, category_at, haversine_m, parse_date
import settings

ICA = settings.load("ica_thresholds")


@pytest.fixture
def repo(tmp_path):
    return Repository(build_mini_data(tmp_path / "data"))


def test_haversine():
    assert float(haversine_m(-3.7300, 40.3050, -3.7289, 40.3050)) == pytest.approx(93, abs=1)


def test_candidates_by_box_distance_and_activity(repo):
    found = repo.candidates(ORIGIN["lon"], ORIGIN["lat"], 1000, ["walk"], "any", 400)
    assert {c.id for c in found} == {"eiel_parques:1", "nmc_parques:1", "nmc_parques:2", "ay_parques:1", "vpla_redes:1"}
    first = next(c for c in found if c.id == "eiel_parques:1")
    assert first.activity == "walk" and first.suitability == 1.0 and first.straight_m == pytest.approx(93, abs=1)
    assert next(c for c in found if c.id == "nmc_parques:2").green is None


def test_candidates_setting_and_limit(repo):
    assert [c.id for c in repo.candidates(ORIGIN["lon"], ORIGIN["lat"], 1000, ["walk", "gym"], "indoor", 400)] == ["eiel_deporte:1"]
    assert "eiel_deporte:1" not in {c.id for c in repo.candidates(ORIGIN["lon"], ORIGIN["lat"], 1000, ["gym"], "outdoor", 400)}
    assert len(repo.candidates(ORIGIN["lon"], ORIGIN["lat"], 1000, ["walk"], "any", 2)) == 2


def test_forecast_in_window(repo):
    by, issued = repo.forecast(["28065", "28079"], NOW, NOW + timedelta(hours=2))
    assert sorted(by["28065"]) == [NOW + timedelta(hours=h) for h in range(3)]
    assert by["28065"][NOW] == (20.0, 20.0, 0.0)
    assert "28079" not in by and issued["28065"] == datetime(2026, 10, 16, 8, 0)


def test_air_categories_require_coverage(repo):
    cats = repo.air_categories(NOW, NOW + timedelta(hours=2), ICA, 3)
    assert cats == {"28065014": [(NOW - timedelta(hours=1), "good")]}    # PM10 con 15 h no cuenta


def test_category_at_uses_last_reading_within_valid_hours():
    readings = [(NOW - timedelta(hours=1), "good"), (NOW, "moderate")]
    assert category_at(readings, NOW - timedelta(hours=1), 3) == "good"
    assert category_at(readings, NOW + timedelta(hours=3), 3) == "moderate"
    assert category_at(readings, NOW + timedelta(hours=4), 3) is None
    assert category_at(readings, NOW - timedelta(hours=2), 3) is None


def test_parse_date():
    assert parse_date("2026-10-16T09:05:00.123456") == datetime(2026, 10, 16, 9, 5, 0, 123456)
    assert parse_date("Tue, 13 Oct 2026 23:55:22 GMT") == datetime(2026, 10, 14, 1, 55, 22)
    assert parse_date(None) is None and parse_date("ayer") is None


def test_source_dates_prefer_modified(repo):
    dates = repo.source_dates()
    assert dates["aire_dia"] == datetime(2026, 10, 16, 9, 5, 0, 123456)
    assert dates["eiel_parques"] == datetime(2026, 10, 14, 15, 51, 38)


def test_municipality_names_prefer_callejero(repo):
    assert repo.municipality_names() == {"28065": "Getafe", "28079": "Madrid", "28127": "Las Rozas de Madrid"}


def test_route_pois_skip_not_working(repo):
    ids = set(repo.route_pois(-3.74, 40.30, -3.72, 40.31)["id"].tolist())
    assert ids == {"ay_fuentes:1", "osm:node/1"}


def test_missing_realtime_is_empty_and_missing_main_raises(tmp_path):
    base = build_mini_data(tmp_path / "data")
    (base / "realtime.duckdb").unlink()
    repo = Repository(base)
    assert repo.forecast(["28065"], NOW, NOW) == ({}, {})
    assert repo.air_categories(NOW, NOW, ICA, 3) == {}
    (base / "gomad.duckdb").unlink()
    with pytest.raises(DataUnavailable):
        repo.candidates(ORIGIN["lon"], ORIGIN["lat"], 1000, ["walk"], "any", 400)


# --- Mapa explorable (C2, Task 141) ---
GETAFE_BOX = (-3.735, 40.300, -3.720, 40.312)
DEST_KINDS = ["facility", "pool", "park", "recreation_area", "trail", "bathing_area"]
POI_KINDS = ["fountain", "bench", "aed", "dog_area", "playground"]


@pytest.fixture
def map_repo(tmp_path):
    import duckdb
    base = build_mini_data(tmp_path / "data")
    con = duckdb.connect(str(base / "gomad.duckdb"))
    con.execute("""INSERT INTO destination VALUES ('eiel_deporte:9', 'eiel_deporte', 'Piscina Municipal', 'facility',
                   false, NULL, NULL, NULL, NULL, NULL, '28065', -3.7260, 40.3060, 0.2, NULL)""")
    con.execute("INSERT INTO destination_activity VALUES ('eiel_deporte:9', 'swim', 1.0), ('eiel_deporte:9', 'gym', 0.5)")
    con.close()
    return Repository(base)


def test_map_points_filters_by_box_and_kind(map_repo):
    rows = map_repo.map_points(GETAFE_BOX, ["park"], [], 100, "swim")
    assert {r[0] for r in rows} == {"eiel_parques:1", "nmc_parques:1", "nmc_parques:2", "ay_parques:1", "vpla_redes:1"}
    assert {r[1] for r in rows} == {"park"}
    pois = map_repo.map_points(GETAFE_BOX, [], ["bench"], 100, "swim")
    assert [(r[0], r[1], r[2], r[3]) for r in pois] == [("osm:node/1", "bench", None, "osm")]


def test_map_points_marks_pools(map_repo):
    rows = {r[0]: r for r in map_repo.map_points(GETAFE_BOX, DEST_KINDS, [], 100, "swim")}
    assert rows["eiel_deporte:9"][1] == "pool"
    assert rows["eiel_deporte:1"][1] == "facility"
    assert rows["eiel_deporte:9"][2] == "Piscina Municipal"
    only_pools = map_repo.map_points(GETAFE_BOX, ["pool"], [], 100, "swim")
    assert [r[0] for r in only_pools] == ["eiel_deporte:9"]


def test_map_points_includes_out_of_service_fountains(map_repo):
    rows = {r[0]: r for r in map_repo.map_points(GETAFE_BOX, [], ["fountain"], 100, "swim")}
    assert rows["ay_fuentes:1"][4] is True
    assert rows["ay_fuentes:2"][4] is False


def test_map_points_orders_by_centre_and_limits(map_repo):
    box = (-3.7400, 40.2950, -3.7200, 40.3150)        # centro -3.73, 40.305 = nodo 0 del grafo mini
    rows = map_repo.map_points(box, DEST_KINDS, [], 3, "swim")
    assert len(rows) == 3
    lon, lat = -3.73, 40.305
    d = [((r[5] - lon) * 0.7627) ** 2 + (r[6] - lat) ** 2 for r in rows]
    assert d == sorted(d)
    assert rows[0][0] == "eiel_parques:1"             # Parque Uno, a 93 m del centro


def test_map_points_puts_destinations_before_pois(map_repo):
    box = (-3.7400, 40.2950, -3.7200, 40.3150)
    rows = map_repo.map_points(box, DEST_KINDS, POI_KINDS, 100, "swim")
    groups = [r[1] in POI_KINDS for r in rows]
    assert groups == sorted(groups) and groups[-1]     # destinos primero aunque la fuente este mas cerca
    assert map_repo.map_points(box, DEST_KINDS, POI_KINDS, 1, "swim")[0][1] not in POI_KINDS


def test_map_points_without_db_is_unavailable(tmp_path):
    with pytest.raises(DataUnavailable):
        Repository(tmp_path).map_points(GETAFE_BOX, ["park"], [], 10, "swim")
