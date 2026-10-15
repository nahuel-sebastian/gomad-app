import pandas as pd

from common import RAW, assign_municipality, filter_region, ine_code, points, read_csv, write
from normalize import normalizer

CITY_COUNCIL = {"ay_fuentes": "fountain", "ay_bancos": "bench", "ay_areas_caninas": "dog_area"}


@normalizer("poi")
def run():
    parts = []
    for source, kind in CITY_COUNCIL.items():
        # COORD_GIS_X/Y (25830): LATITUD/LONGITUD casi vacias en bancos y areas caninas (informe §2.1)
        g = points(read_csv(next((RAW / source).glob("*.csv"))), "COORD_GIS_X", "COORD_GIS_Y", 25830)
        parts.append(g.assign(id=source + ":" + g["ID"].astype(str), type=kind, source=source, ine_code="28079"))
    d = points(read_csv(next((RAW / "desfibriladores").glob("*.csv"))),
               "direccion_coordenada_x", "direccion_coordenada_y", 25830)
    parts.append(d.assign(id="desfibriladores:" + d["codigo_dea"].astype(str), type="aed", source="desfibriladores",
                          ine_code=d["municipio_codigo"].map(ine_code)))
    allpoi = pd.concat([p[["id", "type", "source", "ine_code", "geometry"]] for p in parts], ignore_index=True)
    allpoi = assign_municipality(allpoi.set_geometry("geometry"))
    allpoi, dropped = filter_region(allpoi)
    allpoi = allpoi.drop_duplicates("id")
    print(f"   poi: {len(allpoi)} puntos ({dropped} fuera)")
    return write(allpoi, "poi")
