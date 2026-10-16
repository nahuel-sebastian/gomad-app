import re

import geopandas as gpd

from common import RAW, ine_code, latest_csv, municipalities, read_csv, write
from normalize import normalizer

ARTICLE = re.compile(r"^(.*?)\s*\(([^)]+)\)$")     # «Rozas de Madrid (Las)»


def display_name(name):
    """Nombre del padron para mostrar, con el articulo delante: «Rozas de Madrid (Las)» -> «Las Rozas de Madrid»."""
    name = name.strip()
    m = ARTICLE.match(name)
    return f"{m.group(2)} {m.group(1)}" if m else name


def padron_names():
    """{ine_code: nombre} del padron (con tildes y mayusculas correctas), del ultimo año publicado."""
    df = read_csv(latest_csv(RAW / "padron", ["Año", "Tipo territorio", "Código territorio", "Territorio"]))
    df = df[(df["Tipo territorio"] == "Municipios") & (df["Código territorio"].str.strip().str.len() == 4)]
    df = df[df["Año"] == df["Año"].max()]
    # «Código territorio» = codigo INE de 3 digitos + digito de control (population.py)
    return {ine_code(c.strip()[:3]): display_name(t) for c, t in zip(df["Código territorio"], df["Territorio"])}


@normalizer("municipality")
def run():
    m = municipalities().copy()
    # la capa trae el nombre en MAYUSCULAS y sin tildes («ALCALA DE HENARES»); el del padron, si esta, para mostrar
    m["name"] = m["ine_code"].map(padron_names()).fillna(m["name"])
    eiel = gpd.read_file(RAW / "eiel_deporte" / "eiel_deporte.geojson", columns=["MUN"], ignore_geometry=True)
    vpla = gpd.read_file(RAW / "vpla_redes" / "vpla_redes.geojson", columns=["CD_MUNICIPIO"], ignore_geometry=True)
    # los 155 municipios de EIEL son los que tienen filas en la capa de deporte
    m["in_eiel"] = m["ine_code"].isin(set(eiel["MUN"].map(ine_code)))
    m["in_vpla"] = m["ine_code"].isin(set(vpla["CD_MUNICIPIO"].map(ine_code)))
    return write(m, "municipality")
