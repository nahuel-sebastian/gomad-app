#!/usr/bin/env python3
"""Comprueba la API de AEMET con la clave de app/.env y resume el esquema real.

Uso: python3 scripts/verify_aemet.py 28065 28079
Guarda las respuestas en app/data/raw/aemet_verificacion/ (no se versiona) e imprime las claves
de cada dia, los periodos de cada campo, las cabeceras de cuota y la codificacion.
"""
import importlib.util
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent      # app/ingest
spec = importlib.util.spec_from_file_location("dl", ROOT / "scripts" / "download_sources.py")
dl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dl)


def fetch_with_headers(url, headers):
    req = urllib.request.Request(url, headers={**dl.UA, **headers})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read(), dict(r.headers)


def main(codes):
    key = dl.read_env().get("AEMET_API_KEY")
    if not key:
        sys.exit("Falta AEMET_API_KEY en app/.env")
    out_dir = dl.RAW_DIR / "aemet_verificacion"
    out_dir.mkdir(parents=True, exist_ok=True)
    for code in codes:
        body, headers = fetch_with_headers(dl.AEMET_URL + code, {"api_key": key})
        first = json.loads(body)
        print(f"\n== {code}: estado {first.get('estado')} · {first.get('descripcion')}")
        print("   cabeceras de cuota:", {k: v for k, v in headers.items() if "request" in k.lower() or "limit" in k.lower()})
        data, headers2 = fetch_with_headers(first["datos"], {})
        print("   Content-Type de datos:", headers2.get("Content-Type"))
        try:
            text = data.decode("utf-8")
            print("   codificación: utf-8")
        except UnicodeDecodeError:
            text = data.decode("latin-1")
            print("   codificación: NO es utf-8 (leído como latin-1)")
        (out_dir / f"{code}.json").write_text(text, encoding="utf-8")
        doc = json.loads(text)
        doc = doc[0] if isinstance(doc, list) else doc
        print("   claves raíz:", sorted(doc))
        print("   elaborado:", doc.get("elaborado"))
        days = doc["prediccion"]["dia"]
        print("   días:", [d.get("fecha") for d in days])
        for field, value in days[0].items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                print(f"   {field}: {len(value)} elementos; claves {sorted(value[0])}; ejemplo {value[0]}")
            else:
                print(f"   {field}: {value!r}"[:160])


if __name__ == "__main__":
    main(sys.argv[1:] or ["28065", "28079"])
