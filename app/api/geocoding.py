"""GET /location (RF-01, D-04): municipios, calles y direcciones con numero a partir de texto libre o parcial.

Texto llano (sin tildes ni mayusculas); cada palabra de 3 o mas letras vale como prefijo («geta» -> Getafe).
Orden: municipios que encajan -> viales del callejero local (clean/addresses.parquet, indice en memoria) ->
buscador de Nomecalles (sin clave, cache 1 h en memoria, resuelto con el mismo callejero) solo si el local no
encuentra el vial. Topes en config/location.yaml.
El texto es la ubicacion de la persona: nunca se escribe en los logs."""
import re
import time
import unicodedata

import duckdb
import httpx
import pyarrow.parquet as pq
import shapely

import settings

from repository import DataUnavailable

SEARCH_URL = ("https://apiscm.comunidad.madrid/t/ciudadanos.comunidad.madrid/sector-publico/"
              "nomecalles-buscador/v1/direcciones")
# tipo de via escrito -> tipo llano del callejero (street_type: «Calle», «Avda», «Cmno», «Cñada»...)
TYPE_ALIASES = {"calle": "calle", "c": "calle", "cl": "calle", "avenida": "avda", "avda": "avda", "av": "avda",
                "plaza": "plaza", "pza": "plaza", "pl": "plaza", "paseo": "paseo", "po": "paseo", "camino": "cmno",
                "cmno": "cmno", "carretera": "ctra", "ctra": "ctra", "glorieta": "gta", "gta": "gta",
                "travesia": "trva", "trva": "trva", "ronda": "ronda", "pasaje": "psaje", "psaje": "psaje",
                "urbanizacion": "urb", "urb": "urb", "callejon": "cllon", "cllon": "cllon", "costanilla": "cstan",
                "cstan": "cstan", "bulevar": "bulev", "bulev": "bulev", "cuesta": "custa", "custa": "custa",
                "canada": "cnada", "cnada": "cnada", "vereda": "vreda", "vreda": "vreda", "colonia": "col",
                "col": "col", "lugar": "lugar", "rotonda": "rtda", "rtda": "rtda"}
STREET_TYPES = set(TYPE_ALIASES)
STOP_WORDS = {"de", "del", "la", "las", "el", "los", "y", "en", "n", "no", "num", "numero"}
CACHE_MAX = 1000


def plain(text):
    # misma regla que ingest/normalize/addresses.py: minusculas, sin tildes, solo letras y numeros
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _candidate(label, municipality, ine_code, lon, lat, precision):
    return {"label": label, "municipality": municipality, "ine_code": ine_code,
            "coordinate": {"lat": round(float(lat), 7), "lon": round(float(lon), 7)}, "precision": precision}


