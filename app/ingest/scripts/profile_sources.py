#!/usr/bin/env python3
"""Perfila los datos descargados en data/raw/ (solo stdlib).

Para cada fichero: formato, codificación, separador, filas, columnas con % de vacíos,
valores frecuentes en columnas de pocos valores, rango de coordenadas y cobertura de
municipios (códigos INE distintos frente a los 179 de la Comunidad).

Uso:
    python3 scripts/profile_sources.py                 # todo data/raw/
    python3 scripts/profile_sources.py --solo eiel_deporte nmc_deporte
Salida: data/perfil/perfil.json (detalle completo) y resumen por pantalla.
"""
import argparse
import csv
import io
import json
import re
import struct
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RAW = RAIZ.parent / "data" / "raw"  # app/data (compartido entre servicios)
SALIDA = RAIZ.parent / "data" / "perfil"

# Columnas que pueden llevar el código de municipio (INE 5 dígitos o los 3 últimos)
COLS_MUNI = re.compile(
    r"^(mun|cmun|cd_municipio|cod_ine|codigo_ine|municipio_codigo|cod_municipio|"
    r"codigo_municipio|municipio_codigo_ine|ine|codine|cd_muni|id_municipio|codigo)$",
    re.I,
)
COLS_X = re.compile(r"((^|_)(utm_?)?x$|coordenada_?x$|coord_?x$|^x_?etrs89$)", re.I)
COLS_Y = re.compile(r"((^|_)(utm_?)?y$|coordenada_?y$|coord_?y$|^y_?etrs89$)", re.I)
COLS_LAT = re.compile(r"(^|_)lat(itud|itude)?$", re.I)
COLS_LON = re.compile(r"(^|_)(lon|lng|long|longitud|longitude)$", re.I)

# Caja aproximada de la Comunidad de Madrid
BBOX_4326 = (-4.6, 39.85, -3.0, 41.2)  # lon_min, lat_min, lon_max, lat_max
BBOX_25830 = (360000, 4410000, 500000, 4560000)

MAX_VALORES = 12  # valores frecuentes que se guardan por columna
MAX_DISTINTOS = 40  # por encima, la columna se considera «libre» y no se listan valores


def detectar_codificacion(datos: bytes) -> str:
    if datos.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    try:
        datos.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        return "cp1252"


