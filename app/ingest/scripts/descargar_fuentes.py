#!/usr/bin/env python3
"""Descarga las fuentes de datos abiertos verificadas del proyecto a data/raw/.

Solo usa la biblioteca estándar de Python (3.9+).

Uso:
    python3 scripts/descargar_fuentes.py --listar
    python3 scripts/descargar_fuentes.py                       # grupo "minimo"
    python3 scripts/descargar_fuentes.py --grupo completo
    python3 scripts/descargar_fuentes.py --solo eiel_deporte,nmc_deporte
    python3 scripts/descargar_fuentes.py --grupo completo --incluir-pesadas

Cada fuente se guarda en data/raw/<id>/ y se registra en data/raw/manifest.json
(URL, fecha de descarga y tamaño), para poder citar fuente y fecha (RF-19).
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.parse
import urllib.request
import zipfile

RAIZ = pathlib.Path(__file__).resolve().parent.parent  # app/ingest
DESTINO = RAIZ.parent / "data" / "raw"  # app/data/raw (compartido entre servicios)
UA = {"User-Agent": "Mozilla/5.0 (MAD Open Data Challenge 2026; proyecto Muevete Cerca)"}

CKAN_CM = "https://datos.comunidad.madrid/api/3/action"
CKAN_AY = "https://datos.madrid.es/api/3/action"
WFS = "https://idem.comunidad.madrid/geoidem/wfs?service=WFS&version=2.0.0&request=GetFeature&outputFormat=application/json&typeNames="
NMC = "https://apiscm.comunidad.madrid/t/ciudadanos.comunidad.madrid/sector-publico/nomecalles-descargas/v1/paquetes/"

# id: (tipo, identificador, grupo, pesada, descripción)
# grupo "minimo" = lo imprescindible para el núcleo F1-F5; "completo" = todo lo verificado.
FUENTES = {
    # --- IDEM (WFS, GeoJSON en EPSG:25830) ---
    "eiel_deporte":     ("wfs", "ServiciosPublicos:IDEM_EIEL_INSTAL_DEPORTIVA_23", "minimo", False, "EIEL 2023 instalaciones deportivas (155 municipios, deporte por columna)"),
    "eiel_parques":     ("wfs", "CubiertaTerrestre:IDEM_EIEL_PARQUE_23", "minimo", False, "EIEL 2023 parques"),
    "eiel_nucleos":     ("wfs", "UnidadesAdministrativas:IDEM_EIEL_NUCLEOS_23", "completo", False, "EIEL 2023 núcleos (conectividad)"),
    "eiel_sanitario":   ("wfs", "ServiciosPublicos:IDEM_EIEL_CENT_SANITARIO_23", "completo", False, "EIEL 2023 centros sanitarios"),
    "eiel_ensenanza":   ("wfs", "ServiciosPublicos:IDEM_EIEL_CENT_ENSENANZA_23", "completo", False, "EIEL 2023 centros de enseñanza"),
    "eiel_cultural":    ("wfs", "ServiciosPublicos:IDEM_EIEL_CENT_CULTURAL_23", "completo", False, "EIEL 2023 centros culturales (bibliotecas, hogares del pensionista)"),
    "vpla_redes":       ("wfs", "UsoDelSuelo:VPLA_V_RED_REF_25", "minimo", True, "Planeamiento refundido 2025: zonas verdes y deportivos (166 municipios; ~37.000 polígonos)"),
    "areas_recreativas": ("wfs", "ServiciosPublicos:IDEM_MA_AREAS_RECREA", "minimo", False, "Áreas recreativas (fuentes, bancos, aseos, juegos)"),
    "sendas":           ("wfs", "RedesTransporte:IDEM_V_MA_SENDAS_VERDES", "completo", False, "Sendas por la naturaleza"),
    "vias_pecuarias":   ("wfs", "Zonas:IDEM_MA_VIAS_PECUARIAS", "completo", False, "Vías pecuarias"),
    "municipios":       ("wfs", "Comun:IDEM_V_MUNICIPIOS", "minimo", False, "Límites de los 179 municipios"),
    "estaciones_aire_idem": ("wfs", "InstalacionesMedioAmbiente:IDEM_MA_EST_CALIDAD_AIRE", "minimo", False, "48 estaciones de aire (red regional + Ayuntamiento)"),
    "zonas_aire":       ("wfs", "InstalacionesMedioAmbiente:IDEM_MA_ZONAS_CALIDAD_AIRE", "completo", False, "Zonas de calidad del aire"),
    "viales":           ("wfs", "RedesTransporte:IDEM_GDIE_G_CALLES", "completo", True, "Viales urbanos (~49.000)"),
    "cubierta_terrestre": ("wfs", "BTA:IDEM_BTA_CUBIERTER_POL_17", "completo", True, "Cubierta terrestre BTA 2017 (~137.000 polígonos, muy pesada: mejor filtrar por bbox del piloto)"),
    # --- Nomecalles (shapefile zip, sin clave) ---
    "nmc_deporte":      ("nmc", "deporte", "minimo", False, "Instalaciones deportivas (1.358, 178 municipios, sin deporte por instalación)"),
    "nmc_deporteotros": ("nmc", "deporteotros", "completo", False, "Otras instalaciones deportivas"),
    "nmc_parques":      ("nmc", "parques", "minimo", False, "Parques y jardines (780, 62 municipios)"),
    "nmc_busparadas":   ("nmc", "busparadas", "completo", False, "Paradas de autobús (15.037)"),
    "nmc_estmetro":     ("nmc", "estmetro", "completo", False, "Estaciones de metro"),
    "nmc_estcerca":     ("nmc", "estcerca", "completo", False, "Estaciones de cercanías"),
    "nmc_hipermercados": ("nmc", "hipermercados", "completo", False, "Hipermercados (F6)"),
    "nmc_mercadoabastos": ("nmc", "mercadoabastos", "completo", False, "Mercados de abastos (F6)"),
    "nmc_galimentacion": ("nmc", "galimentacion", "completo", False, "Galerías de alimentación (F6)"),
    "nmc_bibliotecas":  ("nmc", "biblipubli", "completo", False, "Bibliotecas públicas"),
    # --- CKAN Comunidad de Madrid (CSV ;) ---
    "aire_estaciones":  ("ckan_cm", "calidad_aire_estaciones", "minimo", False, "Red regional de aire: 28 estaciones"),
    "aire_dia":         ("ckan_cm", "calidad_aire_datos_dia", "minimo", False, "Aire horario del día en curso (H01..H24, V01..V24)"),
    "aire_zonas":       ("ckan_cm", "calidad_aire_zonas", "minimo", False, "Municipio -> zona de calidad del aire"),
    "aire_historico":   ("ckan_cm", "calidad_aire_datos_historico", "completo", True, "Aire horario desde 2005 (varios ficheros grandes)"),
    "sanitarios":       ("ckan_cm", "centros_servicios_establecimientos_sanitarios", "minimo", False, "Centros sanitarios (una fila por servicio)"),
    "farmacias":        ("ckan_cm", "oficinas_farmacia", "minimo", False, "Farmacias"),
    "educativos":       ("ckan_cm", "centros_educativos", "minimo", False, "Centros educativos (filtrar SITUACIÓN = ALTA)"),
    "desfibriladores":  ("ckan_cm", "desfibriladores_externos_fuera_ambito_sanitario", "minimo", False, "Desfibriladores, toda la región"),
    "padron":           ("ckan_cm", "padron_por_sexo", "minimo", False, "Población por municipio (cp1252)"),
    "densidad":         ("ckan_cm", "1930748", "completo", False, "Densidad por municipio"),
    "renta":            ("ckan_cm", "irpf_indicador_renta", "completo", False, "Renta disponible bruta municipal"),
    "atencion_social":  ("ckan_cm", "atencion_social_registro_centros", "completo", False, "Centros de atención social"),
    "zonas_bano":       ("ckan_cm", "censo_clasificacion_zonas_bano", "completo", False, "Zonas de baño"),
    # --- Ayuntamiento de Madrid (solo capital) ---
    "ay_aire":          ("ckan_ay", "212531-0-calidad-aire-tiempo-real", "minimo", False, "Aire en tiempo real (capital)"),
    "ay_aire_estaciones": ("ckan_ay", "212629-0-estaciones-control-aire", "minimo", False, "Estaciones de aire (capital)"),
    "ay_meteo":         ("ckan_ay", "300392-0-meteorologia-tiempo-real", "completo", False, "Meteorología en tiempo real (capital)"),
    "ay_fuentes":       ("ckan_ay", "300051-0-fuentes", "minimo", False, "Fuentes de agua para beber (capital)"),
    "ay_polideportivos": ("ckan_ay", "200186-0-polideportivos", "minimo", False, "Centros deportivos municipales (capital)"),
    "ay_idb":           ("ckan_ay", "200215-0-instalaciones-deportivas", "completo", False, "Instalaciones deportivas básicas (capital)"),
    "ay_piscinas":      ("ckan_ay", "210227-0-piscinas-publicas", "completo", False, "Piscinas municipales (capital)"),
    "ay_parques":       ("ckan_ay", "200761-0-parques-jardines", "minimo", False, "Parques y jardines (capital)"),
    "ay_bancos":        ("ckan_ay", "300095-0-mobiliario-bancos", "completo", True, "Bancos (capital)"),
    "ay_areas_caninas": ("ckan_ay", "300094-0-areas-caninas", "completo", False, "Áreas caninas (capital)"),
    "ay_trafico":       ("url", "https://informo.madrid.es/informo/tmadrid/pm.xml", "minimo", False, "Tráfico en tiempo real (capital, XML cada 5 min)"),
}


def pedir(url, timeout=300):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def guardar(carpeta, nombre, contenido):
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / nombre
    ruta.write_bytes(contenido)
    return ruta


def nombre_desde_url(url):
    nombre = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name or "recurso"
    return "".join(c for c in nombre if c.isalnum() or c in "._-")


def descomprimir_seguro(zip_path, carpeta):
    """Extrae sin permitir rutas fuera de la carpeta (los zip son datos no confiables)."""
    base = carpeta.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for miembro in z.infolist():
            destino = (carpeta / miembro.filename).resolve()
            if base != destino and base not in destino.parents:
                raise ValueError(f"Ruta sospechosa en el zip: {miembro.filename}")
        z.extractall(carpeta)


def bajar_ckan(base, ident, carpeta, incluir_pesadas):
    meta = json.loads(pedir(f"{base}/package_show?id={urllib.parse.quote(ident)}"))["result"]
    recursos = [r for r in meta["resources"] if (r.get("format") or "").upper() in ("CSV", "XML", "JSON")
                or r["url"].lower().endswith((".csv", ".xml", ".json"))]
    csvs = [r for r in recursos if r["url"].lower().endswith(".csv") or (r.get("format") or "").upper() == "CSV"]
    elegidos = csvs if incluir_pesadas else csvs[:1]
    if not elegidos:
        elegidos = recursos[:1]
    if not elegidos:
        raise RuntimeError("sin recurso descargable (" + ", ".join(sorted({(r.get('format') or '?') for r in meta['resources']})) + ")")
    (carpeta / "metadatos.json").parent.mkdir(parents=True, exist_ok=True)
    (carpeta / "metadatos.json").write_text(json.dumps({
        "titulo": meta.get("title"), "modificado": meta.get("metadata_modified"),
        "licencia": meta.get("license_title"), "recursos": [r["url"] for r in meta["resources"]]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return [guardar(carpeta, nombre_desde_url(r["url"]), pedir(r["url"])) for r in elegidos], [r["url"] for r in elegidos]


def bajar_nomecalles(ref, carpeta):
    datos = json.loads(pedir(NMC + ref))
    url = datos["data"]["url_descarga"]  # enlace firmado, caduca en 1 hora
    zip_path = guardar(carpeta, f"{ref}.zip", pedir(url))
    descomprimir_seguro(zip_path, carpeta)
    return [zip_path], [NMC + ref]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listar", action="store_true", help="muestra las fuentes y sale")
    ap.add_argument("--grupo", choices=["minimo", "completo"], default="minimo")
    ap.add_argument("--solo", help="ids separados por comas (ignora --grupo)")
    ap.add_argument("--incluir-pesadas", action="store_true", help="incluye capas grandes y todos los CSV históricos")
    args = ap.parse_args()

    if args.listar:
        for k, (tipo, ident, grupo, pesada, desc) in FUENTES.items():
            print(f"{k:22} {grupo:8} {'PESADA ' if pesada else '       '}{tipo:8} {desc}")
        return 0

    if args.solo:
        ids = [x.strip() for x in args.solo.split(",") if x.strip()]
        desconocidos = [x for x in ids if x not in FUENTES]
        if desconocidos:
            print("ids desconocidos:", ", ".join(desconocidos), file=sys.stderr)
            return 2
    else:
        ids = [k for k, v in FUENTES.items() if args.grupo == "completo" or v[2] == "minimo"]
        ids = [k for k in ids if args.incluir_pesadas or not FUENTES[k][3]]

    manifest_path = DESTINO / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    fallos = 0
    for k in ids:
        tipo, ident, _, _, desc = FUENTES[k]
        carpeta = DESTINO / k
        print(f"-> {k}: {desc}", flush=True)
        try:
            if tipo == "wfs":
                rutas, urls = [guardar(carpeta, f"{k}.geojson", pedir(WFS + ident, timeout=900))], [WFS + ident]
            elif tipo == "nmc":
                rutas, urls = bajar_nomecalles(ident, carpeta)
            elif tipo == "ckan_cm":
                rutas, urls = bajar_ckan(CKAN_CM, ident, carpeta, args.incluir_pesadas)
            elif tipo == "ckan_ay":
                rutas, urls = bajar_ckan(CKAN_AY, ident, carpeta, args.incluir_pesadas)
            else:
                rutas, urls = [guardar(carpeta, nombre_desde_url(ident), pedir(ident))], [ident]
            manifest[k] = {"tipo": tipo, "identificador": ident, "urls": urls,
                           "descargado": dt.datetime.now().isoformat(timespec="seconds"),
                           "ficheros": [str(r.relative_to(RAIZ.parent)) for r in rutas],
                           "bytes": sum(r.stat().st_size for r in rutas)}
            print(f"   ok ({manifest[k]['bytes'] / 1e6:.1f} MB)")
        except Exception as e:  # una fuente caída no debe parar el resto (RNF-08)
            fallos += 1
            print(f"   ERROR: {e}", file=sys.stderr)
    DESTINO.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nHecho: {len(ids) - fallos} correctas, {fallos} con error. Manifiesto: {manifest_path.relative_to(RAIZ.parent)}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
