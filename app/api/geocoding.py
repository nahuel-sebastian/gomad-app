"""GET /location (RF-01, D-04): direccion con numero o municipio por nombre.

Orden: municipio por nombre -> callejero normalizado local (clean/addresses.parquet) -> buscador de Nomecalles
(sin clave, cache 1 h en memoria, resuelto con el mismo callejero) solo si el local no encuentra el vial.
El texto es la ubicacion de la persona: nunca se escribe en los logs."""
import re
import time
import unicodedata

import duckdb
import httpx
import pyarrow.parquet as pq
import shapely

from repository import DataUnavailable

SEARCH_URL = ("https://apiscm.comunidad.madrid/t/ciudadanos.comunidad.madrid/sector-publico/"
              "nomecalles-buscador/v1/direcciones")
STREET_TYPES = {"calle", "c", "cl", "avenida", "avda", "av", "plaza", "pza", "pl", "paseo", "po", "camino", "cmno",
                "carretera", "ctra", "glorieta", "gta", "travesia", "trva", "ronda", "pasaje", "psaje", "urbanizacion",
                "urb", "callejon", "cllon", "costanilla", "cstan", "bulevar", "bulev", "cuesta", "custa", "canada",
                "cnada", "vereda", "vreda", "colonia", "col", "lugar", "rotonda", "rtda"}
STOP_WORDS = {"de", "del", "la", "las", "el", "los", "y", "en", "n", "no", "num", "numero"}
MAX_CANDIDATES = 6
CACHE_MAX = 1000


def plain(text):
    # misma regla que ingest/normalize/addresses.py: minusculas, sin tildes, solo letras y numeros
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def _candidate(label, municipality, ine_code, lon, lat, precision):
    return {"label": label, "municipality": municipality, "ine_code": ine_code,
            "coordinate": {"lat": round(float(lat), 7), "lon": round(float(lon), 7)}, "precision": precision}


class Geocoder:
    def __init__(self, data_dir, client=None, ttl_s=3600, timeout_s=3.0):
        self.addresses = data_dir / "clean" / "addresses.parquet"
        self.municipality_file = data_dir / "clean" / "municipality.parquet"
        self.client, self.ttl_s, self.timeout_s = client, ttl_s, timeout_s
        self._cache = {}
        self._municipalities = None

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
        while tokens and tokens[0] in STREET_TYPES:
            tokens = tokens[1:]
        numbers = [int(t) for t in tokens if t.isdigit()]
        words = [t for t in tokens if not t.isdigit() and t not in STOP_WORDS]
        muni = found[0] if found else None
        if not words:
            if muni:
                return [self._muni_candidate(muni)]
            return [self._muni_candidate(m) for m in self.municipalities() if q in m[2]][:MAX_CANDIDATES]
        number = numbers[-1] if numbers else None
        # callejero local primero (rapido y sin red); el buscador de Nomecalles solo si el local no encuentra el vial
        out = self._local(words, number, muni) or self._remote(text, muni)
        if not muni and not numbers:
            # «las rozas»: palabras de un municipio, antes que las calles; «geta»: parte de un nombre, si no hay calle
            partial = [m for m in self.municipalities() if f" {q} " in f" {m[2]} "]
            if not partial and not out:
                partial = [m for m in self.municipalities() if q in m[2]]
            out = [self._muni_candidate(m) for m in partial] + out
        if muni:
            out.append(self._muni_candidate(muni))      # respaldo: el centro del municipio
        unique = list({(c["label"], c["ine_code"]): c for c in out}.values())
        return unique[:MAX_CANDIDATES]

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

    def _local(self, words, number, muni):
        where = " AND ".join("(' ' || street_norm || ' ') LIKE ?" for _ in words)
        params = [f"% {w} %" for w in words]
        if muni:
            where += " AND ine_code = ?"
            params.append(muni[0])
        streets = {}
        for r in self._rows(where, params):
            streets.setdefault((r[0], r[2]), []).append(r)
        target = " ".join(words)
        # primero el vial cuyo nombre (sin «de la») es exactamente lo buscado, luego el mas corto
        ranked = sorted(streets.values(), key=lambda rows: (
            " ".join(t for t in rows[0][5].split() if t not in STOP_WORDS) != target, len(rows[0][5])))
        return [self._resolve_street(rows, number) for rows in ranked[:MAX_CANDIDATES]]

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
        return out[:MAX_CANDIDATES]
