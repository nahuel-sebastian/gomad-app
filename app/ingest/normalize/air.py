"""Aire: estaciones de las dos redes (CM y Ayuntamiento) y lecturas horarias en formato largo."""
import datetime as dt

import geopandas as gpd
import pandas as pd

from common import CLEAN, RAW, ine_code, latest_csv, points, read_csv, to_float, write
from normalize import normalizer

AQI_MAGNITUDES = {1, 8, 9, 10, 14}   # SO2, NO2, PM2.5, PM10, O3 (umbrales.md §1.2)
READING_COLUMNS = ["station_id", "magnitude", "ts", "value", "flag"]


def long_readings(df):
    """h01..h24 / v01..v24 -> una fila por hora. ts = fin de la hora (h24 = 00:00 del dia siguiente).

    Fecha por fila (ano, mes, dia): de madrugada el fichero regional trae el dia anterior.
    Se aceptan T (temporal) y V (valido); N se descarta.
    """
    df = df.rename(columns=str.lower)
    rows = []
    for _, r in df.iterrows():
        magnitude = int(r["magnitud"])
        if magnitude not in AQI_MAGNITUDES:
            continue
        station = f"{ine_code(r['municipio'])}{int(r['estacion']):03d}"
        day = dt.datetime(int(r["ano"]), int(r["mes"]), int(r["dia"]))
        for h in range(1, 25):
            value, flag = to_float(r[f"h{h:02d}"]), str(r[f"v{h:02d}"]).strip().upper()
            if value is None or flag not in ("T", "V"):
                continue
            rows.append((station, magnitude, day + dt.timedelta(hours=h), value, flag))
    return pd.DataFrame(rows, columns=READING_COLUMNS)


@normalizer("air_reading")
def run_readings():
    out_dir = CLEAN / "air_reading"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for source, columns in (("aire_dia", ["provincia", "h24"]), ("ay_aire", ["PROVINCIA", "H24"])):
        long = long_readings(read_csv(latest_csv(RAW / source, columns)))
        for day, group in long.groupby(long["ts"].dt.strftime("%Y%m%d")):
            target = out_dir / f"{source}_{day}.parquet"
            if target.exists():   # el mismo dia llega varias veces: V gana a T, lo nuevo a lo viejo
                old = pd.read_parquet(target)
                group = (pd.concat([old, group]).sort_values("flag", key=lambda s: s.eq("V"), kind="stable")
                         .drop_duplicates(["station_id", "magnitude", "ts"], keep="last"))
            tmp = target.with_suffix(".tmp")
            group.sort_values(["station_id", "magnitude", "ts"]).to_parquet(tmp, index=False)
            tmp.replace(target)
            written.append(target)
    return written


@normalizer("air_station")
def run_stations():
    cm = points(read_csv(latest_csv(RAW / "aire_estaciones", ["estacion_codigo"])),
                "estacion_coord_UTM_ETRS89_x", "estacion_coord_UTM_ETRS89_y", 25830)
    cm = cm.assign(id=cm["estacion_codigo"].astype(str).str.zfill(8), network="CM",
                   name=cm["estacion_municipio"], area_type=cm["estacion_tipo_area"])
    ay = points(read_csv(latest_csv(RAW / "ay_aire_estaciones", ["CODIGO"])), "LONGITUD", "LATITUD", 4326)
    ay = ay.assign(id=ay["CODIGO"].astype(str).str.zfill(8), network="AY", name=ay["ESTACION"], area_type=ay["NOM_TIPO"])
    stations = pd.concat([cm, ay], ignore_index=True)
    stations["ine_code"] = stations["id"].str[:5]
    return write(gpd.GeoDataFrame(stations[["id", "network", "name", "ine_code", "area_type", "geometry"]], crs=4326),
                 "air_station")
