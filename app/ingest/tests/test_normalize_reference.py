import geopandas as gpd
import pandas as pd
import pytest

from common import CLEAN, municipalities
from normalize import load_all

pytestmark = pytest.mark.slow
R = load_all()


def read(name):
    return gpd.read_parquet(CLEAN / f"{name}.parquet")


def check_points(gdf):
    assert gdf.crs.to_epsg() == 4326
    assert gdf["ine_code"].dropna().str.match(r"^28\d{3}$").all()
    region = municipalities().union_all().buffer(0.01)
    assert gdf.geometry.representative_point().within(region).all()


def test_municipality():
    R["municipality"]()
    m = read("municipality")
    assert len(m) == 179
    assert m.loc[m.ine_code == "28065", "in_eiel"].item() is False   # Getafe no esta en EIEL
    assert m.loc[m.ine_code == "28079", "in_vpla"].item() is False   # capital fuera de VPLA
    assert m["in_vpla"].sum() == 166 and m["in_eiel"].sum() == 155


def test_population():
    R["population"]()
    p = pd.read_parquet(CLEAN / "population.parquet")
    latest = p[p.year == p.year.max()]
    assert latest["ine_code"].nunique() == 179
    assert latest.loc[latest.ine_code == "28079", "population"].item() > 3_000_000


def test_destination_raw():
    R["destination_raw"]()
    d = read("destination_raw")
    check_points(d)
    assert d["id"].is_unique
    assert (d.source == "eiel_deporte").sum() == 726
    assert (d[d.source == "nmc_deporte"].ine_code == "28065").sum() == 19
    assert d[d.source == "nmc_deporte"].ine_code.nunique() == 178
    eiel = d[d.source == "eiel_deporte"]
    assert eiel["sports"].map(lambda xs: "PADEL" in xs).sum() == 154
    assert eiel["sports"].map(lambda xs: "NATACION" in xs).sum() == 0     # columna vacia (CLAUDE.md §8)


def test_green():
    R["green"]()
    v = read("green")
    vpla = v[v.source == "vpla_redes"]
    assert len(vpla) == 16_867                                             # «Zonas Verdes y Espacios Libres»
    # 166 municipios en VPLA, pero 4 sin zonas verdes (El Atazar, Cervera de Buitrago, Gargantilla, Tielmes)
    assert vpla.ine_code.nunique() == 162
    getafe = vpla[vpla.ine_code == "28065"]
    assert len(getafe) == 648 and round(getafe.area_m2.sum() / 1e6, 1) == 33.4   # informe-datos §3


def test_poi():
    R["poi"]()
    p = read("poi")
    check_points(p)
    assert (p["type"] == "bench").sum() >= 76_000                             # ay_bancos por COORD_GIS (76.627)
    assert (p["type"] == "dog_area").sum() == 112
    assert (p["type"] == "aed").sum() > 12_000
