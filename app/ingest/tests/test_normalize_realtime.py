import json
from datetime import datetime

import pandas as pd
import pytest

from common import ROOT, read_csv
from normalize.open_meteo import FORECAST_COLUMNS, municipality_forecast
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


def test_open_meteo_hourly_forecast():
    """Muestra real de Open-Meteo (16/10, Getafe): 72 horas, probabilidad horaria y Tmax diaria (DEC-16)."""
    doc = json.loads((DATA / "open_meteo_sample.json").read_text(encoding="utf-8"))
    f = municipality_forecast(doc[0], "28065", "2026-10-16T10:00:00")
    assert list(f.columns) == FORECAST_COLUMNS and FORECAST_COLUMNS[-1] == "temp_max_day"
    assert len(f) == 72 and f["ts"].is_monotonic_increasing and f["ts"].is_unique
    assert f["temp"].notna().all() and f["precip_prob"].between(0, 100).all() and (f["precip"] >= 0).all()
    row = f[f["ts"] == datetime(2026, 10, 16, 17)].iloc[0]
    assert (row.temp, row.feels_like, row.precip_prob, row.precip, row.wind, row.sky) == (
        26.4, 26.1, 0.0, 0.0, 1.8, "Despejado")
    assert f[f["ts"].dt.date == datetime(2026, 10, 17).date()]["temp_max_day"].unique().tolist() == [23.3]
    assert (f["ine_code"] == "28065").all() and (f["issued"] == "2026-10-16T10:00:00").all()


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


def _all_n_row(upper=False):
    row = {"provincia": "28", "municipio": "79", "estacion": "4", "magnitud": "8", "punto_muestreo": "x",
           "ano": "2026", "mes": "10", "dia": "15",
           **{f"h{i:02d}": "" for i in range(1, 25)}, **{f"v{i:02d}": "N" for i in range(1, 25)}}
    return {k.upper(): v for k, v in row.items()} if upper else row


def test_air_file_without_valid_hours_does_not_stop_the_rest(tmp_path, monkeypatch):
    # al cambiar de dia un fichero puede no traer ninguna hora valida todavia
    import normalize.air as air

    raw, clean = tmp_path / "raw", tmp_path / "clean"
    (raw / "aire_dia").mkdir(parents=True)
    (raw / "ay_aire").mkdir()
    pd.DataFrame([_all_n_row()]).to_csv(raw / "aire_dia" / "calidad_aire_datos_dia.csv", sep=";", index=False)
    ok = _all_n_row(upper=True) | {"H08": "40", "V08": "V"}
    pd.DataFrame([ok]).to_csv(raw / "ay_aire" / "calair_tiemporeal.csv", sep=";", index=False)
    monkeypatch.setattr(air, "RAW", raw)
    monkeypatch.setattr(air, "CLEAN", clean)
    written = air.run_readings()
    assert [p.name for p in written] == ["ay_aire_20261015.parquet"]
    assert long_readings(pd.DataFrame([_all_n_row()])).empty


def _raw_open_meteo(raw, items, codes):
    (raw / "open_meteo").mkdir(parents=True)
    (raw / "open_meteo" / "forecast.json").write_text(json.dumps(items), encoding="utf-8")
    (raw / "open_meteo" / "points.csv").write_text(
        "ine_code,name,lat,lon\n" + "".join(f"{c},X,40.3,-3.7\n" for c in codes), encoding="utf-8")
    (raw / "manifest.json").write_text(json.dumps({"open_meteo": {"downloaded": "2026-10-16T10:00:00"}}))


def test_open_meteo_writes_one_parquet_per_point(tmp_path, monkeypatch):
    import normalize.open_meteo as om

    raw, clean = tmp_path / "raw", tmp_path / "clean"
    doc = json.loads((DATA / "open_meteo_sample.json").read_text(encoding="utf-8"))
    _raw_open_meteo(raw, doc, ["28065", "28079", "28131"])
    monkeypatch.setattr(om, "RAW", raw)
    monkeypatch.setattr(om, "CLEAN", clean)
    written = om.run()
    assert sorted(p.name for p in written) == ["28065.parquet", "28079.parquet", "28131.parquet"]
    madrid = pd.read_parquet(clean / "forecast" / "28079.parquet")
    assert madrid[madrid["ts"] == datetime(2026, 10, 16, 17)]["temp"].item() == 26.1    # el 2.o de la lista
    assert (madrid["issued"] == "2026-10-16T10:00:00").all()


def test_open_meteo_length_mismatch_keeps_old_parquets(tmp_path, monkeypatch):
    import normalize.open_meteo as om

    raw, clean = tmp_path / "raw", tmp_path / "clean"
    doc = json.loads((DATA / "open_meteo_sample.json").read_text(encoding="utf-8"))
    _raw_open_meteo(raw, doc[:2], ["28065", "28079", "28131"])
    monkeypatch.setattr(om, "RAW", raw)
    monkeypatch.setattr(om, "CLEAN", clean)
    with pytest.raises(RuntimeError, match="2 puntos de 3"):
        om.run()
    assert not (clean / "forecast").exists() or not any((clean / "forecast").iterdir())


def test_air_discards_n_with_value():
    row = _all_n_row() | {"h05": "30", "v05": "N", "h06": "25", "v06": "V"}
    long = long_readings(pd.DataFrame([row]))
    assert list(long["ts"]) == [pd.Timestamp("2026-10-15 06:00")]
    assert list(long["value"]) == [25.0]


def test_air_uses_row_date_not_today():
    row = _all_n_row() | {"ano": "2020", "mes": "1", "dia": "1",
                          "h01": "10", "v01": "V", "h24": "12", "v24": "T"}
    long = long_readings(pd.DataFrame([row]))
    assert list(long["ts"]) == [pd.Timestamp("2020-01-01 01:00"), pd.Timestamp("2020-01-02 00:00")]