class Geocoder:
    def __init__(self, data_dir, client=None, ttl_s=3600, timeout_s=3.0, config=None):
        cfg = config if config is not None else settings.load("location")      # topes: config/location.yaml
        self.max_candidates = int(cfg["max_candidates"])
        self.max_municipalities = int(cfg["max_municipalities"])
        self.min_prefix_len = int(cfg["min_prefix_len"])
        self.addresses = data_dir / "clean" / "addresses.parquet"
        self.municipality_file = data_dir / "clean" / "municipality.parquet"
        self.client, self.ttl_s, self.timeout_s = client, ttl_s, timeout_s
        self._cache = {}
        self._municipalities = None
        self._street_index = None

    # --- municipios -------------------------------------------------------------------------------------------
    def municipalities(self):
        """[(ine_code, nombre, nombre llano, lon, lat)]: centro del contorno y nombre del callejero."""
        if self._municipalities is None:
            if not self.municipality_file.exists():
                raise DataUnavailable("Los datos de municipios todavía no están cargados en el servidor.")
            names = {}
            if self.addresses.exists():
                con = duckdb.connect()
                try:
                    names = dict(con.execute("SELECT DISTINCT ine_code, municipality FROM read_parquet(?)",
                                             [str(self.addresses)]).fetchall())
                finally:
                    con.close()
            t = pq.read_table(self.municipality_file, columns=["ine_code", "name", "geometry"]).to_pydict()
            out = []
            for ine, name, wkb in zip(t["ine_code"], t["name"], t["geometry"]):
                poly = shapely.from_wkb(wkb)
                center = poly.centroid if poly.contains(poly.centroid) else poly.point_on_surface()
                display = names.get(ine) or name.title()
                out.append((ine, display, plain(display), center.x, center.y))
            self._municipalities = out
        return self._municipalities

    def _municipality_in(self, q):
        """Municipio nombrado en el texto (palabras completas); si hay varios, el que acaba mas tarde y mas largo."""
        best = None
        padded = f" {q} "
        for m in self.municipalities():
            names = {m[2]}
            first, _, rest = m[2].partition(" ")
            if first in ("el", "la", "los", "las") and rest:
                names.add(rest)                  # «rozas de madrid» = «Las Rozas de Madrid»
            for n in names:
                i = padded.rfind(f" {n} ")
                if i >= 0 and (best is None or (i + len(n), len(n)) > (best[1] + len(best[2]), len(best[2]))):
                    best = (m, i, n)
        return best

    def _muni_candidate(self, m):
        return _candidate(m[1], m[1], m[0], m[3], m[4], "municipality")

    # --- busqueda ---------------------------------------------------------------------------------------------
    def search(self, text):
        """Candidatos ordenados: municipios que encajan con el texto, despues calles y portales (como mucho
        max_candidates). Con numero de portal o calle + municipio, las calles primero y el municipio al final."""
        # «nº10» -> «no 10»: cifras y letras pegadas se separan para encontrar el numero del portal
        q = re.sub(r"(?<=[a-z])(?=[0-9])|(?<=[0-9])(?=[a-z])", " ", plain(text))
        if not q:
            return []
        found = self._municipality_in(q)
        rest = q
        if found:
            _, i, n = found
            rest = (f" {q} "[:i] + " " + f" {q} "[i + len(n) + 2:]).strip()
        tokens = rest.split()
        typed_type = None
        while tokens and tokens[0] in STREET_TYPES:
            typed_type = typed_type or TYPE_ALIASES[tokens[0]]
            tokens = tokens[1:]
        numbers = [int(t) for t in tokens if t.isdigit()]
        words = [t for t in tokens if not t.isdigit() and t not in STOP_WORDS]
        number = numbers[-1] if numbers else None
        muni = found[0] if found else None
        if muni and words:
            # calle (y portal) dentro del municipio nombrado; el buscador de Nomecalles solo si el local no la encuentra
            out = self._local(words, number, muni, typed_type) or self._remote(text, muni)
        else:
            if muni:
                # solo el municipio («getafe») o su nombre como calle («calle madrid 10»): sus palabras, en la region
                words = [t for t in found[2].split() if t not in STOP_WORDS]
            if not words:
                return []
            munis = [] if number is not None else self._municipalities_matching(words)
            out = [self._muni_candidate(m) for m in munis]
            out += self._local(words, number, None, typed_type) or ([] if munis else self._remote(text, None))
        if muni:
            out.append(self._muni_candidate(muni))      # respaldo: el centro del municipio
        unique = list({(c["label"], c["ine_code"]): c for c in out}.values())
        return unique[:self.max_candidates]

    def _municipalities_matching(self, words):
        """Municipios con todas las palabras como prefijo de las de su nombre: primero el nombre igual al texto,
        despues los que tienen las palabras enteras («san» -> San Martin antes que Santorcaz), despues el que empieza
        por el texto y el mas corto; como mucho max_municipalities."""
        target = " ".join(words)
        hits = []
        for m in self.municipalities():
            padded = f" {m[2]} "
            if all(self._hit(w, padded) for w in words):
                short = " ".join(t for t in m[2].split() if t not in STOP_WORDS)
                whole = all(f" {w} " in padded for w in words)
                hits.append(((short != target, not whole, not short.startswith(target), len(m[2]), m[2]), m))
        return [m for _, m in sorted(hits, key=lambda h: h[0])[:self.max_municipalities]]

    def _rows(self, where, params):
        if not self.addresses.exists():
            return []
        con = duckdb.connect()
        try:
            return con.execute(f"""SELECT ine_code, municipality, street_code, street_type, street, street_norm,
                                          number, lon, lat FROM read_parquet(?) WHERE {where}""",
                               [str(self.addresses), *params]).fetchall()
        finally:
            con.close()

    @staticmethod
    def _resolve_street(rows, number):
        """De las filas de un vial: el portal pedido (precision address) o un punto del vial (precision street)."""
        ine, muni, _, stype, street = rows[0][:5]
        if number is not None:
            exact = [r for r in rows if r[6] == number]
            if exact:
                r = exact[0]
                return _candidate(f"{stype} {street} {number}, {muni}", muni, ine, r[7], r[8], "address")
        vial = [r for r in rows if r[6] is None]
        numbered = sorted((r for r in rows if r[6] is not None), key=lambda r: r[6])
        r = vial[0] if vial else numbered[len(numbered) // 2]
        return _candidate(f"{stype} {street}, {muni}", muni, ine, r[7], r[8], "street")

    def _streets(self):
        """Indice en memoria de los viales del callejero (uno por ine_code + street_code), cargado una vez."""
        if self._street_index is None:
            if not self.addresses.exists():
                return []
            con = duckdb.connect()
            try:
                rows = con.execute("""SELECT ine_code, any_value(municipality), street_code, any_value(street_type),
                                             any_value(street), any_value(street_norm), count(*)
                                      FROM read_parquet(?) GROUP BY ine_code, street_code""",
                                   [str(self.addresses)]).fetchall()
            finally:
                con.close()
            self._street_index = [(ine, muni, code, plain(stype or ""), norm or "", f" {norm} ", f" {plain(muni)} ",
                                   portals) for ine, muni, code, stype, _, norm, portals in rows]
        return self._street_index

    def _hit(self, word, padded):
        # palabra de al menos min_prefix_len letras: prefijo de una palabra; mas corta: palabra entera
        return f" {word}" in padded if len(word) >= self.min_prefix_len else f" {word} " in padded

    def _local(self, words, number, muni, typed_type=None):
        """Viales cuyo nombre (o su municipio) contiene todas las palabras, al menos una en el nombre del vial."""
        found = []
        for st in self._streets():
            ine, municipality, _, stype, norm, street_p, muni_p, portals = st
            if muni and ine != muni[0]:
                continue
            in_street = [w for w in words if self._hit(w, street_p)]
            if not in_street or any(w not in in_street and not self._hit(w, muni_p) for w in words):
                continue
            name = [t for t in norm.split() if t not in STOP_WORDS]
            covered = all(any(t == w or (len(w) >= self.min_prefix_len and t.startswith(w)) for w in in_street)
                          for t in name)
            prefix_only = sum(f" {w} " not in street_p for w in in_street)
            # nombre entero cubierto, menos prefijos, tipo escrito (o «Calle»), nombre corto (sin «de la»),
            # vial con mas portales (las calles principales antes), municipio
            found.append(((not covered, prefix_only, stype != (typed_type or "calle"), len(" ".join(name)), -portals,
                           municipality), st))
        best = [st for _, st in sorted(found, key=lambda f: f[0])[:self.max_candidates]]
        if not best:
            return []
        codes = sorted({st[2] for st in best})
        by_street = {}
        for r in self._rows(f"street_code IN ({', '.join('?' for _ in codes)})", codes):
            by_street.setdefault((r[0], r[2]), []).append(r)
        return [self._resolve_street(by_street[(st[0], st[2])], number) for st in best if (st[0], st[2]) in by_street]

    def _remote(self, text, muni):
        if self.client is None:
            return []
        key = plain(text)
        hit = self._cache.get(key)
        if hit and time.monotonic() - hit[0] < self.ttl_s:
            items = hit[1]
        else:
            try:
                r = self.client.get(SEARCH_URL, params={"busqueda": key}, timeout=self.timeout_s)
                r.raise_for_status()
                items = r.json()["data"]["direcciones"]
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                return []
            if len(self._cache) >= CACHE_MAX:
                self._cache.clear()
            self._cache[key] = (time.monotonic(), items)
        wanted = []
        for item in items:
            ine = "28" + str(item.get("municipio", "")).zfill(3)
            if item.get("tipo") not in ("app", "calle") or (muni and ine != muni[0]) or not item.get("cdVial"):
                continue
            m = re.search(r"(\d+)\s*$", item.get("direccion", ""))
            wanted.append((ine, item["cdVial"], int(m.group(1)) if item["tipo"] == "app" and m else None))
        if not wanted:
            return []
        codes = sorted({w[1] for w in wanted})
        rows = self._rows(f"street_code IN ({', '.join('?' for _ in codes)})", codes)
        by_street = {}
        for r in rows:
            by_street.setdefault((r[0], r[2]), []).append(r)
        out = []
        for ine, code, number in wanted:
            street = by_street.get((ine, code))
            if street:
                out.append(self._resolve_street(street, number))
        return out[:self.max_candidates]
