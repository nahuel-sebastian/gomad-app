"""Carga y valida config/indicators.yaml (DEC-09, Task 34): indicadores de la vista de municipio y encaje RF-18.

Las categorias, perfiles y acompanantes son copia del contrato (app/api/schemas.py): ningun servicio importa
codigo de otro; test_contract_enums_in_sync las compara con el openapi.json.
"""
import yaml

from common import CONFIG_DIR

CATEGORIES = ("sport", "nature", "mobility", "health", "education", "connectivity", "social")
PROFILES = ("general", "senior", "stroller", "sensitive")
COMPANIONS = ("dog", "kids")
REQUIRED = ("key", "category", "label", "source", "unit", "no_rows", "year")
NO_ROWS = ("zero", "null")


class IndicatorConfigError(ValueError):
    pass


def _fail(msg):
    raise IndicatorConfigError(f"indicators.yaml: {msg}")


def _check_indicator(ind, n):
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
    if ind["year"] is not None and not isinstance(ind["year"], int):
        _fail(f"el indicador «{name}» tiene «year» {ind['year']!r}; debe ser un año o null")


def _check_refs(kind, allowed, mapping, keys):
    for who, refs in (mapping or {}).items():
        if who not in allowed:
            _fail(f"fit: {kind} «{who}» no está en el contrato ({', '.join(allowed)})")
        if isinstance(refs, dict):
            if "route_poi" not in refs:
                _fail(f"fit: {kind} «{who}» necesita una lista de indicadores o «route_poi»")
            continue
        for ref in refs:
            if ref not in keys:
                _fail(f"fit: {kind} «{who}» cita el indicador «{ref}», que no existe")


def validate(config):
    """Devuelve config si es valido; si no, IndicatorConfigError con un mensaje legible."""
    if not isinstance(config.get("population_year"), int):
        _fail("falta «population_year» (año del padrón para las tasas)")
    seen = set()
    for n, ind in enumerate(config.get("indicators") or [], start=1):
        _check_indicator(ind, n)
        if ind["key"] in seen:
            _fail(f"clave repetida «{ind['key']}»")
        seen.add(ind["key"])
    if not seen:
        _fail("no hay indicadores")
    fit = config.get("fit") or _fail("falta la sección «fit» (encaje RF-18)")
    if fit.get("own_criterion") is not True:
        _fail("fit: es criterio propio y debe llevar «own_criterion: true»")
    _check_refs("perfil", PROFILES, fit.get("profiles"), seen)
    _check_refs("acompañante", COMPANIONS, fit.get("companions"), seen)
    return config


def load(path=None):
    path = path or CONFIG_DIR / "indicators.yaml"
    return validate(yaml.safe_load(path.read_text(encoding="utf-8")))
