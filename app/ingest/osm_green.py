"""Areas verdes de OSM -> app/data/clean/osm_green.parquet (verde de los destinos sin VPLA, Task 110) y
clean/osm_parks.parquet (solo parques: zonas verdes por habitante fuera de VPLA, Task 175).

Mismas etiquetas que las rutas (routing.yaml, clave osm_green) y misma lectura que graph.read_osm, pero
solo las areas: no rehace el grafo ni poi.parquet. Se ejecuta tras descargar `osm` y antes de build_db main.

Uso: python osm_green.py
"""
import geopandas as gpd
import shapely
import yaml

from common import CONFIG_DIR, RAW, municipalities, write

PBF = RAW / "osm" / "madrid-latest.osm.pbf"


def read_area_sets(pbf, sets):
    """Una sola lectura del extracto: {nombre: GeoDataFrame (osm_id, geometry, EPSG:4326)} con las areas que tienen
    alguna etiqueta de sets[nombre] ({clave: [valores]}). Un area puede estar en varios conjuntos."""
    import osmium

    pairs = {name: {(k, v) for k, values in (tags or {}).items() for v in values} for name, tags in sets.items()}
    rows = {name: [] for name in sets}
    if any(pairs.values()):
        wkb_factory = osmium.geom.WKBFactory()

        class Reader(osmium.SimpleHandler):
            def area(self, a):
                tags = {(t.k, t.v) for t in a.tags}
                hits = [name for name, p in pairs.items() if tags & p]
                if not hits:
                    return
                try:
                    wkb = wkb_factory.create_multipolygon(a)
                except RuntimeError:
                    return                      # geometria rota en OSM: se salta (como graph.read_osm)
                for name in hits:
                    rows[name].append((a.orig_id(), wkb))

        Reader().apply_file(str(pbf), locations=True)
    return {name: gpd.GeoDataFrame({"osm_id": [i for i, _ in r]},
                                   geometry=shapely.from_wkb([bytes.fromhex(w) for _, w in r]), crs=4326)
            for name, r in rows.items()}


def read_green_areas(pbf, green_tags):
    """Poligonos de las areas de OSM con alguna etiqueta de green_tags ({clave: [valores]}), EPSG:4326."""
    return read_area_sets(pbf, {"green": green_tags})["green"]


def extract(pbf=PBF, config=None, parks_tags=None):
    """Lee las areas verdes (routing.yaml osm_green: destinos y rutas) y los parques (indicators.yaml osm_parks:
    zonas verdes por habitante fuera de VPLA, Task 175) y guarda las que tocan la Comunidad en
    clean/osm_green.parquet y clean/osm_parks.parquet. Devuelve (ruta_verde, n_verde, ruta_parques, n_parques)."""
    config = config or yaml.safe_load((CONFIG_DIR / "routing.yaml").read_text(encoding="utf-8"))
    if parks_tags is None:
        parks_tags = yaml.safe_load((CONFIG_DIR / "indicators.yaml").read_text(encoding="utf-8"))["osm_parks"]["tags"]
    sets = read_area_sets(pbf, {"green": config.get("osm_green"), "parks": parks_tags})
    region = municipalities().union_all()
    out = []
    for name, target in (("green", "osm_green"), ("parks", "osm_parks")):
        g = sets[name][sets[name].intersects(region)].reset_index(drop=True)
        out += [write(g, target), len(g)]
    return tuple(out)


if __name__ == "__main__":
    print(extract())
