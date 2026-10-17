"""Areas verdes de OSM -> app/data/clean/osm_green.parquet (verde de los destinos sin VPLA, Task 110).

Mismas etiquetas que las rutas (routing.yaml, clave osm_green) y misma lectura que graph.read_osm, pero
solo las areas: no rehace el grafo ni poi.parquet. Se ejecuta tras descargar `osm` y antes de build_db main.

Uso: python osm_green.py
"""
import geopandas as gpd
import shapely
import yaml

from common import CONFIG_DIR, RAW, municipalities, write

PBF = RAW / "osm" / "madrid-latest.osm.pbf"


def read_green_areas(pbf, green_tags):
    """Poligonos de las areas de OSM con alguna etiqueta de green_tags ({clave: [valores]}), EPSG:4326."""
    import osmium

    pairs = {(k, v) for k, values in (green_tags or {}).items() for v in values}
    rows = []
    if pairs:
        wkb_factory = osmium.geom.WKBFactory()

        class Reader(osmium.SimpleHandler):
            def area(self, a):
                if any((t.k, t.v) in pairs for t in a.tags):
                    try:
                        rows.append((a.orig_id(), wkb_factory.create_multipolygon(a)))
                    except RuntimeError:
                        pass                    # geometria rota en OSM: se salta (como graph.read_osm)

        Reader().apply_file(str(pbf), locations=True)
    return gpd.GeoDataFrame({"osm_id": [i for i, _ in rows]},
                            geometry=shapely.from_wkb([bytes.fromhex(w) for _, w in rows]), crs=4326)


def extract(pbf=PBF, config=None):
    """Lee las areas verdes del extracto y guarda las que tocan la Comunidad en clean/osm_green.parquet."""
    config = config or yaml.safe_load((CONFIG_DIR / "routing.yaml").read_text(encoding="utf-8"))
    green = read_green_areas(pbf, config.get("osm_green"))
    region = municipalities().union_all()
    green = green[green.intersects(region)].reset_index(drop=True)
    return write(green, "osm_green"), len(green)


if __name__ == "__main__":
    print(extract())
