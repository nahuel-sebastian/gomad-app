import geopandas as gpd
import pandas as pd

from common import RAW, assign_municipality, filter_region, ine_code, latest_csv, points, read_csv, to_float, write
from normalize import normalizer

SPORT_COLUMNS = ["SUBACUATIC", "ATLETISMO", "BEISBOL", "BALONCESTO", "BALONMANO", "BOLOS", "BALONVOLEA",
                 "DEPINVIERN", "ESQUINAUTI", "FUTBOL", "GOLF", "GIMNASIA", "JUDOKARATE", "LUCHA", "NATACION",
                 "OTROS", "PADEL", "PELOTA", "PIRAGUISMO", "PATINAJE", "REMO", "TENIS", "TIROALPLAT", "VELA"]
COLUMNS = ["id", "source", "source_id", "name", "type", "covered", "accessible", "condition", "owner", "water",
           "sports", "facility_type", "label", "area_m2", "url", "ine_code", "geometry"]


# TIPOINSTAL decide si la instalacion es cubierta: SUP_CUBI > 0 tambien lo cumplen piscinas al aire libre
# o campos con vestuario o grada cubiertos. Los tipos mixtos (complejos, otros) se deciden por SUP_CUBI.
OUTDOOR_TYPES = ("AIRE LIBRE", "SIN CUBRIR", "PISTAS POLIDEPORTIVAS", "TERRENOS DE JUEGO", "ESCUELA DE VELA",
                 "ESTACIONES DE ESQUI", "PUERTO DEPORTIVO")
COVERED_TYPES = ("CUBIERT", "GIMNASIO")
# nombre por defecto cuando la fuente no trae ninguno (DS_USO_DETA vacio en VPLA)
DEFAULT_NAMES = {"facility": "Instalación deportiva", "park": "Zona verde", "recreation_area": "Área recreativa"}
FLAGS = ("covered", "accessible", "water")


def eiel_covered(facility_type, sup_cubi):
    kind = str(facility_type or "").upper()
    if any(t in kind for t in OUTDOOR_TYPES):
        return False
    if any(t in kind for t in COVERED_TYPES):
        return True
    area = to_float(sup_cubi)
    return None if area is None else area > 0


def is_yes(v):
    return str(v).strip().upper() == "SI"


def eiel_sports():
    g = gpd.read_file(RAW / "eiel_deporte" / "eiel_deporte.geojson").set_crs(25830, allow_override=True).to_crs(4326)
    g["geometry"] = g.geometry.representative_point()
    g["source_id"] = g[["PROV", "MUN", "ENT", "POBLAMIENT", "ORDEN_INST"]].astype(str).agg("-".join, axis=1)
    g["source"], g["type"] = "eiel_deporte", "facility"
    g["name"] = g["NOMBRE"]
    g["covered"] = [eiel_covered(t, v) for t, v in zip(g["TIPOINSTAL"], g["SUP_CUBI"])]
    g["accessible"] = g["ACCESOSILL"].map(lambda v: None if not v else not str(v).upper().startswith("SIN"))
    g["condition"], g["owner"], g["facility_type"] = g["ESTADO"], g["TITULAR"], g["TIPOINSTAL"]
    g["sports"] = g[SPORT_COLUMNS].apply(lambda row: [c for c in SPORT_COLUMNS if is_yes(row[c])], axis=1)
    g["ine_code"] = g["MUN"].map(ine_code)
    return g


def nmc_sports():
    df = gpd.read_file(next((RAW / "nmc_deporte").glob("*.shp")), ignore_geometry=True)   # .prj no fiable
    g = points(df, "UTM_X", "UTM_Y", 25830)
    # ID_APP se repite en instalaciones distintas del mismo complejo (33 ids, 69 filas):
    # se numeran por orden estable de nombre y coordenadas -> "794536-1", "794536-2"
    g["source_id"] = g["ID_APP"].astype(str).str.strip()
    g = g.sort_values(["source_id", "DESCR", "UTM_X", "UTM_Y"])
    repeated = g["source_id"].duplicated(keep=False)
    n = g.groupby("source_id").cumcount() + 1
    g.loc[repeated, "source_id"] = g.loc[repeated, "source_id"] + "-" + n[repeated].astype(str)
    g["source"], g["type"] = "nmc_deporte", "facility"
    g["name"], g["label"], g["url"] = g["DESCR"], g["ETIQUETA"], g["URL"]
    g["ine_code"] = g["CMUN"].map(ine_code)
    g["sports"] = [[] for _ in range(len(g))]
    return g


def city_council(source):
    g = points(read_csv(latest_csv(RAW / source, ["PK", "NOMBRE", "LATITUD", "LONGITUD"])), "LONGITUD", "LATITUD", 4326)
    g["source_id"], g["source"], g["type"] = g["PK"], source, "facility"
    g["name"], g["url"], g["label"] = g["NOMBRE"], g["CONTENT-URL"], g["EQUIPAMIENTO"]
    g["ine_code"] = "28079"
    g["sports"] = [[] for _ in range(len(g))]
    return g


@normalizer("destination_raw")
def run():
    from normalize.green import green_destinations   # los parques tambien son destinos
    parts = [eiel_sports(), nmc_sports()] + [city_council(s) for s in ("ay_polideportivos", "ay_idb", "ay_piscinas")]
    parts += green_destinations()
    alldest = pd.concat([p.reindex(columns=COLUMNS) for p in parts], ignore_index=True)
    alldest["id"] = alldest["source"] + ":" + alldest["source_id"].astype(str)
    blank = alldest["name"].isna() | (alldest["name"].astype(str).str.strip() == "")
    alldest.loc[blank, "name"] = alldest.loc[blank, "type"].map(DEFAULT_NAMES)
    for col in FLAGS:
        alldest[col] = alldest[col].astype("boolean")
    alldest = gpd.GeoDataFrame(alldest, geometry="geometry", crs=4326)
    alldest = assign_municipality(alldest)
    alldest, dropped = filter_region(alldest)
    print(f"   destination_raw: {len(alldest)} destinos, {dropped} fuera de la Comunidad descartados")
    return write(alldest, "destination_raw")
