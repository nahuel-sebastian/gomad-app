import json
from datetime import datetime

import pandas as pd
import pytest

from common import ROOT, read_csv
from normalize.aemet import municipality_forecast
from normalize.air import long_readings

DATA = ROOT / "tests" / "data"


def test_air_date_per_row():
    df = read_csv(DATA / "aire_dia_sample.csv")
    long = long_readings(df)
    row = df.iloc[0]
    expected_day = datetime(int(row["ano"]), int(row["mes"]), int(row["dia"]))
    assert long["ts"].min() >= pd.Timestamp(expected_day)          # no supone «hoy»
    assert set(long["flag"]) <= {"T", "V"}                          # N descartado
    assert long["station_id"].str.match(r"^28\d{6}$").all()


def test_air_h24_is_next_midnight():
    df = pd.DataFrame([{"provincia": "28", "municipio": "65", "estacion": "14", "magnitud": "8",
                        "punto_muestreo": "x", "ano": "2026", "mes": "10", "dia": "13",
                        **{f"h{i:02d}": "" for i in range(1, 25)}, **{f"v{i:02d}": "N" for i in range(1, 25)},
                        "h24": "12", "v24": "V"}])
    long = long_readings(df)
    assert list(long["ts"]) == [pd.Timestamp("2026-10-14 00:00")]
    assert long["station_id"].item() == "28065014"


def test_air_city_council_uppercase():
    df = pd.DataFrame([{"PROVINCIA": "28", "MUNICIPIO": "079", "ESTACION": "4", "MAGNITUD": "14",
                        "PUNTO_MUESTREO": "x", "ANO": "2026", "MES": "10", "DIA": "14",
                        **{f"H{i:02d}": "" for i in range(1, 25)}, **{f"V{i:02d}": "N" for i in range(1, 25)},
                        "H08": "55", "V08": "V"}])
    long = long_readings(df)
    assert long["station_id"].item() == "28079004" and long["value"].item() == 55.0


@pytest.mark.skipif(not (DATA / "aemet_28065.json").exists(), reason="muestra de Task 4")
def test_aemet_hourly_forecast():
    doc = json.loads((DATA / "aemet_28065.json").read_text(encoding="utf-8"))
    f = municipality_forecast(doc[0] if isinstance(doc, list) else doc, "28065")
    assert len(f) >= 24
    assert f["ts"].is_monotonic_increasing and f["ts"].is_unique
    assert f["temp"].notna().all()
    assert f["precip_prob"].between(0, 100).all()
    assert (f["precip"] >= 0).all()


@pytest.mark.slow
def test_reading_stations_exist_in_air_station():
    import geopandas as gpd

    from common import RAW, latest_csv
    from normalize.air import run_stations

    stations = gpd.read_parquet(run_stations())
    assert stations["id"].is_unique and stations["id"].str.match(r"^28\d{6}$").all()
    assert set(stations["network"]) == {"CM", "AY"}
    for source, columns in (("aire_dia", ["provincia", "h24"]), ("ay_aire", ["PROVINCIA", "H24"])):
        readings = long_readings(read_csv(latest_csv(RAW / source, columns)))
        assert len(readings) > 0
        missing = set(readings["station_id"]) - set(stations["id"])
        assert not missing, f"{source}: estaciones sin ficha {sorted(missing)}"
