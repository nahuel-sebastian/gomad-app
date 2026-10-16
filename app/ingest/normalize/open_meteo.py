"""Prevision horaria de Open-Meteo de los 179 municipios (DEC-16) -> clean/forecast/<ine>.parquet.

raw/open_meteo/forecast.json es la respuesta de UNA peticion (lista, un elemento por punto) y raw/open_meteo/points.csv
los puntos en el mismo orden. Open-Meteo no publica hora de elaboracion: issued = fecha de descarga del manifiesto.
"""
import csv
import datetime as dt
import json

import pandas as pd
import yaml

from common import CLEAN, CONFIG_DIR, RAW
from normalize import normalizer

# temp_max_day (al final): Tmax diaria de Open-Meteo del dia de ts, para el «dia de calor» (DEC-06)
FORECAST_COLUMNS = ["ine_code", "ts", "temp", "feels_like", "precip_prob", "precip", "wind", "sky", "issued",
                    "temp_max_day"]


def _sky_texts():
    cfg = yaml.safe_load((CONFIG_DIR / "weather_codes.yaml").read_text(encoding="utf-8"))
    return {int(k): v for k, v in cfg["codes"].items()}


def municipality_forecast(item, ine, issued, sky=None):
    sky = _sky_texts() if sky is None else sky
    h = item["hourly"]
    df = pd.DataFrame({"ts": pd.to_datetime(h["time"]), "temp": h["temperature_2m"],
                       "feels_like": h["apparent_temperature"], "precip_prob": h["precipitation_probability"],
                       "precip": h["precipitation"], "wind": h["wind_speed_10m"],
                       "sky": [sky.get(int(c)) if c is not None else None for c in h["weather_code"]]})
    for c in ("temp", "feels_like", "precip_prob", "precip", "wind"):
        df[c] = df[c].astype("float64")
    daily = item.get("daily") or {}
    tmax = {dt.date.fromisoformat(d): v for d, v in zip(daily.get("time", []), daily.get("temperature_2m_max", []))}
    df["temp_max_day"] = [tmax.get(ts.date()) for ts in df["ts"]]
    df["temp_max_day"] = df["temp_max_day"].astype("float64")
    df = df[df["temp"].notna()].sort_values("ts").reset_index(drop=True)
    df["ine_code"], df["issued"] = ine, issued
    return df[FORECAST_COLUMNS]


@normalizer("forecast")
def run():
    folder = RAW / "open_meteo"
    doc = json.loads((folder / "forecast.json").read_text(encoding="utf-8"))
    items = doc if isinstance(doc, list) else [doc]
    with (folder / "points.csv").open(encoding="utf-8") as f:
        codes = [r["ine_code"] for r in csv.DictReader(f)]
    if len(items) != len(codes):        # nada a medias: se conservan los parquet anteriores
        raise RuntimeError(f"Previsión sin procesar: Open-Meteo trae {len(items)} puntos de {len(codes)}")
    manifest = json.loads((RAW / "manifest.json").read_text(encoding="utf-8")) if (RAW / "manifest.json").exists() else {}
    issued = (manifest.get("open_meteo") or {}).get("downloaded")
    out_dir = CLEAN / "forecast"
    out_dir.mkdir(parents=True, exist_ok=True)
    sky, written = _sky_texts(), []
    for ine, item in zip(codes, items):
        target = out_dir / f"{ine}.parquet"
        tmp = target.with_suffix(".tmp")
        municipality_forecast(item, ine, issued, sky).to_parquet(tmp, index=False)
        tmp.replace(target)
        written.append(target)
    return written
