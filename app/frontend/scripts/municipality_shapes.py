"""Genera src/data/municipalityShapes.json: contornos simplificados de los 179 municipios para «Usar mi ubicacion».

Fuente: Comun:IDEM_V_MUNICIPIOS (app/data/raw/municipios/municipios.geojson, CC BY 4.0), la misma de la lista
estatica de P-09. Se ejecuta con el venv de ingest, desde app/frontend:
    ../ingest/.venv/bin/python scripts/municipality_shapes.py
"""
import json
import pathlib

import geopandas as gpd
import shapely

ROOT = pathlib.Path(__file__).resolve().parents[1]                       # app/frontend
SOURCE = ROOT.parent / "data" / "raw" / "municipios" / "municipios.geojson"
TARGET = ROOT / "src" / "data" / "municipalityShapes.json"
TOLERANCE = 0.0005                                                       # grados (~50 m)


def main():
    g = gpd.read_file(SOURCE).set_crs(25830, allow_override=True).to_crs(4326)
    shapes = {}
    for code, geom in zip(g["CDMUNICIPIO"], g.geometry):
        ine = "28" + str(code).strip().zfill(3)[-3:]
        simple = shapely.simplify(geom, TOLERANCE, preserve_topology=True)
        polygons = [simple] if simple.geom_type == "Polygon" else list(simple.geoms)
        shapes[ine] = [[[round(x, 4), round(y, 4)] for x, y in p.exterior.coords] for p in polygons]
    TARGET.write_text(json.dumps(shapes, separators=(",", ":"), sort_keys=True), encoding="utf-8")
    print(f"{TARGET}: {len(shapes)} municipios, {TARGET.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
