import duckdb
import pandas as pd
import pytest

import build_db

TEST_RULES = {"activities": [
    {"id": "swim", "label": "Nadar", "icon": "pool", "outdoor": None, "rules": [
        {"source": "eiel_deporte", "field": "facility_type", "in": ["PISCINAS CUBIERTAS"], "suitability": 1.0},
        {"source": "nmc_deporte", "field": "name", "contains": ["piscina"], "suitability": 0.9}]},
    {"id": "padel", "label": "Pádel", "icon": "sports_tennis", "outdoor": None, "rules": [
        {"source": "eiel_deporte", "sport": "PADEL", "suitability": 1.0},
        {"source": "nmc_deporte", "field": "name", "contains": ["pádel", "padel"], "suitability": 0.8}]},
]}


def sample_destinations():
    return pd.DataFrame([
        {"id": "eiel_deporte:1", "source": "eiel_deporte", "name": "Piscina cubierta", "facility_type": "PISCINAS CUBIERTAS", "sports": []},
        {"id": "eiel_deporte:2", "source": "eiel_deporte", "name": "Polideportivo", "facility_type": "OTROS", "sports": ["PADEL"]},
        {"id": "nmc_deporte:3", "source": "nmc_deporte", "name": "Pistas de PÁDEL Norte", "facility_type": None, "sports": []},
        {"id": "nmc_deporte:4", "source": "nmc_deporte", "name": "Campo de fútbol", "facility_type": None, "sports": []},
    ])


def test_apply_activities():
    r = build_db.apply_activities(sample_destinations(), TEST_RULES)
    assert set(zip(r.destination_id, r.activity)) == {
        ("eiel_deporte:1", "swim"), ("eiel_deporte:2", "padel"), ("nmc_deporte:3", "padel")}


def test_atomic_replace(tmp_path):
    target = tmp_path / "x.duckdb"
    target.write_bytes(b"old version")

    def fails(con):
        raise RuntimeError("fuente rota")

    with pytest.raises(RuntimeError):
        build_db.atomic(target, fails)
    assert target.read_bytes() == b"old version"                # el anterior se mantiene (arquitectura §3.3)
    build_db.atomic(target, lambda con: con.execute("CREATE TABLE t AS SELECT 1 AS a"))
    assert duckdb.connect(str(target), read_only=True).execute("SELECT a FROM t").fetchone() == (1,)


def test_aqi_moving_averages():
    hours = pd.date_range("2026-10-13 01:00", periods=30, freq="h")
    readings = pd.DataFrame({"station_id": "28065014", "magnitude": 14, "ts": hours,
                             "value": [float(i) for i in range(30)], "flag": "V"})
    con = duckdb.connect()
    con.register("air_reading", readings)
    build_db.create_aqi_hourly(con)
    row = con.execute("SELECT mean, n_hours FROM aqi_hourly WHERE pollutant='O3' AND ts = ?",
                      [hours[-1].to_pydatetime()]).fetchone()
    assert row == (sum(range(22, 30)) / 8, 8)                    # media de las 8 ultimas horas


@pytest.mark.slow
def test_build_main_real(tmp_path):
    path = build_db.build_main(tmp_path / "gomad.duckdb", rules=TEST_RULES)
    con = duckdb.connect(str(path), read_only=True)
    assert con.execute("SELECT count(*) FROM municipality").fetchone()[0] == 179
    assert con.execute("SELECT count(*) FROM destination WHERE ine_code IS NULL").fetchone()[0] == 0
    without_vpla = con.execute("SELECT count(*) FROM destination d JOIN municipality m USING (ine_code) "
                               "WHERE NOT m.in_vpla AND d.green IS NOT NULL").fetchone()[0]
    assert without_vpla == 0                                     # sin VPLA -> green NULL, no 0
    assert con.execute("SELECT count(*) FROM destination_activity WHERE activity='swim'").fetchone()[0] > 0
