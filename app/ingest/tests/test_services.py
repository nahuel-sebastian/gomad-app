import geopandas as gpd
import pandas as pd
import pytest

from common import CLEAN, RAW, latest_csv, municipalities, read_csv, to_wgs84
from normalize import load_all
import normalize.services as services
from normalize.services import build, health, located, schools, social

HEALTH_TYPES = {"Centro de salud", "Consultorio de atención primaria"}


def test_located_parses_comma_decimal_and_keeps_rows_without_coordinates():
    df = pd.DataFrame({"x": ["440267,13", ""], "y": ["4475425,75", "4475425"]})
    g = located(df, "x", "y", 25830)
    lon, lat = to_wgs84([440267.13], [4475425.75])
    assert len(g) == 2 and g.crs.to_epsg() == 4326
    assert g.geometry.iloc[0].x == pytest.approx(lon[0]) and g.geometry.iloc[0].y == pytest.approx(lat[0])
    assert g.geometry.iloc[1] is None


def test_health_one_row_per_centre_by_name():
    df = pd.DataFrame({"centro_nro_registro": ["C1", "C1", "C2"],
                       "centro_tipo": ["Centro de salud", "Centro de salud", "Clínica dental"],
                       "municipio_nombre": ["Rozas de Madrid (Las)", "Rozas de Madrid (Las)", "Getafe"],
                       "localizacion_coordenada_x": ["", "", "437838"],
                       "localizacion_coordenada_y": ["", "", "4461942"]})
    g = health(df, {"las rozas de madrid": "28127", "getafe": "28065"})
    assert list(g["id"]) == ["sanitarios:C1", "sanitarios:C2"]
    assert list(g["ine_code"]) == ["28127", "28065"] and g.geometry.iloc[0] is None
    assert list(g["subtype"]) == ["Centro de salud", "Clínica dental"]


def test_schools_only_alta_and_social_without_reserved():
    s = schools(pd.DataFrame({"CODIGO": ["1", "2"], "TIPO_EXT": ["CEIP", "CEIP"], "CDMUNI": ["65", "065"],
                              "UTM_X": ["437838", ""], "UTM_Y": ["4461942", ""], "SITUACIÓN": ["ALTA", "BAJA"]}))
    assert list(s["id"]) == ["educativos:1"] and list(s["ine_code"]) == ["28065"]
    a = social(pd.DataFrame({"numero_registro": ["C1", "C2"], "tipo": ["RESIDENCIAS", "RESIDENCIAS"],
                             "municipio_codigo": ["079", "RESERVADO"],
                             "direccion_coor_x": ["443644", "RESERVADO"], "direccion_coor_y": ["4476188", "RESERVADO"]}))
    assert list(a["id"]) == ["atencion_social:C1"] and list(a["ine_code"]) == ["28079"]


def test_spatial_join_keeps_declared_municipality_when_it_finds_none(monkeypatch):
    # un punto en un hueco o en el borde exacto entre poligonos no pierde el municipio que declara la fuente
    monkeypatch.setattr(services, "filter_region", lambda g: (g, 0))
    monkeypatch.setattr(services, "assign_municipality", lambda g: g.assign(ine_code=None))
    pts = gpd.GeoDataFrame({"id": ["farmacias:1", "desfibriladores:1"], "source": ["farmacias", "desfibriladores"],
                            "category": ["pharmacy", "aed"], "subtype": [None, None], "ine_code": ["28065", None]},
                           geometry=gpd.points_from_xy([-3.73, -3.74], [40.30, 40.31]), crs=4326)
    out = build([pts])
    assert list(out["id"]) == ["farmacias:1"] and list(out["ine_code"]) == ["28065"]


@pytest.fixture(scope="module")
def service():
    load_all()["services"]()
    return gpd.read_parquet(CLEAN / "service.parquet")


@pytest.mark.slow
def test_service_points_inside_region(service):
    assert service.crs.to_epsg() == 4326
    assert service["id"].is_unique
    assert service["ine_code"].str.match(r"^28\d{3}$").all()
    assert set(service["category"]) == {"health", "pharmacy", "education", "social", "aed"}
    region = municipalities().union_all()
    assert service.geometry.dropna().intersects(region).all()


@pytest.mark.slow
def test_health_centres(service):
    # division: 429; la descarga del 16/10 trae 430 (Ruling en el ledger)
    hc = service[(service.category == "health") & service.subtype.isin(HEALTH_TYPES)]
    assert len(hc) == 430 and hc.ine_code.nunique() == 179


@pytest.mark.slow
def test_schools_alta(service):
    s = service[service.category == "education"]
    assert len(s) == 3906 and s.ine_code.nunique() == 156


@pytest.mark.slow
def test_social_without_reserved(service):
    raw = read_csv(latest_csv(RAW / "atencion_social", ["numero_registro", "direccion_coor_x"]))
    reserved = "atencion_social:" + raw.loc[raw.direccion_coor_x == "RESERVADO", "numero_registro"]
    assert len(reserved) == 175                                   # division: 177 (Ruling en el ledger)
    s = service[service.category == "social"]
    assert not s["id"].isin(reserved).any() and len(s) == len(raw) - len(reserved)
    assert not s["subtype"].eq("RESERVADO").any()


@pytest.mark.slow
def test_aed_and_pharmacies_by_spatial_join(service):
    aed = service[service.category == "aed"]
    assert aed.ine_code.nunique() == 172                          # municipio_codigo daria 162
    assert aed.geometry.notna().all()
    assert service[service.category == "pharmacy"].ine_code.nunique() == 160
