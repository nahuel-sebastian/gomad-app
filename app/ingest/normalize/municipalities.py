import geopandas as gpd

from common import RAW, ine_code, municipalities, write
from normalize import normalizer


@normalizer("municipality")
def run():
    m = municipalities().copy()
    eiel = gpd.read_file(RAW / "eiel_deporte" / "eiel_deporte.geojson", columns=["MUN"], ignore_geometry=True)
    vpla = gpd.read_file(RAW / "vpla_redes" / "vpla_redes.geojson", columns=["CD_MUNICIPIO"], ignore_geometry=True)
    # los 155 municipios de EIEL son los que tienen filas en la capa de deporte
    m["in_eiel"] = m["ine_code"].isin(set(eiel["MUN"].map(ine_code)))
    m["in_vpla"] = m["ine_code"].isin(set(vpla["CD_MUNICIPIO"].map(ine_code)))
    return write(m, "municipality")
