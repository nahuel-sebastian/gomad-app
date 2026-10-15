"""Prevision horaria de AEMET por municipio (CLAUDE.md §7.1) -> clean/forecast/<ine>.parquet."""
import datetime as dt
import json

import pandas as pd

from common import CLEAN, RAW, to_float
from normalize import normalizer

FORECAST_COLUMNS = ["ine_code", "ts", "temp", "feels_like", "precip_prob", "precip", "wind", "sky", "issued"]


def _hourly(items, day):
    """[{value, periodo:'07'}] -> {datetime: valor}. Ignora periodos que no sean una hora."""
    out = {}
    for e in items or []:
        p = str(e.get("periodo", ""))
        if len(p) == 2 and p.isdigit():
            v = e.get("value")
            out[day + dt.timedelta(hours=int(p))] = 0.0 if str(v).lower() == "ip" else to_float(v)
    return out


def _by_band(items, day):
    """probPrecipitacion: [{value, periodo:'0208'}] -> valor para cada hora de la franja."""
    out = {}
    for e in items or []:
        p = str(e.get("periodo", ""))
        if len(p) == 4 and p.isdigit():
            start, end = int(p[:2]), int(p[2:]) or 24
            end = end if end > start else end + 24
            for h in range(start, end):
                out[day + dt.timedelta(hours=h)] = to_float(e.get("value"))
    return out


def municipality_forecast(doc, ine):
    rows = {}
    for d in doc["prediccion"]["dia"]:
        day = dt.datetime.fromisoformat(d["fecha"][:10])
        series = {"temp": _hourly(d.get("temperatura"), day),
                  "feels_like": _hourly(d.get("sensTermica"), day),
                  "precip": _hourly(d.get("precipitacion"), day),
                  "precip_prob": _by_band(d.get("probPrecipitacion"), day),
                  "sky": {day + dt.timedelta(hours=int(e["periodo"])): e.get("descripcion")
                          for e in d.get("estadoCielo", [])
                          if str(e.get("periodo", "")).isdigit() and len(str(e["periodo"])) == 2}}
        for column, values in series.items():
            for ts, v in values.items():
                rows.setdefault(ts, {})[column] = v
    df = pd.DataFrame([{"ts": ts, **v} for ts, v in sorted(rows.items())])
    df = df[df["temp"].notna()].copy()
    df["ine_code"], df["issued"] = ine, doc.get("elaborado")
    for c in ("feels_like", "precip_prob", "precip", "wind", "sky"):
        if c not in df:
            df[c] = None
    return df[FORECAST_COLUMNS]


def _decode(raw):
    # AEMET sirve ISO-8859-15 y raw/aemet guarda los bytes tal cual; las muestras de pruebas estan en UTF-8
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("iso-8859-15")


@normalizer("forecast")
def run():
    out_dir = CLEAN / "forecast"
    out_dir.mkdir(parents=True, exist_ok=True)
    written, failed = [], []
    for path in sorted((RAW / "aemet").glob("28???.json")):
        try:   # un fichero roto (429, JSON a medias) no para al resto; se mantiene su parquet anterior
            doc = json.loads(_decode(path.read_bytes()))
            doc = doc[0] if isinstance(doc, list) else doc
            forecast = municipality_forecast(doc, path.stem)
        except Exception as e:
            failed.append(f"{path.stem} ({type(e).__name__}: {e})")
            continue
        target = out_dir / f"{path.stem}.parquet"
        tmp = target.with_suffix(".tmp")
        forecast.to_parquet(tmp, index=False)
        tmp.replace(target)
        written.append(target)
    if failed:
        raise RuntimeError(f"Previsión sin procesar ({len(written)} correctas): {', '.join(failed)}")
    return written
