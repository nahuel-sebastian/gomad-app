import pathlib

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
    # VPLA republicado (descarga del 16/10): entra Sevilla la Nueva (28141); antes 166
    assert m["in_vpla"].sum() == 167 and m["in_eiel"].sum() == 155


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
    # «Zonas Verdes y Espacios Libres». VPLA republicado (16/10): 17.010 (antes 16.867), +143 de Sevilla la Nueva
    assert len(vpla) == 17_010
    # 167 municipios en VPLA, pero 4 sin zonas verdes (El Atazar, Cervera de Buitrago, Gargantilla, Tielmes)
    assert vpla.ine_code.nunique() == 163 and (vpla.ine_code == "28141").sum() == 143
    getafe = vpla[vpla.ine_code == "28065"]
    assert len(getafe) == 648 and round(getafe.area_m2.sum() / 1e6, 1) == 33.4   # informe-datos §3


def test_poi():
    # graph.py anade el mobiliario OSM a poi.parquet: la recarga de normalize no debe borrarlo
    before = set(read("poi").query("source == 'osm'")["id"]) if (CLEAN / "poi.parquet").exists() else set()
    R["poi"]()
    p = read("poi")
    check_points(p)
    assert set(p.loc[p.source == "osm", "id"]) == before
    p = p[p.source != "osm"]                                                 # el mobiliario OSM lo anade graph.py
    assert (p["type"] == "bench").sum() >= 76_000                             # ay_bancos por COORD_GIS (76.627)
    assert (p["type"] == "dog_area").sum() == 112
    assert (p["type"] == "aed").sum() > 12_000


def test_destination_raw_names_and_flags():
    # nombre obligatorio en la API (DestinationSummary.name: str); banderas booleanas con nulos, no double
    d = read("destination_raw")
    assert d["name"].notna().all() and (d["name"].str.strip() != "").all()
    for col in ("covered", "accessible", "water"):
        assert str(d[col].dtype) == "boolean", col
    eiel = d[d.source == "eiel_deporte"]
    outdoor = eiel.facility_type.isin(["PISCINAS AL AIRE LIBRE", "TERRENOS DE JUEGO", "PISTAS POLIDEPORTIVAS"])
    assert not eiel.loc[outdoor, "covered"].any()


def test_poi_keeps_broken_fountains_flagged():
    # las fuentes cerradas se guardan marcadas (mapa en gris, informe de averias); la ruta usa solo working
    from common import RAW, latest_csv, read_csv
    raw = read_csv(latest_csv(RAW / "ay_fuentes", ["ID", "ESTADO"])).set_index("ID")
    p = read("poi")
    assert str(p["working"].dtype) == "boolean"
    fountains = p[p.source == "ay_fuentes"].set_index("id")
    assert len(fountains) == len(raw)                                     # ninguna se pierde
    status = raw.loc[fountains.index.str.removeprefix("ay_fuentes:"), "ESTADO"].to_numpy()
    assert (fountains["status"].to_numpy() == status).all()
    assert (fountains["working"].to_numpy(dtype=bool) == (status == "OPERATIVO")).all()
    assert (~fountains["working"]).sum() == 1_045
    assert p.loc[p.source == "desfibriladores", "working"].isna().all()   # sin estado en origen: no se sabe


def test_population_write_is_atomic(tmp_path, monkeypatch):
    import common
    import normalize.population as population
    target = tmp_path / "population.parquet"
    target.write_bytes(b"old")
    monkeypatch.setattr(common, "CLEAN", tmp_path)
    if hasattr(population, "CLEAN"):
        monkeypatch.setattr(population, "CLEAN", tmp_path)

    def broken(self, path, *args, **kwargs):
        pathlib.Path(path).write_bytes(b"partial")
        raise OSError("disco lleno")

    monkeypatch.setattr(pd.DataFrame, "to_parquet", broken)
    with pytest.raises(OSError):
        population.run()
    assert target.read_bytes() == b"old"
