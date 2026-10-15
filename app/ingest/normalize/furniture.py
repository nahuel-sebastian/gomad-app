import pandas as pd

from common import RAW, assign_municipality, filter_region, ine_code, latest_csv, points, read_csv, write
from normalize import normalizer

CITY_COUNCIL = {"ay_fuentes": "fountain", "ay_bancos": "bench", "ay_areas_caninas": "dog_area"}


def working_from_status(status):
    """True si OPERATIVO, False si trae otro estado, nulo si viene vacio (sin dato no es averia)."""
    working = (status.str.strip() == "OPERATIVO").astype("boolean")
    working[status.str.strip().fillna("") == ""] = pd.NA
    return working


@normalizer("poi")
def run():
    parts = []
    for source, kind in CITY_COUNCIL.items():
        # COORD_GIS_X/Y (25830): LATITUD/LONGITUD casi vacias en bancos y areas caninas (informe §2.1)
        df = read_csv(latest_csv(RAW / source, ["ID", "ESTADO", "COORD_GIS_X", "COORD_GIS_Y"]))
        g = points(df, "COORD_GIS_X", "COORD_GIS_Y", 25830)
        status = g["ESTADO"].str.strip().mask(lambda s: s == "")
        # las cerradas o fuera de servicio (1.045 fuentes) se guardan marcadas: el mapa las muestra como
        # no disponibles y la ruta solo cuenta las que funcionan (working distinto de False)
        parts.append(g.assign(id=source + ":" + g["ID"].astype(str), type=kind, source=source, ine_code="28079",
                              status=status, working=working_from_status(g["ESTADO"])))
    d = points(read_csv(latest_csv(RAW / "desfibriladores",
                                   ["codigo_dea", "municipio_codigo", "direccion_coordenada_x"])),
               "direccion_coordenada_x", "direccion_coordenada_y", 25830)
    parts.append(d.assign(id="desfibriladores:" + d["codigo_dea"].astype(str), type="aed", source="desfibriladores",
                          ine_code=d["municipio_codigo"].map(ine_code)))
    columns = ["id", "type", "source", "ine_code", "status", "working", "geometry"]
    allpoi = pd.concat([p.reindex(columns=columns) for p in parts], ignore_index=True)
    allpoi["working"] = allpoi["working"].astype("boolean")   # nulo = la fuente no informa del estado (DEA, OSM)
    allpoi = assign_municipality(allpoi.set_geometry("geometry"))
    allpoi, dropped = filter_region(allpoi)
    allpoi = allpoi.drop_duplicates("id")
    broken = int(allpoi["working"].eq(False).sum())
    print(f"   poi: {len(allpoi)} puntos ({dropped} fuera, {broken} fuera de servicio)")
    return write(allpoi, "poi")
