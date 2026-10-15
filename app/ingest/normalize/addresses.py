"""Callejero completo 2025 (IDEM) -> clean/addresses.parquet para /location (D-04).

CSV separado por comas, cp1252, coordenadas EPSG:25830. Una fila por portal (cdtipo A), punto kilometrico (K)
o vial sin numero (V). Se quedan los portales con numero (A + tiponumero N) y los viales (V) para la precision «calle».
"""
import re
import unicodedata

import pandas as pd

from common import RAW, ine_code, to_wgs84, write
from normalize import normalizer

SOURCE = RAW / "callejero" / "gdie_callejero_completo.csv"
COLUMNS = ["cdtipo", "cdmuni", "dsmuni", "cdtvia", "cdvial", "dspart", "dsvial", "tiponumero", "numero", "calif",
           "coord_x", "coord_y"]


def plain(text):
    # misma regla que api/geocoding.py: minusculas, sin tildes, solo letras y numeros
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def build(path):
    df = pd.read_csv(path, sep=",", dtype=str, encoding="cp1252", usecols=COLUMNS, keep_default_na=False)
    numbered = (df["cdtipo"] == "A") & (df["tiponumero"] == "N") & df["numero"].str.strip().str.isdigit()
    df = df[numbered | (df["cdtipo"] == "V")].copy()
    x = pd.to_numeric(df["coord_x"].str.replace(",", "."), errors="coerce")
    y = pd.to_numeric(df["coord_y"].str.replace(",", "."), errors="coerce")
    ok = x.notna() & y.notna()
    df, x, y = df[ok], x[ok], y[ok]
    lon, lat = to_wgs84(x.to_numpy(), y.to_numpy())
    street = (df["dspart"].str.strip() + " " + df["dsvial"].str.strip()).str.strip()
    number = [int(n) if t == "A" else None for n, t in zip(df["numero"], df["cdtipo"])]
    out = pd.DataFrame({
        "ine_code": df["cdmuni"].map(ine_code).to_numpy(),
        "municipality": df["dsmuni"].str.strip().to_numpy(),
        "street_code": df["cdvial"].str.strip().to_numpy(),
        "street_type": df["cdtvia"].str.strip().to_numpy(),
        "street": street.to_numpy(),
        "street_norm": street.map(plain).to_numpy(),
        "number": pd.array(number, dtype="Int64"),
        "letter": df["calif"].str.strip().to_numpy(),
        "lon": lon, "lat": lat})
    return out[out["ine_code"].notna()].reset_index(drop=True)


@normalizer("addresses")
def run():
    return write(build(SOURCE), "addresses")
