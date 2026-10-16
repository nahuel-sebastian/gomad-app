import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import LineString, Point, Polygon

from common import RAW, assign_municipality, filter_region, ine_code, latest_csv, points, read_csv, to_float, write
from normalize import normalizer

SPORT_COLUMNS = ["SUBACUATIC", "ATLETISMO", "BEISBOL", "BALONCESTO", "BALONMANO", "BOLOS", "BALONVOLEA",
                 "DEPINVIERN", "ESQUINAUTI", "FUTBOL", "GOLF", "GIMNASIA", "JUDOKARATE", "LUCHA", "NATACION",
                 "OTROS", "PADEL", "PELOTA", "PIRAGUISMO", "PATINAJE", "REMO", "TENIS", "TIROALPLAT", "VELA"]
COLUMNS = ["id", "source", "source_id", "name", "type", "covered", "accessible", "condition", "owner", "water",
           "sports", "facility_type", "label", "area_m2", "url", "ine_code", "geometry"]


# TIPOINSTAL decide si la instalacion es cubierta: SUP_CUBI > 0 tambien lo cumplen piscinas al aire libre
# o campos con vestuario o grada cubiertos. Los tipos mixtos (complejos, otros) se deciden por SUP_CUBI.
OUTDOOR_TYPES = ("AIRE LIBRE", "SIN CUBRIR", "PISTAS POLIDEPORTIVAS", "TERRENOS DE JUEGO", "ESCUELA DE VELA",
                 "ESTACIONES DE ESQUI", "PUERTO DEPORTIVO")
COVERED_TYPES = ("CUBIERT", "GIMNASIO")
# nombre por defecto cuando la fuente no trae ninguno (DS_USO_DETA vacio en VPLA)
DEFAULT_NAMES = {"facility": "Instalación deportiva", "park": "Zona verde", "recreation_area": "Área recreativa"}
FLAGS = ("covered", "accessible", "water")

# OSM filtrado como fuente de destinos (decidido el 16/10, ficha B3): solo lo que tiene poca duda de ser publico
OSM_PBF = RAW / "osm" / "madrid-latest.osm.pbf"
OSM_CENTRES = ("sports_centre", "stadium")            # con sport=* y name
OSM_PITCH_SPORTS = ("tennis", "basketball", "padel")  # leisure=pitch, con name o access=yes|public
OSM_OPEN_ACCESS = ("yes", "public")
OSM_DEFAULT_NAMES = {"tennis": "Pista de tenis (OpenStreetMap)", "basketball": "Pista de baloncesto (OpenStreetMap)",
                     "padel": "Pista de pádel (OpenStreetMap)", "swimming": "Piscina (OpenStreetMap)"}


def eiel_covered(facility_type, sup_cubi):
    kind = str(facility_type or "").upper()
    if any(t in kind for t in OUTDOOR_TYPES):
        return False
    if any(t in kind for t in COVERED_TYPES):
        return True
    area = to_float(sup_cubi)
    return None if area is None else area > 0


def is_yes(v):
    return str(v).strip().upper() == "SI"


def eiel_sports():
    g = gpd.read_file(RAW / "eiel_deporte" / "eiel_deporte.geojson").set_crs(25830, allow_override=True).to_crs(4326)
    g["geometry"] = g.geometry.representative_point()
    g["source_id"] = g[["PROV", "MUN", "ENT", "POBLAMIENT", "ORDEN_INST"]].astype(str).agg("-".join, axis=1)
    g["source"], g["type"] = "eiel_deporte", "facility"
    g["name"] = g["NOMBRE"]
    g["covered"] = [eiel_covered(t, v) for t, v in zip(g["TIPOINSTAL"], g["SUP_CUBI"])]
    g["accessible"] = g["ACCESOSILL"].map(lambda v: None if not v else not str(v).upper().startswith("SIN"))
    g["condition"], g["owner"], g["facility_type"] = g["ESTADO"], g["TITULAR"], g["TIPOINSTAL"]
    g["sports"] = g[SPORT_COLUMNS].apply(lambda row: [c for c in SPORT_COLUMNS if is_yes(row[c])], axis=1)
    g["ine_code"] = g["MUN"].map(ine_code)
    return g


def nmc_sports():
    df = gpd.read_file(next((RAW / "nmc_deporte").glob("*.shp")), ignore_geometry=True)   # .prj no fiable
    g = points(df, "UTM_X", "UTM_Y", 25830)
    # ID_APP se repite en instalaciones distintas del mismo complejo (33 ids, 69 filas):
    # se numeran por orden estable de nombre y coordenadas -> "794536-1", "794536-2"
    g["source_id"] = g["ID_APP"].astype(str).str.strip()
    g = g.sort_values(["source_id", "DESCR", "UTM_X", "UTM_Y"])
    repeated = g["source_id"].duplicated(keep=False)
    n = g.groupby("source_id").cumcount() + 1
    g.loc[repeated, "source_id"] = g.loc[repeated, "source_id"] + "-" + n[repeated].astype(str)
    g["source"], g["type"] = "nmc_deporte", "facility"
    g["name"], g["label"], g["url"] = g["DESCR"], g["ETIQUETA"], g["URL"]
    g["ine_code"] = g["CMUN"].map(ine_code)
    g["sports"] = [[] for _ in range(len(g))]
    return g


