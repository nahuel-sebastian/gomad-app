"""Servicios de la Comunidad -> clean/service.parquet (V-D1, DEC-09).

Una fila por servicio con municipio conocido. ine_code: el que declara la fuente (nombre o codigo), salvo
farmacias y DEA, que van por cruce espacial con municipality.geom. Geometria en EPSG:4326, nula si la fuente
no trae coordenadas o caen fuera de la Comunidad: la fila sigue contando en los indicadores, el mapa no la pinta.
"""
import geopandas as gpd
import pandas as pd

from common import (RAW, assign_municipality, filter_region, ine_code, latest_csv, municipalities, normalize_name,
                    read_csv, to_float, to_wgs84, write)
from normalize import normalizer

COLUMNS = ["id", "source", "category", "subtype", "ine_code", "geometry"]
SPATIAL = ("farmacias", "desfibriladores")


def located(df, x, y, crs):
    """Todas las filas de df con su punto; nulo si falta una coordenada. Acepta coma decimal."""
    xs = df[x].map(to_float).to_numpy(dtype=float)
    ys = df[y].map(to_float).to_numpy(dtype=float)
    ok = ~(pd.isna(xs) | pd.isna(ys))
    if crs == 25830 and ok.any():
        xs[ok], ys[ok] = to_wgs84(xs[ok], ys[ok])
    g = gpd.GeoDataFrame(df.reset_index(drop=True), geometry=gpd.points_from_xy(xs, ys), crs=4326)
    g.loc[~ok, "geometry"] = None
    return g


def _frame(g, source, category, ids, subtype, ine):
    return g.assign(id=source + ":" + ids.astype(str).str.strip(), source=source, category=category,
                    subtype=subtype, ine_code=ine)[COLUMNS]


def health(df, by_name):
    """sanitarios trae una fila por servicio: una por centro (centro_tipo y coordenada son del centro)."""
    g = located(df.drop_duplicates("centro_nro_registro"), "localizacion_coordenada_x", "localizacion_coordenada_y",
                25830)
    return _frame(g, "sanitarios", "health", g["centro_nro_registro"], g["centro_tipo"].str.strip(),
                  g["municipio_nombre"].map(normalize_name).map(by_name))


def pharmacies(df, by_name):
    g = located(df, "LOCALIZACION_COORDENADA_X", "LOCALIZACION_COORDENADA_Y", 25830)
    return _frame(g, "farmacias", "pharmacy", g["FARMACIA_NRO_SOE"], None,
                  g["MUNICIPIO_NOMBRE"].map(normalize_name).map(by_name))


def schools(df):
    """Solo SITUACIÓN = ALTA (hay 3.552 de baja)."""
    g = located(df[df["SITUACIÓN"].str.strip() == "ALTA"], "UTM_X", "UTM_Y", 25830)
    return _frame(g, "educativos", "education", g["CODIGO"], g["TIPO_EXT"].str.strip(), g["CDMUNI"].map(ine_code))


def social(df):
    """Fuera los centros protegidos: direccion_coor_x «RESERVADO» (tambien municipio y calle)."""
    g = located(df[df["direccion_coor_x"].str.strip() != "RESERVADO"], "direccion_coor_x", "direccion_coor_y", 25830)
    return _frame(g, "atencion_social", "social", g["numero_registro"], g["tipo"].str.strip(),
                  g["municipio_codigo"].map(ine_code))


def aeds(df):
    """Mismas coordenadas que route_poi aed (furniture.py); municipio_codigo solo de respaldo sin coordenadas."""
    g = located(df.drop_duplicates("codigo_dea"), "direccion_coordenada_x", "direccion_coordenada_y", 25830)
    return _frame(g, "desfibriladores", "aed", g["codigo_dea"], g["tipo_establecimiento"].str.strip(),
                  g["municipio_codigo"].map(ine_code))


def build(parts):
    out = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), geometry="geometry", crs=4326)
    has = out.geometry.notna()
    inside, outside = filter_region(out[has])
    out.loc[has & ~out.index.isin(inside.index), "geometry"] = None
    spatial = out["source"].isin(SPATIAL) & out.geometry.notna()
    joined = assign_municipality(out.loc[spatial, ["geometry"]].assign(ine_code=None))
    out.loc[spatial, "ine_code"] = joined["ine_code"]
    dropped = int(out["ine_code"].isna().sum())
    out = out[out["ine_code"].notna()].reset_index(drop=True)
    print(f"   service: {len(out)} servicios ({outside} fuera de la Comunidad sin punto, {dropped} sin municipio):",
          out["category"].value_counts().to_dict())
    return out


@normalizer("services")
def run():
    by_name = dict(zip(municipalities()["name_norm"], municipalities()["ine_code"]))
    def raw(source, columns):
        return read_csv(latest_csv(RAW / source, columns))
    parts = [
        health(raw("sanitarios", ["centro_nro_registro", "centro_tipo", "municipio_nombre"]), by_name),
        pharmacies(raw("farmacias", ["FARMACIA_NRO_SOE", "MUNICIPIO_NOMBRE"]), by_name),
        schools(raw("educativos", ["CODIGO", "CDMUNI", "SITUACIÓN"])),
        social(raw("atencion_social", ["numero_registro", "municipio_codigo", "direccion_coor_x"])),
        aeds(raw("desfibriladores", ["codigo_dea", "municipio_codigo", "direccion_coordenada_x"])),
    ]
    return write(build(parts), "service")
