#!/usr/bin/env python3
"""Descarga las fuentes de datos abiertos verificadas del proyecto a data/raw/.

Solo usa la biblioteca estandar de Python (3.9+).

Uso:
    python3 scripts/download_sources.py --list
    python3 scripts/download_sources.py                       # grupo "minimal"
    python3 scripts/download_sources.py --group full
    python3 scripts/download_sources.py --only eiel_deporte,nmc_deporte
    python3 scripts/download_sources.py --group full --include-heavy
    python3 scripts/download_sources.py --refresh reference --include-heavy   # mensual
    python3 scripts/download_sources.py --refresh daily                       # de madrugada
    python3 scripts/download_sources.py --refresh hourly                      # cada hora
    python3 scripts/download_sources.py --refresh weekly --include-heavy      # OSM (y despues el grafo)
    python3 scripts/download_sources.py --only osm --force                    # descarga aunque no haya cambiado

Niveles de recarga (CLAUDE.md 6.4): reference, weekly, daily, hourly, on_demand.
Antes de descargar se comprueba si la fuente ha cambiado (metadata_modified de CKAN,
ETag / Last-Modified o sha256 del contenido); si no ha cambiado, se marca "sin cambios".

Cada fuente se guarda en data/raw/<id>/ y se registra en data/raw/manifest.json
(URL, fecha de descarga y de comprobacion, tamano, sha256), para poder citar fuente
y fecha (RF-19). Si una fuente falla, se conserva su entrada anterior con last_failure.
El directorio de datos se puede cambiar con GOMAD_DATA_DIR.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.parse
import urllib.request
import zipfile
import hashlib
import fcntl
import os
import re
import tempfile
import time
import urllib.error
from collections import namedtuple

ROOT = pathlib.Path(__file__).resolve().parent.parent       # app/ingest
APP_DIR = ROOT.parent                                        # app (donde esta .env)
DATA_DIR = pathlib.Path(os.environ.get("GOMAD_DATA_DIR", APP_DIR / "data"))   # volumen compartido
RAW_DIR = DATA_DIR / "raw"

Source = namedtuple("Source", "kind ident group heavy desc refresh")
REFRESH_LEVELS = ("reference", "weekly", "daily", "hourly", "on_demand")
GEOFABRIK_MADRID = "https://download.geofabrik.de/europe/spain/madrid-latest.osm.pbf"

UA = {"User-Agent": "Mozilla/5.0 (MAD Open Data Challenge 2026; proyecto Muevete Cerca)"}

CKAN_CM = "https://datos.comunidad.madrid/api/3/action"
CKAN_AY = "https://datos.madrid.es/api/3/action"
WFS = "https://idem.comunidad.madrid/geoidem/wfs?service=WFS&version=2.0.0&request=GetFeature&outputFormat=application/json&typeNames="
AEMET_URL = "https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/horaria/"
NMC = "https://apiscm.comunidad.madrid/t/ciudadanos.comunidad.madrid/sector-publico/nomecalles-descargas/v1/paquetes/"

# id: (kind, identificador, grupo, pesada, descripcion, refresh)
# grupo "minimal" = lo imprescindible para el nucleo F1-F5; "full" = todo lo verificado.
_SOURCES = {
    # --- IDEM (WFS, GeoJSON en EPSG:25830) ---
    "eiel_deporte":     ("wfs", "ServiciosPublicos:IDEM_EIEL_INSTAL_DEPORTIVA_23", "minimal", False, "EIEL 2023 instalaciones deportivas (155 municipios, deporte por columna)", "reference"),
    "eiel_parques":     ("wfs", "CubiertaTerrestre:IDEM_EIEL_PARQUE_23", "minimal", False, "EIEL 2023 parques", "reference"),
    "eiel_nucleos":     ("wfs", "UnidadesAdministrativas:IDEM_EIEL_NUCLEOS_23", "full", False, "EIEL 2023 núcleos (conectividad)", "reference"),
    "eiel_sanitario":   ("wfs", "ServiciosPublicos:IDEM_EIEL_CENT_SANITARIO_23", "full", False, "EIEL 2023 centros sanitarios", "reference"),
    "eiel_ensenanza":   ("wfs", "ServiciosPublicos:IDEM_EIEL_CENT_ENSENANZA_23", "full", False, "EIEL 2023 centros de enseñanza", "reference"),
    "eiel_cultural":    ("wfs", "ServiciosPublicos:IDEM_EIEL_CENT_CULTURAL_23", "full", False, "EIEL 2023 centros culturales (bibliotecas, hogares del pensionista)", "reference"),
    "vpla_redes":       ("wfs", "UsoDelSuelo:VPLA_V_RED_REF_25", "minimal", True, "Planeamiento refundido 2025: zonas verdes y deportivos (166 municipios; ~37.000 polígonos)", "reference"),
    "areas_recreativas": ("wfs", "ServiciosPublicos:IDEM_MA_AREAS_RECREA", "minimal", False, "Áreas recreativas (fuentes, bancos, aseos, juegos)", "reference"),
    "sendas":           ("wfs", "RedesTransporte:IDEM_V_MA_SENDAS_VERDES", "full", False, "Sendas por la naturaleza", "reference"),
    "vias_pecuarias":   ("wfs", "Zonas:IDEM_MA_VIAS_PECUARIAS", "full", False, "Vías pecuarias", "reference"),
    "municipios":       ("wfs", "Comun:IDEM_V_MUNICIPIOS", "minimal", False, "Límites de los 179 municipios", "reference"),
    "estaciones_aire_idem": ("wfs", "InstalacionesMedioAmbiente:IDEM_MA_EST_CALIDAD_AIRE", "minimal", False, "48 estaciones de aire (red regional + Ayuntamiento)", "reference"),
    "zonas_aire":       ("wfs", "InstalacionesMedioAmbiente:IDEM_MA_ZONAS_CALIDAD_AIRE", "full", False, "Zonas de calidad del aire", "reference"),
    "viales":           ("wfs", "RedesTransporte:IDEM_GDIE_G_CALLES", "full", True, "Viales urbanos (~49.000)", "reference"),
    "cubierta_terrestre": ("wfs", "BTA:IDEM_BTA_CUBIERTER_POL_17", "full", True, "Cubierta terrestre BTA 2017 (~137.000 polígonos, muy pesada: mejor filtrar por bbox del piloto)", "reference"),
    # --- Nomecalles (shapefile zip, sin clave) ---
    "nmc_deporte":      ("nmc", "deporte", "minimal", False, "Instalaciones deportivas (1.358, 178 municipios, sin deporte por instalación)", "daily"),
    "nmc_deporteotros": ("nmc", "deporteotros", "full", False, "Otras instalaciones deportivas", "daily"),
    "nmc_parques":      ("nmc", "parques", "minimal", False, "Parques y jardines (845 filas, 62 municipios)", "daily"),
    "nmc_busparadas":   ("nmc", "busparadas", "full", False, "Paradas de autobús (15.037)", "daily"),
    "nmc_estmetro":     ("nmc", "estmetro", "full", False, "Estaciones de metro", "daily"),
    "nmc_estcerca":     ("nmc", "estcerca", "full", False, "Estaciones de cercanías", "daily"),
    "nmc_hipermercados": ("nmc", "hipermercados", "full", False, "Hipermercados (F6)", "daily"),
    "nmc_mercadoabastos": ("nmc", "mercadoabastos", "full", False, "Mercados de abastos (F6)", "daily"),
    "nmc_galimentacion": ("nmc", "galimentacion", "full", False, "Galerías de alimentación (F6)", "daily"),
    "nmc_bibliotecas":  ("nmc", "biblipubli", "full", False, "Bibliotecas públicas", "daily"),
    # --- CKAN Comunidad de Madrid (CSV ;) ---
    "aire_estaciones":  ("ckan_cm", "calidad_aire_estaciones", "minimal", False, "Red regional de aire: 28 estaciones", "reference"),
    "aire_dia":         ("ckan_cm", "calidad_aire_datos_dia", "minimal", False, "Aire horario del día en curso (H01..H24, V01..V24)", "hourly"),
    "aire_zonas":       ("ckan_cm", "calidad_aire_zonas", "minimal", False, "Municipio -> zona de calidad del aire", "reference"),
    "aire_historico":   ("ckan_cm", "calidad_aire_datos_historico", "full", True, "Aire horario desde 2005 (varios ficheros grandes)", "reference"),
    "sanitarios":       ("ckan_cm", "centros_servicios_establecimientos_sanitarios", "minimal", False, "Centros sanitarios (una fila por servicio)", "daily"),
    "farmacias":        ("ckan_cm", "oficinas_farmacia", "minimal", False, "Farmacias", "daily"),
    "educativos":       ("ckan_cm", "centros_educativos", "minimal", False, "Centros educativos (filtrar SITUACIÓN = ALTA)", "reference"),
    "desfibriladores":  ("ckan_cm", "desfibriladores_externos_fuera_ambito_sanitario", "minimal", False, "Desfibriladores, toda la región", "daily"),
    "padron":           ("ckan_cm", "padron_por_sexo", "minimal", False, "Población por municipio (cp1252)", "reference"),
    "densidad":         ("ckan_cm", "1930748", "full", False, "Densidad por municipio", "reference"),
    "renta":            ("ckan_cm", "irpf_indicador_renta", "full", False, "Renta disponible bruta municipal", "reference"),
    "atencion_social":  ("ckan_cm", "atencion_social_registro_centros", "full", False, "Centros de atención social", "daily"),
    "zonas_bano":       ("ckan_cm", "censo_clasificacion_zonas_bano", "full", False, "Zonas de baño", "reference"),
    # --- Ayuntamiento de Madrid (solo capital) ---
    "ay_aire":          ("ckan_ay", "212531-0-calidad-aire-tiempo-real", "minimal", False, "Aire en tiempo real (capital)", "hourly"),
    "ay_aire_estaciones": ("ckan_ay", "212629-0-estaciones-control-aire", "minimal", False, "Estaciones de aire (capital)", "reference"),
    "ay_meteo":         ("ckan_ay", "300392-0-meteorologia-tiempo-real", "full", False, "Meteorología en tiempo real (capital)", "hourly"),
    "ay_fuentes":       ("ckan_ay", "300051-0-fuentes", "minimal", False, "Fuentes de agua para beber (capital)", "daily"),
    "ay_polideportivos": ("ckan_ay", "200186-0-polideportivos", "minimal", False, "Centros deportivos municipales (capital)", "daily"),
    "ay_idb":           ("ckan_ay", "200215-0-instalaciones-deportivas", "full", False, "Instalaciones deportivas básicas (capital)", "daily"),
    "ay_piscinas":      ("ckan_ay", "210227-0-piscinas-publicas", "full", False, "Piscinas municipales (capital)", "daily"),
    "ay_parques":       ("ckan_ay", "200761-0-parques-jardines", "minimal", False, "Parques y jardines (capital)", "daily"),
    "ay_bancos":        ("ckan_ay", "300095-0-mobiliario-bancos", "full", True, "Bancos (capital)", "daily"),
    "ay_areas_caninas": ("ckan_ay", "300094-0-areas-caninas", "full", False, "Áreas caninas (capital)", "daily"),
    "ay_trafico":       ("url", "https://informo.madrid.es/informo/tmadrid/pm.xml", "minimal", False, "Tráfico en tiempo real (capital, XML cada 5 min)", "on_demand"),
    # --- Nuevas (14/10) ---
    "osm":       ("url", GEOFABRIK_MADRID, "full", True,
                  "Extracto OSM de la Comunidad de Madrid (Geofabrik, ODbL): red peatonal y mobiliario", "weekly"),
    "callejero": ("nmc", "callejero_completo_2025", "full", True,
                  "Callejero completo 2025: 855.909 portales con coordenadas (geocodificación RF-01, D-04)", "reference"),
    "aemet":     ("aemet", "prediccion/especifica/municipio/horaria", "minimal", False,
                  "AEMET: predicción horaria por municipio (clave en .env)", "hourly"),
}
SOURCES = {key: Source(*value) for key, value in _SOURCES.items()}


def fetch(url, timeout=300, headers=None):
    req = urllib.request.Request(url, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_conditional(url, previous, timeout=300):
    """GET con If-None-Match / If-Modified-Since. Devuelve (None, cabeceras) si el servidor responde 304."""
    headers = dict(UA)
    if previous.get("etag"):
        headers["If-None-Match"] = previous["etag"]
    if previous.get("last_modified"):
        headers["If-Modified-Since"] = previous["last_modified"]
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(), {"etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")}
    except urllib.error.HTTPError as e:
        if e.code == 304:
            return None, {}
        raise


def file_hash(paths):
    h = hashlib.sha256()
    for p in sorted(paths):
        with open(p, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
    return h.hexdigest()


# GeoServer no manda ETag ni Last-Modified y cada respuesta cambia aunque los datos no:
# un "timeStamp" de la respuesta y, en capas sin clave primaria, ids "<capa>.fid-<uuid>_<n>" inventados
WFS_VOLATILE = re.compile(rb'"timeStamp":\s*"[^"]*"|"id":\s*"[^"]*\.fid-[^"]*"')


def wfs_hash(content):
    """sha256 del GeoJSON del WFS sin las partes que cambian en cada peticion (si no, siempre parece cambiado)."""
    return hashlib.sha256(WFS_VOLATILE.sub(b"", content)).hexdigest()


def ckan_modified(base, ident):
    meta = json.loads(fetch(f"{base}/package_show?id={urllib.parse.quote(ident)}"))["result"]
    return meta.get("metadata_modified")


def save(folder, name, content):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(content)
    return path


def filename_from_url(url):
    name = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name or "recurso"
    return "".join(c for c in name if c.isalnum() or c in "._-")


def safe_unzip(zip_path, folder):
    """Extrae sin permitir rutas fuera de la carpeta (los zip son datos no confiables)."""
    base = folder.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for member in z.infolist():
            target = (folder / member.filename).resolve()
            if base != target and base not in target.parents:
                raise ValueError(f"Ruta sospechosa en el zip: {member.filename}")
        z.extractall(folder)


def download_ckan(base, ident, folder, include_heavy):
    meta = json.loads(fetch(f"{base}/package_show?id={urllib.parse.quote(ident)}"))["result"]
    resources = [r for r in meta["resources"] if (r.get("format") or "").upper() in ("CSV", "XML", "JSON")
                 or r["url"].lower().endswith((".csv", ".xml", ".json"))]
    csvs = [r for r in resources if r["url"].lower().endswith(".csv") or (r.get("format") or "").upper() == "CSV"]
    chosen = csvs if include_heavy else csvs[:1]
    if not chosen:
        chosen = resources[:1]
    if not chosen:
        raise RuntimeError("sin recurso descargable (" + ", ".join(sorted({(r.get('format') or '?') for r in meta['resources']})) + ")")
    (folder / "metadatos.json").parent.mkdir(parents=True, exist_ok=True)
    (folder / "metadatos.json").write_text(json.dumps({
        "titulo": meta.get("title"), "modificado": meta.get("metadata_modified"),
        "licencia": meta.get("license_title"), "recursos": [r["url"] for r in meta["resources"]]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return ([save(folder, filename_from_url(r["url"]), fetch(r["url"])) for r in chosen],
            [r["url"] for r in chosen], meta.get("metadata_modified"))


def download_nomecalles(ref, folder):
    data = json.loads(fetch(NMC + ref))
    url = data["data"]["url_descarga"]  # enlace firmado, caduca en 1 hora
    zip_path = save(folder, f"{ref}.zip", fetch(url))
    safe_unzip(zip_path, folder)
    return [zip_path], [NMC + ref]


def read_env(path=None):
    """Lee app/.env (CLAVE=valor por linea) sin dependencias. Las variables de entorno reales mandan."""
    path = pathlib.Path(path or (APP_DIR / ".env"))
    values = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    values.update({k: v for k, v in os.environ.items() if k.startswith("AEMET_")})
    return values


def aemet_municipalities(value):
    if value and value != "todos":
        return [c.strip() for c in value.split(",") if c.strip()]
    geo = json.loads((RAW_DIR / "municipios" / "municipios.geojson").read_text(encoding="utf-8"))
    return sorted("28" + str(f["properties"]["CDMUNICIPIO"]).zfill(3) for f in geo["features"])


def download_aemet(folder, municipalities):
    """Prevision horaria de AEMET por municipio. La clave va en la cabecera api_key, nunca en la URL."""
    env = read_env()
    key = env.get("AEMET_API_KEY")
    if not key:
        raise RuntimeError("Falta AEMET_API_KEY en app/.env (ver app/.env.example)")
    pause = float(env.get("AEMET_PAUSE_S", "1.5"))
    codes = aemet_municipalities(municipalities or env.get("AEMET_MUNICIPALITIES", "todos"))
    paths, urls = [], []
    for code in codes:
        first = json.loads(fetch(AEMET_URL + code, timeout=60, headers={"api_key": key}))
        if first.get("estado") != 200:
            raise RuntimeError(f"AEMET {code}: estado {first.get('estado')} {first.get('descripcion', '')}")
        paths.append(save(folder, f"{code}.json", fetch(first["datos"], timeout=60)))
        meta = {k: v for k, v in first.items() if k != "api_key"}
        paths.append(save(folder, f"{code}.meta.json", json.dumps(meta, ensure_ascii=False).encode("utf-8")))
        urls.append(AEMET_URL + code)
        time.sleep(pause)
    return paths, urls


def select(args):
    if args.only:
        return [x.strip() for x in args.only.split(",") if x.strip()]
    if args.refresh:
        keys = [k for k, s in SOURCES.items() if s.refresh == args.refresh]
    else:
        keys = [k for k, s in SOURCES.items() if args.group == "full" or s.group == "minimal"]
    return [k for k in keys if args.include_heavy or not SOURCES[k].heavy]


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


def download_source(key, src, previous, force, aemet_municipalities=None):
    """Descarga una fuente si ha cambiado. Devuelve la entrada nueva del manifiesto."""
    folder = RAW_DIR / key
    # si responde bien (aunque sin cambios), el fallo anterior ya no vale
    unchanged = {**{k: v for k, v in previous.items() if k != "last_failure"},
                 "refresh": src.refresh, "checked": now(), "changed": False}
    extra, digest = {}, None
    # CKAN de referencia/diario: metadata_modified (las horarias cambian el recurso sin tocar el paquete)
    if src.kind in ("ckan_cm", "ckan_ay") and src.refresh in ("reference", "daily") and not force:
        base = CKAN_CM if src.kind == "ckan_cm" else CKAN_AY
        modified = ckan_modified(base, src.ident)
        if modified and modified == previous.get("modified"):
            return unchanged
    if src.kind == "wfs":
        content, extra = fetch_conditional(WFS + src.ident, {} if force else previous, timeout=900)
        if content is None:
            return unchanged
        paths, urls = [save(folder, f"{key}.geojson", content)], [WFS + src.ident]
        digest = wfs_hash(content)
    elif src.kind == "nmc":
        paths, urls = download_nomecalles(src.ident, folder)
    elif src.kind in ("ckan_cm", "ckan_ay"):
        base = CKAN_CM if src.kind == "ckan_cm" else CKAN_AY
        paths, urls, modified = download_ckan(base, src.ident, folder, src.heavy)
        extra = {"modified": modified}
    elif src.kind == "aemet":
        paths, urls = download_aemet(folder, aemet_municipalities)
    else:
        content, extra = fetch_conditional(src.ident, {} if force else previous)
        if content is None:
            return unchanged
        paths, urls = [save(folder, filename_from_url(src.ident), content)], [src.ident]
    digest = digest or file_hash(paths)
    return {"kind": src.kind, "identifier": src.ident, "refresh": src.refresh, "urls": urls,
            "downloaded": now(), "checked": now(),
            "files": [str(p.relative_to(RAW_DIR)) for p in paths],
            "bytes": sum(p.stat().st_size for p in paths), "sha256": digest,
            "changed": force or digest != previous.get("sha256"),
            **{k: v for k, v in extra.items() if v}}


def read_manifest(manifest_path):
    return json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}


def save_entry(manifest_path, key, entry):
    """Escribe una entrada del manifiesto de forma atomica y con cerrojo.

    Relee el manifiesto dentro del cerrojo para no pisar lo que haya escrito otra
    ejecucion solapada (p. ej. los cron diario y horario), y se llama tras cada fuente
    para que una ejecucion interrumpida no pierda lo ya descargado.
    """
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(manifest_path.with_suffix(".lock"), "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        manifest = read_manifest(manifest_path)
        manifest[key] = entry
        fd, tmp = tempfile.mkstemp(dir=RAW_DIR, prefix="manifest.", suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=1)
        os.replace(tmp, manifest_path)


def run(args):
    if args.list:
        for key, s in SOURCES.items():
            print(f"{key:22} {s.group:8} {s.refresh:10} {'PESADA ' if s.heavy else '       '}{s.kind:8} {s.desc}")
        return 0
    keys = select(args)
    unknown = [k for k in keys if k not in SOURCES]
    if unknown:
        print("ids desconocidos:", ", ".join(unknown), file=sys.stderr)
        return 2
    manifest_path = RAW_DIR / "manifest.json"
    failures = 0
    for key in keys:
        src = SOURCES[key]
        print(f"-> {key} [{src.refresh}]: {src.desc}", flush=True)
        previous = read_manifest(manifest_path).get(key, {})
        try:
            entry = download_source(key, src, previous, args.force, args.aemet_municipalities)
            state = "cambiado" if entry["changed"] else "sin cambios"
            print(f"   ok, {state} ({entry.get('bytes', 0) / 1e6:.1f} MB)")
        except Exception as e:  # una fuente caida no debe parar el resto (RNF-08)
            failures += 1
            entry = {**previous, "last_failure": {"date": now(), "error": str(e)[:300]}}
            print(f"   ERROR: {e}", file=sys.stderr)
        save_entry(manifest_path, key, entry)
    print(f"\nHecho: {len(keys) - failures} correctas, {failures} con error. Manifiesto: {manifest_path}")
    return 1 if failures else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true", help="muestra las fuentes y sale")
    ap.add_argument("--group", choices=["minimal", "full"], default="minimal")
    ap.add_argument("--only", help="ids separados por comas (ignora --group y --refresh)")
    ap.add_argument("--refresh", choices=REFRESH_LEVELS, help="solo las fuentes de ese nivel de recarga (CLAUDE.md §6.4)")
    ap.add_argument("--include-heavy", action="store_true", help="incluye capas grandes y todos los CSV históricos")
    ap.add_argument("--force", action="store_true", help="descarga aunque la fuente no haya cambiado")
    ap.add_argument("--aemet-municipalities", help="códigos INE separados por comas o 'todos' (por defecto, AEMET_MUNICIPALITIES de .env)")
    return run(ap.parse_args())


if __name__ == "__main__":
    sys.exit(main())