def a_float(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(" ", "")
    if not s:
        return None
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def normalizar_ine(v):
    """Devuelve código INE de 5 dígitos '28xxx' o None."""
    if v is None:
        return None
    s = str(v).strip()
    if s.endswith(".0"):
        s = s[:-2]
    if not s.isdigit():
        return None
    if len(s) == 5 and s.startswith("28"):
        return s
    if 1 <= len(s) <= 3:
        return "28" + s.zfill(3)
    if len(s) == 6 and s.startswith("28"):  # algunos llevan dígito de control
        return s[:5]
    return None


COLS_MUNI_AMPLIA = re.compile(r"mun|^cmun$|^codigo$|territorio|^ine$|cod_?ine", re.I)
REF = {}  # cod_ine -> nombre, se rellena en main()
REF_NOMBRES = {}  # clave normalizada -> cod_ine


def clave_nombre(v: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode().lower().strip()
    m = re.fullmatch(r"(.+?)\s*\((la|el|los|las)\)", s) or re.fullmatch(r"(.+?),\s*(la|el|los|las)", s)
    if m:
        s = f"{m.group(2)} {m.group(1)}"
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


class Perfil:
    def __init__(self):
        self.filas = 0
        self.columnas = {}  # nombre -> {"vacios": n, "valores": Counter, "distintos": set|None}
        self.orden = []

    def fila(self, registro: dict):
        self.filas += 1
        for k, v in registro.items():
            c = self.columnas.get(k)
            if c is None:
                c = {"vacios": self.filas - 1, "valores": Counter(), "libre": False}
                self.columnas[k] = c
                self.orden.append(k)
            if v is None or (isinstance(v, str) and v.strip() == ""):
                c["vacios"] += 1
                continue
            if isinstance(v, (dict, list)):
                v = json.dumps(v, ensure_ascii=False)[:60]
            if not c["libre"]:
                c["valores"][str(v)[:80]] += 1
                if len(c["valores"]) > 5000:
                    c["libre"] = True
        # columnas que no aparecen en esta fila cuentan como vacías
        for k in self.orden:
            if k not in registro:
                self.columnas[k]["vacios"] += 1

    def resumen(self):
        cols = []
        for k in self.orden:
            c = self.columnas[k]
            distintos = None if c["libre"] else len(c["valores"])
            info = {
                "columna": k,
                "pct_vacio": round(100 * c["vacios"] / self.filas, 1) if self.filas else None,
                "distintos": distintos if distintos is not None else ">5000",
            }
            if distintos is not None and distintos <= MAX_DISTINTOS:
                info["valores"] = c["valores"].most_common(MAX_VALORES)
            elif distintos is not None:
                info["ejemplos"] = [v for v, _ in c["valores"].most_common(3)]
            cols.append(info)
        return cols


def analizar_registros(registros, coords_geom=None):
    """registros: iterable de dicts. coords_geom: lista de (x, y) de la geometría si hay."""
    p = Perfil()
    lista = []
    for r in registros:
        p.fila(r)
        lista.append(r)
    res = {"filas": p.filas, "columnas": p.resumen()}

    nombres = p.orden
    # Municipios: se prueba cada columna candidata por código INE y por nombre,
    # y se queda la que más municipios de referencia reconoce.
    if REF:
        mejor = None
        for c in nombres:
            if not COLS_MUNI_AMPLIA.search(c):
                continue
            valores = [r.get(c) for r in lista if r.get(c) not in (None, "")]
            if not valores:
                continue
            cods = [normalizar_ine(v) for v in valores]
            validos = [x for x in cods if x in REF]
            via = "código"
            if len(validos) < 0.8 * len(valores):
                validos = [REF_NOMBRES.get(clave_nombre(v)) for v in valores if isinstance(v, str)]
                validos = [x for x in validos if x]
                via = "nombre"
                if len(validos) < 0.5 * len(valores):
                    continue
            conjunto = set(validos)
            if mejor is None or len(conjunto) > len(mejor[1]):
                mejor = (c, conjunto, via, len(valores) - len(validos))
        if mejor:
            res["municipios"] = {"columna": mejor[0], "via": mejor[2], "codigos": sorted(mejor[1]),
                                 "filas_sin_municipio_reconocido": mejor[3]}

    # Coordenadas en columnas
    def rango(cx, cy):
        pts = [(a_float(r.get(cx)), a_float(r.get(cy))) for r in lista]
        pts = [(x, y) for x, y in pts if x is not None and y is not None]
        if not pts:
            return None
        coma = sum(1 for r in lista if "," in str(r.get(cx) or ""))
        return pts, coma

    for regx, regy, crs in ((COLS_LON, COLS_LAT, "4326"), (COLS_X, COLS_Y, "25830?")):
        cx = next((c for c in nombres if regx.search(c)), None)
        cy = next((c for c in nombres if regy.search(c)), None)
        if cx and cy:
            r = rango(cx, cy)
            if r:
                pts, coma = r
                res.setdefault("coordenadas", []).append(evaluar_puntos(pts, f"{cx}/{cy}", crs, coma))
    if coords_geom:
        res.setdefault("coordenadas", []).append(evaluar_puntos(coords_geom, "geometría", None, 0))
    return res


def evaluar_puntos(pts, origen, crs, coma):
    xs = [x for x, _ in pts]
    ys = [y for _, y in pts]
    if crs is None or crs.endswith("?"):
        crs = "4326" if max(abs(v) for v in xs) <= 180 and max(abs(v) for v in ys) <= 90 else "25830"
    bb = BBOX_4326 if crs == "4326" else BBOX_25830
    fuera = sum(1 for x, y in pts if not (bb[0] <= x <= bb[2] and bb[1] <= y <= bb[3]))
    ceros = sum(1 for x, y in pts if x == 0 or y == 0)
    return {
        "origen": origen,
        "crs_deducido": "EPSG:" + crs,
        "puntos": len(pts),
        "x": [round(min(xs), 5), round(max(xs), 5)],
        "y": [round(min(ys), 5), round(max(ys), 5)],
        "fuera_de_madrid": fuera,
        "ceros": ceros,
        "con_coma_decimal": coma,
    }


# ---------- lectores ----------

def leer_csv(ruta: Path):
    datos = ruta.read_bytes()
    cod = detectar_codificacion(datos)
    texto = datos.decode(cod, errors="replace")
    muestra = texto[:20000]
    primera = muestra.splitlines()[0] if muestra else ""
    sep = max([";", ",", "\t", "|"], key=lambda s: primera.count(s))
    lector = csv.DictReader(io.StringIO(texto), delimiter=sep)
    res = analizar_registros(lector)
    res.update({"formato": "csv", "codificacion": cod, "separador": sep})
    return res


def recorrer_coords(g, salida, limite=1):
    """Toma un punto representativo por geometría (el primero)."""
    if not g:
        return
    c = g.get("coordinates")
    if g.get("type") == "GeometryCollection":
        for h in g.get("geometries", []):
            recorrer_coords(h, salida)
            return
    while isinstance(c, list) and c and isinstance(c[0], list):
        c = c[0]
    if isinstance(c, list) and len(c) >= 2 and all(isinstance(v, (int, float)) for v in c[:2]):
        salida.append((float(c[0]), float(c[1])))


def leer_geojson(ruta: Path):
    with ruta.open(encoding="utf-8") as f:
        d = json.load(f)
    feats = d.get("features", [])
    tipos = Counter((ft.get("geometry") or {}).get("type") for ft in feats)
    pts = []
    for ft in feats:
        recorrer_coords(ft.get("geometry"), pts)
    res = analizar_registros((ft.get("properties") or {} for ft in feats), pts)
    crs = (d.get("crs") or {}).get("properties", {}).get("name")
    res.update({
        "formato": "geojson",
        "crs_declarado": crs,
        "geometrias": dict(tipos),
        "total_declarado": d.get("totalFeatures") or d.get("numberMatched"),
    })
    if res["total_declarado"] not in (None, "unknown") and int(res["total_declarado"]) != len(feats):
        res["aviso_truncado"] = f"El servicio declara {res['total_declarado']} y hay {len(feats)}"
    return res


def leer_dbf(ruta: Path):
    datos = ruta.read_bytes()
    n, cab, lreg = struct.unpack("<IHH", datos[4:12])
    campos = []
    pos = 32
    while datos[pos] != 0x0D:
        nombre = datos[pos:pos + 11].split(b"\x00")[0].decode("ascii", "replace")
        tipo = chr(datos[pos + 11])
        largo = datos[pos + 16]
        campos.append((nombre, tipo, largo))
        pos += 32
    cpg = ruta.with_suffix(".cpg")
    cod = cpg.read_text().strip() if cpg.exists() else "utf-8"
    cod = {"UTF-8": "utf-8", "UTF8": "utf-8"}.get(cod.upper(), cod)

    def registros():
        p = cab
        for _ in range(n):
            reg = datos[p:p + lreg]
            p += lreg
            if not reg or reg[0:1] == b"*":
                continue
            off = 1
            fila = {}
            for nombre, tipo, largo in campos:
                v = reg[off:off + largo].decode(cod, errors="replace").strip()
                off += largo
                fila[nombre] = v
            yield fila

    res = analizar_registros(registros())
    prj = ruta.with_suffix(".prj")
    res.update({
        "formato": "shapefile (dbf)",
        "codificacion": cod,
        "prj": prj.read_text(errors="replace")[:60] if prj.exists() else "SIN .prj",
    })
    return res


def leer_trafico(ruta: Path):
    raiz = ET.parse(ruta).getroot()
    pms = raiz.findall(".//pm")

    def registros():
        for pm in pms:
            yield {h.tag: (h.text or "") for h in pm}

    res = analizar_registros(registros())
    res.update({"formato": "xml", "fecha_hora": (raiz.findtext("fecha_hora") or "")})
    return res


def perfilar_fuente(dir_fuente: Path):
    out = {}
    for f in sorted(dir_fuente.iterdir()):
        try:
            if f.name == "metadatos.json":
                m = json.loads(f.read_text(encoding="utf-8"))
                out[f.name] = {"formato": "metadatos", "contenido": m}
            elif f.suffix == ".csv":
                out[f.name] = leer_csv(f)
            elif f.suffix == ".geojson":
                out[f.name] = leer_geojson(f)
            elif f.suffix == ".dbf":
                out[f.name] = leer_dbf(f)
            elif f.suffix == ".xml" and f.name == "pm.xml":
                out[f.name] = leer_trafico(f)
            elif f.name.endswith("_fuentesynotas.txt"):
                out[f.name] = {"formato": "notas", "texto": f.read_text(errors="replace")[:1500]}
        except Exception as e:  # un fichero roto no debe parar el perfil
            out[f.name] = {"error": f"{type(e).__name__}: {e}"}
    return out


def municipios_referencia():
    ruta = RAW / "municipios" / "municipios.geojson"
    d = json.loads(ruta.read_text(encoding="utf-8"))
    ref = {}
    for ft in d["features"]:
        pr = ft["properties"]
        ref["28" + str(pr["CDMUNICIPIO"]).zfill(3)] = pr.get("DSMUNICIPIO_ORI") or pr.get("DSMUNICIPIO")
    return ref


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--solo", nargs="*", help="ids de fuente (carpetas de data/raw/)")
    args = ap.parse_args()

    fuentes = sorted(p for p in RAW.iterdir() if p.is_dir())
    if args.solo:
        fuentes = [p for p in fuentes if p.name in args.solo]
    ref = municipios_referencia()
    REF.update(ref)
    for cod, nom in ref.items():
        REF_NOMBRES[clave_nombre(nom)] = cod
        sin_art = re.sub(r"^(la|el|los|las) ", "", clave_nombre(nom))
        REF_NOMBRES.setdefault(sin_art, cod)
    perfil = {"municipios_referencia": len(ref), "fuentes": {}}
    for d in fuentes:
        print(f"· {d.name}", file=sys.stderr)
        perfil["fuentes"][d.name] = perfilar_fuente(d)

    # cobertura frente a los 179
    for nombre, ficheros in perfil["fuentes"].items():
        for fic, r in ficheros.items():
            m = r.get("municipios") if isinstance(r, dict) else None
            if m:
                cods = set(m["codigos"])
                m["n"] = len(cods & set(ref))
                m["no_reconocidos"] = sorted(cods - set(ref))[:10]
                m["faltan"] = sorted(set(ref) - cods)
                faltan_nombres = [ref[c] for c in m["faltan"]]
                m["faltan_nombres"] = faltan_nombres[:40]
                del m["codigos"]

    SALIDA.mkdir(parents=True, exist_ok=True)
    (SALIDA / "perfil.json").write_text(json.dumps(perfil, ensure_ascii=False, indent=1), encoding="utf-8")
    (SALIDA / "municipios_referencia.json").write_text(json.dumps(ref, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nMunicipios de referencia: {len(ref)}")
    for nombre, ficheros in perfil["fuentes"].items():
        for fic, r in ficheros.items():
            if r.get("formato") in ("metadatos", "notas"):
                continue
            if "error" in r:
                print(f"{nombre}/{fic}: ERROR {r['error']}")
                continue
            m = r.get("municipios")
            cob = f"muni {m['n']}/{len(ref)} ({m['columna']})" if m else "muni —"
            co = r.get("coordenadas") or []
            cs = "; ".join(f"{c['crs_deducido']} fuera:{c['fuera_de_madrid']}" for c in co) or "sin coords"
            extra = f" cod:{r.get('codificacion')} sep:{r.get('separador')}" if r.get("formato") == "csv" else ""
            print(f"{nombre}/{fic}: {r['filas']} filas, {len(r['columnas'])} cols, {cob}, {cs}{extra}")
    print(f"\nDetalle: {SALIDA / 'perfil.json'}")


if __name__ == "__main__":
    main()
