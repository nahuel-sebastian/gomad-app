"""Puntos de prevision de los 179 municipios (DEC-16, Task 72): lo unico que se envia a Open-Meteo."""
import csv
import importlib.util
import pathlib
import re

import geopandas as gpd
from shapely.geometry import Polygon

ROOT = pathlib.Path(__file__).resolve().parents[2]      # app/ingest
CSV = ROOT.parent / "config" / "forecast_points.csv"


def load_script():
    spec = importlib.util.spec_from_file_location("forecast_points", ROOT / "scripts" / "forecast_points.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_points_inside_polygon(tmp_path):
    square = Polygon([(-3.8, 40.3), (-3.7, 40.3), (-3.7, 40.4), (-3.8, 40.4)])
    # «C» cuyo centroide cae en el hueco
    c_shape = Polygon([(-4.0, 40.0), (-3.9, 40.0), (-3.9, 40.02), (-3.98, 40.02), (-3.98, 40.08),
                       (-3.9, 40.08), (-3.9, 40.1), (-4.0, 40.1)])
    path = tmp_path / "municipality.parquet"
    gpd.GeoDataFrame({"ine_code": ["28065", "28001"], "name": ["GETAFE", "C"]},
                     geometry=[square, c_shape], crs="EPSG:4326").to_parquet(path)
    got = load_script().points(path)
    assert [p[0] for p in got] == ["28001", "28065"]                      # ordenados por codigo
    assert got[1][2:] == (40.35, -3.75)                                    # centroide del cuadrado (lat, lon)
    from shapely.geometry import Point
    assert c_shape.contains(Point(got[0][3], got[0][2]))                  # dentro de la «C»


def test_repo_csv_has_179_points():
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    codes = [r["ine_code"] for r in rows]
    assert len(rows) == 179 and len(set(codes)) == 179 and codes == sorted(codes)
    assert all(re.fullmatch(r"28\d{3}", c) for c in codes)
    assert {"28065", "28079", "28131"} <= set(codes)
    for r in rows:
        assert 39.8 <= float(r["lat"]) <= 41.2 and -4.6 <= float(r["lon"]) <= -3.0, r
