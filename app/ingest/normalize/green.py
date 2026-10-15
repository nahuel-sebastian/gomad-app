import geopandas as gpd

from common import RAW, ine_code, points, read_csv, to_float, write
from normalize import normalizer

YES_VALUES = ("SI", "EXISTE SERVICIO")   # literales reales: IT_FUENTE "SI"/vacio; AGUA "EXISTE SERVICIO"/"NO EXISTE SERVICIO"


def vpla_green():
    g = gpd.read_file(RAW / "vpla_redes" / "vpla_redes.geojson").set_crs(25830, allow_override=True)
    g = g[g["DS_USO_GENE"] == "Zonas Verdes y Espacios Libres"].to_crs(4326)
    g["id"] = "vpla_redes:" + g["CDID"].astype(str)
    g["source"], g["ine_code"], g["use_detail"] = "vpla_redes", g["CD_MUNICIPIO"].map(ine_code), g["DS_USO_DETA"]
    g["area_m2"] = g["NM_AREA"].map(to_float)
    return g[["id", "source", "ine_code", "use_detail", "area_m2", "geometry"]]


def green_destinations():
    """Parques y areas como destinos puntuales (type park / recreation_area)."""
    v = vpla_green()
    p1 = v.assign(geometry=v.geometry.representative_point(), source_id=v["id"].str.split(":").str[1],
                  name=v["use_detail"], type="park", covered=False, label=v["use_detail"])
    e = gpd.read_file(RAW / "eiel_parques" / "eiel_parques.geojson").set_crs(25830, allow_override=True).to_crs(4326)
    p2 = e.assign(geometry=e.geometry.representative_point(),
                  source_id=e[["PROV", "MUN", "ENT", "POBLAMIENT", "ORDEN_PARQ"]].astype(str).agg("-".join, axis=1),
                  source="eiel_parques", name=e["NOMBRE"], type="park", covered=False,
                  water=e["AGUA"].map(lambda x: str(x).strip().upper() in YES_VALUES if x else None),
                  condition=e["ESTADO"], label=e["TIPOPARQUE"], ine_code=e["MUN"].map(ine_code))
    n = gpd.read_file(next((RAW / "nmc_parques").glob("*.shp")), ignore_geometry=True)   # .prj erroneo (informe §2.2)
    n = points(n, "UTM_X", "UTM_Y", 25830)
    p3 = n.assign(source_id=n.index.astype(str), source="nmc_parques", name=n["ETIQUETA"], type="park",
                  covered=False, ine_code=n["CMUN"].map(ine_code))
    a = gpd.read_file(RAW / "areas_recreativas" / "areas_recreativas.geojson", ignore_geometry=True)
    a = points(a, "NM_COOX", "NM_COOY", 25830)
    # sin codigo de municipio (DS_MUNI es nombre): assign_municipality lo pone por geometria
    p4 = a.assign(source_id=a.index.astype(str), source="areas_recreativas", name=a["DS_NOMBRE"],
                  type="recreation_area", covered=False, ine_code=None,
                  water=a["IT_FUENTE"].map(lambda x: str(x).strip().upper() in YES_VALUES))
    ay = points(read_csv(next((RAW / "ay_parques").glob("*.csv"))), "LONGITUD", "LATITUD", 4326)
    p5 = ay.assign(source_id=ay["PK"], source="ay_parques", name=ay["NOMBRE"], type="park", covered=False,
                   ine_code="28079", url=ay["CONTENT-URL"])
    for p in (p1, p2, p3, p4, p5):
        if "sports" not in p:
            p["sports"] = [[] for _ in range(len(p))]
    return [p1, p2, p3, p4, p5]


@normalizer("green")
def run():
    return write(vpla_green(), "green")
