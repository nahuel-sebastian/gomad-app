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
    assert {c.id for c in found} == {"eiel_parques:1", "nmc_parques:1", "nmc_parques:2", "ay_parques:1"}
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
    assert repo.municipality_names() == {"28065": "Getafe", "28079": "Madrid"}


def test_route_pois_skip_not_working(repo):
    ids = {r[0] for r in repo.route_pois(-3.74, 40.30, -3.72, 40.31)}
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
