"""Carga y valida config/indicators.yaml (DEC-09, Task 34): indicadores de la vista de municipio y encaje RF-18.

Las categorias, perfiles y acompanantes son copia del contrato (app/api/schemas.py): ningun servicio importa
codigo de otro; test_contract_enums_in_sync las compara con el openapi.json.
"""
import re

import yaml

from common import CONFIG_DIR

CATEGORIES = ("sport", "nature", "mobility", "health", "education", "connectivity", "social")
PROFILES = ("general", "senior", "stroller", "sensitive")
COMPANIONS = ("dog", "kids")
REQUIRED = ("key", "category", "label", "source", "unit", "no_rows", "year")
NO_ROWS = ("zero", "null")
# que dice el encaje si no hay nada, segun la cobertura de la fuente (API: services/municipality.py ABSENT)
WHEN_ABSENT = ("none", "not_listed", "no_data")
# tipos de route_poi: furniture.py (Ayto. y DEA) y graph.py (OSM); test_poi_types_in_sync_with_route_poi los compara
POI_TYPES = ("fountain", "bench", "bin", "dog_area", "playground", "aed")
CATALOG_UNIT = re.compile(r"^de (\d+)$")   # «de 8»: actividades del catalogo con destino (activities.yaml)


class IndicatorConfigError(ValueError):
    pass


def _fail(msg):
    raise IndicatorConfigError(f"indicators.yaml: {msg}")


def _check_indicator(ind, n, activities_count):
    if not isinstance(ind, dict):
        _fail(f"el indicador n.º {n} debe ser un mapa con {', '.join(REQUIRED)}; es {ind!r}")
    name = ind.get("key") or f"n.º {n}"
    for field in REQUIRED:
        if field not in ind:
            _fail(f"al indicador «{name}» le falta «{field}»")
    if ind["category"] not in CATEGORIES:
        _fail(f"el indicador «{name}» tiene la categoría «{ind['category']}», que no está en el contrato "
              f"({', '.join(CATEGORIES)})")
    if ind["no_rows"] not in NO_ROWS:
        _fail(f"el indicador «{name}» tiene no_rows «{ind['no_rows']}»; debe ser {' o '.join(NO_ROWS)}")
    if not isinstance(ind["source"], list) or not ind["source"]:
        _fail(f"el indicador «{name}» necesita «source» como lista de ids de fuente")
    if "complement" in ind and (not isinstance(ind["complement"], list) or not ind["complement"]
                                or not all(isinstance(x, str) and x for x in ind["complement"])):
        _fail(f"el indicador «{name}» tiene «complement» {ind['complement']!r}; debe ser una lista de ids de fuente")
    if ind["year"] is not None and (isinstance(ind["year"], bool) or not isinstance(ind["year"], int)):
        _fail(f"el indicador «{name}» tiene «year» {ind['year']!r}; debe ser un año o null")
    if "unit_one" in ind and (not isinstance(ind["unit_one"], str) or not ind["unit_one"].strip()):
        _fail(f"el indicador «{name}» tiene «unit_one» {ind['unit_one']!r}; debe ser la unidad en singular")
    unit = CATALOG_UNIT.match(str(ind["unit"]))
    if activities_count is not None and "destination_activity" in ind["source"] and unit \
            and int(unit.group(1)) != activities_count:
        _fail(f"el indicador «{name}» tiene la unidad «{ind['unit']}», pero activities.yaml tiene "
              f"{activities_count} actividades: debe ser «de {activities_count}»")


def _check_absent(where, spec):
    value = (spec or {}).get("when_absent", "none")
    if value not in WHEN_ABSENT:
        _fail(f"fit: {where} tiene when_absent «{value}»; debe ser {', '.join(WHEN_ABSENT)}")


def _check_refs(kind, allowed, mapping, keys):
    for who, refs in (mapping or {}).items():
        if who not in allowed:
            _fail(f"fit: {kind} «{who}» no está en el contrato ({', '.join(allowed)})")
        if isinstance(refs, dict):
            if "route_poi" not in refs:
                _fail(f"fit: {kind} «{who}» necesita una lista de indicadores o «route_poi»")
            if refs["route_poi"] not in POI_TYPES:
                _fail(f"fit: {kind} «{who}» cita el tipo de route_poi «{refs['route_poi']}», que no existe "
                      f"({', '.join(POI_TYPES)})")
            missing = [f for f in ("label", "unit") if not refs.get(f)]
            if missing:
                _fail(f"fit: {kind} «{who}» necesita {' y '.join(missing)} (texto de la frase del encaje)")
            _check_absent(f"{kind} «{who}»", refs)
            continue
        for ref in refs:
            if ref not in keys:
                _fail(f"fit: {kind} «{who}» cita el indicador «{ref}», que no existe")


def validate(config, activities_count=None):
    """Devuelve config si es valido; si no, IndicatorConfigError con un mensaje legible.

    activities_count: n.º de actividades de activities.yaml, para comprobar la unidad «de N» (None = no se mira).
    """
    if not isinstance(config.get("population_year"), int):
        _fail("falta «population_year» (año del padrón para las tasas)")
    seen = set()
    for n, ind in enumerate(config.get("indicators") or [], start=1):
        _check_indicator(ind, n, activities_count)
        if ind["key"] in seen:
            _fail(f"clave repetida «{ind['key']}»")
        seen.add(ind["key"])
    if not seen:
        _fail("no hay indicadores")
    fit = config.get("fit") or _fail("falta la sección «fit» (encaje RF-18)")
    threshold = fit.get("met_if_above")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        _fail(f"fit: «met_if_above» debe ser un número; es {threshold!r}")
    if fit.get("own_criterion") is not True:
        _fail("fit: es criterio propio y debe llevar «own_criterion: true»")
    _check_absent("activities", fit.get("activities"))
    _check_refs("perfil", PROFILES, fit.get("profiles"), seen)
    _check_refs("acompañante", COMPANIONS, fit.get("companions"), seen)
    return config


def load(path=None):
    path = path or CONFIG_DIR / "indicators.yaml"
    activities = yaml.safe_load((CONFIG_DIR / "activities.yaml").read_text(encoding="utf-8"))["activities"]
    return validate(yaml.safe_load(path.read_text(encoding="utf-8")), activities_count=len(activities))