def city_council(source):
    g = points(read_csv(latest_csv(RAW / source, ["PK", "NOMBRE", "LATITUD", "LONGITUD"])), "LONGITUD", "LATITUD", 4326)
    g["source_id"], g["source"], g["type"] = g["PK"], source, "facility"
    g["name"], g["url"], g["label"] = g["NOMBRE"], g["CONTENT-URL"], g["EQUIPAMIENTO"]
    g["ine_code"] = "28079"
    g["sports"] = [[] for _ in range(len(g))]
    return g


def _sports(value):
    return [s.strip().lower() for s in str(value or "").split(";") if s.strip()]


def osm_sport_tags(tags):
    """Deportes del elemento si entra en el catalogo (ficha B3), None si no."""
    leisure, name, access = tags.get("leisure"), str(tags.get("name") or "").strip(), tags.get("access")
    sports = _sports(tags.get("sport"))
    if leisure in OSM_CENTRES:
        return sports if sports and name else None
    if leisure == "pitch":
        kept = [s for s in sports if s in OSM_PITCH_SPORTS]
        return kept if kept and (name or access in OSM_OPEN_ACCESS) else None
    if leisure == "swimming_pool":
        # nunca las privadas ni las sin nombre (comunidades de vecinos): solo con nombre o access=public
        if access == "private" or not (name or access == "public"):
            return None
        return ["swimming"]
    return None


def osm_default_name(tags, sports):
    name = str(tags.get("name") or "").strip()
    return name or next((OSM_DEFAULT_NAMES[s] for s in sports if s in OSM_DEFAULT_NAMES), "Instalación deportiva")


def _osm_row(kind, osm_id, tags, sports, geometry):
    covered = True if "yes" in (tags.get("covered"), tags.get("indoor")) else False if tags.get("leisure") == "pitch" else None
    return {"id": f"osm:{kind}/{osm_id}", "source": "osm_sport", "source_id": f"{kind}/{osm_id}", "type": "facility",
            "name": osm_default_name(tags, sports), "sports": sports, "facility_type": tags.get("leisure"),
            "covered": covered, "access": tags.get("access"), "geometry": geometry}


def _way_point(coords):
    if len(coords) >= 4 and coords[0] == coords[-1]:
        poly = Polygon(coords)
        if poly.is_valid:
            return poly.representative_point()
    return LineString(coords).interpolate(0.5, normalized=True) if len(coords) > 1 else Point(coords[0])


def osm_sports(pbf):
    """Destinos deportivos de OSM filtrado (nodos, vias y multipoligonos) como puntos EPSG:4326."""
    import osmium

    wkb_factory = osmium.geom.WKBFactory()

    class Reader(osmium.SimpleHandler):
        def __init__(self):
            super().__init__()
            self.rows = []

        def node(self, n):
            tags = dict(n.tags)
            sports = osm_sport_tags(tags) if "leisure" in tags else None
            if sports and n.location.valid():
                self.rows.append(_osm_row("node", n.id, tags, sports, Point(n.location.lon, n.location.lat)))

        def way(self, w):
            tags = dict(w.tags)
            sports = osm_sport_tags(tags) if "leisure" in tags else None
            if sports:
                coords = [(n.location.lon, n.location.lat) for n in w.nodes if n.location.valid()]
                if coords:
                    self.rows.append(_osm_row("way", w.id, tags, sports, _way_point(coords)))

        def area(self, a):
            if a.from_way():
                return                      # las vias cerradas ya entran por way()
            tags = dict(a.tags)
            sports = osm_sport_tags(tags) if "leisure" in tags else None
            if sports:
                try:
                    geom = shapely.from_wkb(bytes.fromhex(wkb_factory.create_multipolygon(a)))
                except RuntimeError:
                    return                  # multipoligono roto en OSM: se salta
                self.rows.append(_osm_row("relation", a.orig_id(), tags, sports, geom.representative_point()))

    r = Reader()
    r.apply_file(str(pbf), locations=True)
    columns = ["id", "source", "source_id", "type", "name", "sports", "facility_type", "covered", "access", "geometry"]
    g = gpd.GeoDataFrame(pd.DataFrame(r.rows, columns=columns), geometry="geometry", crs=4326)
    g["ine_code"] = None
    return g


@normalizer("destination_raw")
def run():
    from normalize.green import green_destinations   # los parques tambien son destinos
    parts = [eiel_sports(), nmc_sports()] + [city_council(s) for s in ("ay_polideportivos", "ay_idb", "ay_piscinas")]
    parts += green_destinations()
    if OSM_PBF.exists():
        parts.append(osm_sports(OSM_PBF))   # id propio osm:<tipo>/<id>, como route_poi
    else:
        print(f"   aviso: falta {OSM_PBF}; destination_raw sin destinos de OSM")
    alldest = pd.concat([p.reindex(columns=COLUMNS) for p in parts], ignore_index=True)
    alldest["id"] = alldest["id"].fillna(alldest["source"] + ":" + alldest["source_id"].astype(str))
    blank = alldest["name"].isna() | (alldest["name"].astype(str).str.strip() == "")
    alldest.loc[blank, "name"] = alldest.loc[blank, "type"].map(DEFAULT_NAMES)
    for col in FLAGS:
        alldest[col] = alldest[col].astype("boolean")
    alldest = gpd.GeoDataFrame(alldest, geometry="geometry", crs=4326)
    alldest = assign_municipality(alldest)
    alldest, dropped = filter_region(alldest)
    print(f"   destination_raw: {len(alldest)} destinos, {dropped} fuera de la Comunidad descartados")
    return write(alldest, "destination_raw")
