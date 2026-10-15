"""Utilidades comunes de normalizacion (informe-datos §2 y §4)."""
import functools
import os
import pathlib
import unicodedata

import geopandas as gpd
import numpy as np
import pandas as pd
from pyproj import Transformer

ROOT = pathlib.Path(__file__).resolve().parent                                  # app/ingest
APP_DIR = ROOT.parent                                                           # app
DATA_DIR = pathlib.Path(os.environ.get("GOMAD_DATA_DIR", APP_DIR / "data"))     # volumen compartido
CONFIG_DIR = pathlib.Path(os.environ.get("GOMAD_CONFIG_DIR", APP_DIR / "config"))
RAW = DATA_DIR / "raw"
CLEAN = DATA_DIR / "clean"
_TO_WGS84 = Transformer.from_crs(25830, 4326, always_xy=True)
_ARTICLES = ("el", "la", "los", "las")


def to_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return None if pd.isna(v) else float(v)
    s = str(v).strip().replace(",", ".")
    try:
        return float(s) if s else None
    except ValueError:
        return None


def ine_code(v):
    if v is None:
        return None
    s = str(v).strip()
    if not s.isdigit():
        return None
    if len(s) == 5 and s.startswith("28"):
        return s
    if len(s) <= 3:
        return "28" + s.zfill(3)
    return None


def normalize_name(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode().lower().strip()
    for art in _ARTICLES:
        # "rozas de madrid (las)" y "alamo, el" -> articulo delante
        if s.endswith(f"({art})"):
            s = f"{art} " + s[: -len(art) - 2].strip()
        elif s.endswith(f", {art}"):
            s = f"{art} " + s[: -len(art) - 2].strip()
    return " ".join(s.replace("-", " ").split())


def to_wgs84(xs, ys):
    lon, lat = _TO_WGS84.transform(np.asarray(xs, dtype=float), np.asarray(ys, dtype=float))
    return np.asarray(lon), np.asarray(lat)


def read_csv(path, sep=";", nrows=None):
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            return pd.read_csv(path, sep=sep, dtype=str, encoding=encoding, keep_default_na=False, nrows=nrows)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Codificación no reconocida: {path}")


def latest_csv(folder, columns):
    """CSV mas reciente de la carpeta que trae todas las columnas pedidas.

    El Ayuntamiento cambia el nombre del fichero en cada publicacion y la descarga no borra el anterior;
    con --include-heavy baja ademas otros recursos del dataset con columnas distintas.
    """
    for path in sorted(pathlib.Path(folder).glob("*.csv"), key=lambda f: f.stat().st_mtime, reverse=True):
        header = read_csv(path, nrows=0).columns
        if all(c in header for c in columns):
            return path
    raise FileNotFoundError(f"Ningún CSV de {folder} tiene las columnas {list(columns)}")


def points(df, x, y, crs):
    xs, ys = df[x].map(to_float), df[y].map(to_float)
    ok = xs.notna() & ys.notna()
    df, xs, ys = df[ok].copy(), xs[ok].to_numpy(), ys[ok].to_numpy()
    if crs == 25830:
        xs, ys = to_wgs84(xs, ys)
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(xs, ys), crs=4326)


@functools.cache
def municipalities():
    g = gpd.read_file(RAW / "municipios" / "municipios.geojson")
    g = g.set_crs(25830, allow_override=True).to_crs(4326)
    g["ine_code"] = g["CDMUNICIPIO"].map(ine_code)
    g["name"] = g["DSMUNICIPIO"]
    g["name_norm"] = g["name"].map(normalize_name)
    return g[["ine_code", "name", "name_norm", "geometry"]]


def assign_municipality(gdf):
    missing = gdf["ine_code"].isna() if "ine_code" in gdf else pd.Series(True, index=gdf.index)
    if missing.any():
        joined = gpd.sjoin(gdf.loc[missing, ["geometry"]], municipalities()[["ine_code", "geometry"]],
                           how="left", predicate="within")
        joined = joined[~joined.index.duplicated()]
        gdf.loc[missing, "ine_code"] = joined["ine_code"]
    return gdf


def filter_region(gdf):
    region = municipalities().union_all()
    geom = gdf.geometry
    ok = ~((geom.x == 0) & (geom.y == 0)) if (geom.geom_type == "Point").all() else pd.Series(True, index=gdf.index)
    ok &= geom.intersects(region)
    return gdf[ok].copy(), int((~ok).sum())


def write(gdf, name):
    CLEAN.mkdir(parents=True, exist_ok=True)
    target = CLEAN / f"{name}.parquet"
    tmp = target.with_suffix(".tmp")
    gdf.to_parquet(tmp, index=False)
    os.replace(tmp, target)
    return target
