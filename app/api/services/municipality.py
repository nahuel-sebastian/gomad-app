"""GET /municipality/{ine_code} (F5, RF-17, RF-19): indicadores DEC-09 de un municipio con su fuente y fecha.

Determinista y sin IA. Sin ranking ni comparacion con otros municipios. Que indicadores hay, su etiqueta y su
orden salen de config/indicators.yaml; los valores, de la tabla municipality_indicator (ingest, Task 35)."""
import schemas as s
import settings
from services.common import data_source


class UnknownMunicipality(LookupError):
    pass


def indicators(cfg, rows, labels, dates):
    """Un Indicator por entrada del YAML, en su orden; sin fila o con NULL -> value None («sin datos»)."""
    out = []
    for ind in cfg["indicators"]:
        value, unit, year, source = rows.get(ind["key"], (None, ind["unit"], ind["year"], ind["source"][0]))
        out.append(s.Indicator(category=ind["category"], key=ind["key"], label=ind["label"], value=value, unit=unit,
                               year=year, source=data_source(source, labels, dates.get(source))))
    return out


def municipality(ine_code, repo):
    info = repo.municipality(ine_code)
    if info is None:
        raise UnknownMunicipality(f"No hay ningún municipio de la Comunidad de Madrid con el código «{ine_code}».")
    name, population = info
    labels = (settings.load("sources") or {}).get("labels", {})
    items = indicators(settings.load("indicators"), repo.municipality_indicators(ine_code), labels,
                       repo.source_dates())
    return s.MunicipalityResponse(ine_code=ine_code, name=repo.municipality_names().get(ine_code, name),
                                  population=population, indicators=items, fit=[])
