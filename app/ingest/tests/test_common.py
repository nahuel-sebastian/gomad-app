import os

import numpy as np
import pandas as pd
import pytest

import common


@pytest.mark.parametrize("v,expected", [("40,123", 40.123), ("40.5", 40.5), ("", None), (None, None),
                                        (" -3,7 ", -3.7), ("abc", None), (12, 12.0)])
def test_to_float(v, expected):
    assert common.to_float(v) == expected


@pytest.mark.parametrize("v,expected", [("6", "28006"), ("079", "28079"), ("28079", "28079"), (65, "28065"),
                                        ("", None), ("RESERVADO", None), (None, None)])
def test_ine_code(v, expected):
    assert common.ine_code(v) == expected


def test_normalize_name():
    assert common.normalize_name("Rozas de Madrid (Las)") == common.normalize_name("LAS ROZAS DE MADRID")
    assert common.normalize_name("Álamo, El") == common.normalize_name("El Álamo")


def test_reprojection_getafe():
    # portal de prueba de D-04 (calle Madrid 10, Getafe): x 437838,98 / y 4461942,01
    lon, lat = common.to_wgs84(np.array([437838.98]), np.array([4461942.01]))
    assert -3.8 < lon[0] < -3.65 and 40.25 < lat[0] < 40.35


def test_read_csv_cp1252(tmp_path):
    path = tmp_path / "x.csv"
    path.write_bytes("Territorio;Valor\nMóstoles;1\n".encode("cp1252"))
    assert common.read_csv(path).loc[0, "Territorio"] == "Móstoles"


def test_read_csv_utf8_bom(tmp_path):
    path = tmp_path / "x.csv"
    path.write_bytes("﻿municipio;valor\nGetafe;1\n".encode("utf-8"))
    assert list(common.read_csv(path).columns) == ["municipio", "valor"]


def test_data_dir_is_shared_app_data():
    assert common.DATA_DIR.name == "data" and common.DATA_DIR.parent == common.APP_DIR


@pytest.mark.slow
def test_there_are_179_municipalities():
    m = common.municipalities()
    assert len(m) == 179 and m["ine_code"].str.match(r"^28\d{3}$").all()
    assert m.crs.to_epsg() == 4326


@pytest.mark.slow
def test_filter_region_drops_outside_and_zeros():
    df = pd.DataFrame({"x": [437838.98, 0, 100000], "y": [4461942.01, 0, 4000000]})
    inside, dropped = common.filter_region(common.points(df, "x", "y", 25830))
    assert len(inside) == 1 and dropped == 2


def test_latest_csv_prefers_newest_with_expected_columns(tmp_path):
    # el Ayuntamiento cambia el nombre del fichero cada dia y --include-heavy baja recursos con otras columnas
    old = tmp_path / "300095_20261013.csv"
    new = tmp_path / "300095_20261014.csv"
    other = tmp_path / "300095-10.csv"
    old.write_text("ID;COORD_GIS_X\n1;2\n", encoding="utf-8")
    new.write_text("ID;COORD_GIS_X\n3;4\n", encoding="utf-8")
    other.write_text("DISTRITO;TOTAL\nx;1\n", encoding="utf-8")
    os.utime(old, (1_000, 1_000))
    os.utime(new, (2_000, 2_000))
    os.utime(other, (3_000, 3_000))
    assert common.latest_csv(tmp_path, ["ID", "COORD_GIS_X"]) == new


def test_latest_csv_without_match_raises(tmp_path):
    (tmp_path / "a.csv").write_text("X;Y\n1;2\n", encoding="utf-8")
    with pytest.raises(FileNotFoundError):
        common.latest_csv(tmp_path, ["ID"])
