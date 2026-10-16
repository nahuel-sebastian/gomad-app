#!/usr/bin/env python3
"""Genera app/config/forecast_points.csv: un punto por municipio para pedir la prevision a Open-Meteo (DEC-16).

Es lo unico que se envia a Open-Meteo (CLAUDE.md 2.8: nunca la ubicacion de la persona). Regla del punto, la misma
que Geocoder.municipalities de la API: centroide del contorno si cae dentro; si no, point_on_surface.
Uso: python scripts/forecast_points.py   (lee data/clean/municipality.parquet; rehacer si cambian los limites)
"""
import csv
import os
import pathlib
import sys

import pyarrow.parquet as pq
import shapely

ROOT = pathlib.Path(__file__).resolve().parent.parent       # app/ingest
APP_DIR = ROOT.parent
DATA_DIR = pathlib.Path(os.environ.get("GOMAD_DATA_DIR", APP_DIR / "data"))
CONFIG_DIR = pathlib.Path(os.environ.get("GOMAD_CONFIG_DIR", APP_DIR / "config"))


def points(parquet_path):
    """[(ine, nombre, lat, lon)] ordenado por codigo, con 4 decimales (~10 m)."""
    t = pq.read_table(parquet_path, columns=["ine_code", "name", "geometry"]).to_pydict()
    out = []
    for ine, name, wkb in zip(t["ine_code"], t["name"], t["geometry"]):
        poly = shapely.from_wkb(wkb)
        center = poly.centroid if poly.contains(poly.centroid) else poly.point_on_surface()
        out.append((ine, name.title(), round(center.y, 4), round(center.x, 4)))
    return sorted(out)


def main():
    rows = points(DATA_DIR / "clean" / "municipality.parquet")
    target = CONFIG_DIR / "forecast_points.csv"
    with target.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["ine_code", "name", "lat", "lon"])
        w.writerows(rows)
    print(f"{len(rows)} puntos -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
