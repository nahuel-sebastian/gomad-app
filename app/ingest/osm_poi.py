"""Mobiliario de OSM -> app/data/clean/osm_poi.parquet (route_poi fuera de Madrid capital, C2b).

Mismas etiquetas (graph.OSM_POI), mismos ids y mismo esquema (graph.osm_pois) que el mobiliario que usa
el grafo, pero sin rehacer la red peatonal: se ejecuta tras descargar `osm` y antes de build_db main.

Uso: python osm_poi.py
"""
import time

import pandas as pd
import yaml

import common
from common import CONFIG_DIR, RAW, assign_municipality, municipalities
from graph import OSM_POI, osm_pois

PBF = RAW / "osm" / "madrid-latest.osm.pbf"


def read_furniture(pbf, out_of_service):
    """Elementos de mobiliario del extracto (nodos y vias) con su estado.

    Devuelve osm_type, osm_id, key, value, coords (como graph.read_osm) y status: "clave=valor" de la
    primera etiqueta de out_of_service ({clave: [valores]}) que tenga el elemento, o None.
    """
    import osmium

    pairs = [(k, v) for k, values in (out_of_service or {}).items() for v in values]

    def kind(tags):
        for key, value in OSM_POI:
            if tags.get(key) == value:
                return key, value
        return None

    def status(tags):
        return next((f"{k}={v}" for k, v in pairs if tags.get(k) == v), None)

    rows = []

    class Reader(osmium.SimpleHandler):
        def node(self, n):
            tag = kind(n.tags)
            if tag and n.location.valid():
                rows.append(("node", n.id, *tag, [(n.location.lon, n.location.lat)], status(n.tags)))

        def way(self, w):
            tag = kind(w.tags)
            if tag:
                coords = [(n.location.lon, n.location.lat) for n in w.nodes if n.location.valid()]
                if coords:
                    rows.append(("way", w.id, *tag, coords, status(w.tags)))

    Reader().apply_file(str(pbf), locations=True)
    return pd.DataFrame(rows, columns=["osm_type", "osm_id", "key", "value", "coords", "status"])


def furniture_frame(osm):
    """Esquema de clean/poi.parquet; working = False si OSM lo marca fuera de servicio, si no sin dato."""
    pois = osm_pois(osm)
    if len(pois):
        st = osm["status"].reset_index(drop=True)
        pois["status"] = st.where(st.notna(), None).to_numpy()
        pois["working"] = pd.array([False if s is not None else pd.NA for s in pois["status"]], dtype="boolean")
    return pois


def extract(pbf=PBF, config=None):
    """Lee el mobiliario, se queda con el de la Comunidad, le pone municipio y escribe clean/osm_poi.parquet."""
    config = config or yaml.safe_load((CONFIG_DIR / "routing.yaml").read_text(encoding="utf-8"))
    pois = furniture_frame(read_furniture(pbf, config["osm_poi"]["out_of_service"]))
    pois = pois[pois.intersects(municipalities().union_all())].copy()
    pois = assign_municipality(pois).reset_index(drop=True)
    return common.write(pois, "osm_poi"), len(pois)


if __name__ == "__main__":
    t0 = time.perf_counter()
    path, n = extract()
    print(path, n, f"{time.perf_counter() - t0:.1f} s")
