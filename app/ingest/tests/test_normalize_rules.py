import pandas as pd
import pytest

from normalize.furniture import working_from_status
from normalize.sports import eiel_covered


@pytest.mark.parametrize("facility_type,sup_cubi,expected", [
    ("PISCINAS AL AIRE LIBRE", "350", False),     # vestuario cubierto, piscina al aire libre
    ("TERRENOS DE JUEGO", "120", False),
    ("PISTAS POLIDEPORTIVAS", "80", False),
    ("FRONTONES (SIN CUBRIR)", "40", False),
    ("PISCINAS CUBIERTAS", "0", True),
    ("POLIDEPORTIVOS CUBIERTOS", "", True),
    ("GIMNASIO", "0", True),
    ("COMPLEJOS POLIDEPORTIVOS", "1500", True),   # mixto: decide la superficie cubierta
    ("COMPLEJOS POLIDEPORTIVOS", "0", False),
    ("OTROS", "", None),                          # sin datos: no se sabe
])
def test_eiel_covered(facility_type, sup_cubi, expected):
    assert eiel_covered(facility_type, sup_cubi) is expected


def test_working_from_status():
    # nulo = sin dato: un banco sin ESTADO no es un banco roto
    status = pd.Series(["OPERATIVO", "FUERA_DE_SERVICIO", "", "  "])
    working = working_from_status(status)
    assert str(working.dtype) == "boolean"
    assert working[:2].tolist() == [True, False]
    assert working[2:].isna().all()


def test_keep_osm_rows(tmp_path):
    # graph.py anade el mobiliario OSM a poi.parquet; la recarga diaria de normalize no lo borra
    import geopandas as gpd
    from shapely.geometry import Point

    from normalize.furniture import keep_osm_rows

    columns = {"type": ["bench", "fountain"], "ine_code": ["28065", "28079"], "status": [None, None],
               "working": pd.array([pd.NA, True], dtype="boolean")}
    previous = gpd.GeoDataFrame({"id": ["osm:node/1", "ay_fuentes:9"], "source": ["osm", "ay_fuentes"], **columns},
                                geometry=[Point(-3.73, 40.30), Point(-3.70, 40.40)], crs=4326)
    previous.to_parquet(tmp_path / "poi.parquet")
    new = gpd.GeoDataFrame({"id": ["ay_fuentes:9"], "source": ["ay_fuentes"], "type": ["fountain"],
                            "ine_code": ["28079"], "status": [None], "working": pd.array([True], dtype="boolean")},
                           geometry=[Point(-3.70, 40.40)], crs=4326)
    out = keep_osm_rows(new, tmp_path / "poi.parquet")
    assert sorted(out["id"]) == ["ay_fuentes:9", "osm:node/1"]
    assert keep_osm_rows(new, tmp_path / "missing.parquet")["id"].tolist() == ["ay_fuentes:9"]
