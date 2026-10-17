"""GET /municipality/{ine_code} (F5, RF-17, RF-18, RF-19): indicadores DEC-09 de un municipio con su fuente y fecha
y encaje con las preferencias de la persona.

Determinista y sin IA. Sin ranking, nota ni comparacion con otros municipios. Que indicadores hay, su etiqueta,
su orden y que mira cada perfil salen de config/indicators.yaml; los valores, de la tabla municipality_indicator
(ingest, Task 35)."""
import math

import schemas as s
import settings
from services.common import data_source

# que se dice cuando una comprobacion no encuentra nada, segun la cobertura de su fuente (fit.*.when_absent)
ABSENT = {"none": (False, "no hay en este municipio"),
          "not_listed": (False, "no consta en nuestros datos"),
          "no_data": (None, "sin datos")}


class UnknownMunicipality(LookupError):
    pass


class UnknownActivity(ValueError):
    pass


def number(value):
    """Formato espanol: enteros sin decimales; desde 1, un decimal; por debajo de 1, dos cifras significativas.
    Sin ceros de cola, para no escribir «0,00» ni «1,0» de algo que no es exactamente eso."""
    value = float(value)
    if value.is_integer():
        digits = 0
    elif abs(value) >= 1:
        digits = 1
    else:
        digits = 1 - math.floor(math.log10(abs(value)))
    text = f"{value:,.{digits}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(",", " ").replace(".", ",").replace(" ", ".")


def validate_fit(cfg, activity_ids):
    """Comprueba la seccion fit de indicators.yaml al arrancar: un error de configuracion para el arranque, no
    sale como 500 en una peticion. Devuelve cfg."""
    keys = {i["key"] for i in cfg["indicators"]}
    fit = cfg["fit"]

    def absent(where, value):
        if value not in ABSENT:
            raise ValueError(f"indicators.yaml: fit.{where} tiene when_absent «{value}»; debe ser "
                             f"{', '.join(ABSENT)}")

    absent("activities", (fit.get("activities") or {}).get("when_absent", "none"))
    for kind in ("profiles", "companions"):
        for who, refs in (fit.get(kind) or {}).items():
            if isinstance(refs, dict):
                missing = [f for f in ("route_poi", "label", "unit") if f not in refs]
                if missing:
                    raise ValueError(f"indicators.yaml: fit.{kind}.{who} necesita {', '.join(missing)}")
                absent(f"{kind}.{who}", refs.get("when_absent", "none"))
                continue
            for ref in refs:
                if ref not in keys:
                    raise ValueError(f"indicators.yaml: fit.{kind}.{who} cita el indicador «{ref}», que no existe")
    return cfg


def indicators(cfg, rows, labels, dates):
    """Un Indicator por entrada del YAML, en su orden; sin fila o con NULL -> value None («sin datos»)."""
    out = []
    for ind in cfg["indicators"]:
        value, unit, year, source = rows.get(ind["key"], (None, ind["unit"], ind["year"], ind["source"][0]))
        # RF-19: la tabla guarda las fuentes usadas en ese municipio separadas por comas (C3: la principal o una
        # complementaria primero); despues van las fijas del YAML (padron en las tasas...) que no esten ya
        used = [x for x in str(source).split(",") if x]
        source = used[0]
        extra = list(dict.fromkeys(used[1:] + [x for x in ind["source"][1:] if x not in used]))
        out.append(s.Indicator(category=ind["category"], key=ind["key"], label=ind["label"], value=value, unit=unit,
                               year=year, source=data_source(source, labels, dates.get(source)),
                               extra_sources=[data_source(x, labels, dates.get(x)) for x in extra]))
    return out


def _absent(label, when_absent):
    ok, text = ABSENT[when_absent]
    return ok, f"{label}: {text}"


def fit_sentences(fit_cfg, by_key, activities, profile, companions, activity_label, activity_count, poi_count,
                  units_one=None):
    """Encaje RF-18: «Cumple N de M[, K sin datos]» y una frase por preferencia. Sin nota, orden ni percentil.

    activity_count(actividad) y poi_count(tipo) dicen cuantos hay en el municipio; units_one, la unidad en
    singular de cada indicador. Lo que se dice si no hay nada depende de la cobertura de la fuente (ABSENT)."""
    above = fit_cfg["met_if_above"]
    units_one = units_one or {}
    activity_absent = (fit_cfg.get("activities") or {}).get("when_absent", "none")
    checks = []                                   # (True cumple | False no | None sin datos, frase)
    for a in dict.fromkeys(activities):
        n = activity_count(a)
        checks.append((True, f"{activity_label[a]}: sí, {n} {'sitio' if n == 1 else 'sitios'}") if n > above
                      else _absent(activity_label[a], activity_absent))
    wanted = list(fit_cfg["profiles"].get(profile, []))
    for c in dict.fromkeys(companions):
        spec = fit_cfg["companions"].get(c, [])
        wanted.extend([spec] if isinstance(spec, dict) else spec)
    seen = set()
    for w in wanted:
        if isinstance(w, dict):                   # punto de ruta (OSM/Ayto., cobertura parcial)
            if w["route_poi"] in seen:
                continue
            seen.add(w["route_poi"])
            n = poi_count(w["route_poi"])
            unit = w.get("unit_one", w["unit"]) if n == 1 else w["unit"]
            checks.append((True, f"{w['label']}: sí, {n} {unit}") if n > above
                          else _absent(w["label"], w.get("when_absent", "none")))   # perro: no_data, nunca «No»
            continue
        if w in seen:
            continue
        seen.add(w)
        ind = by_key[w]
        if ind.value is None:
            checks.append((None, f"{ind.label}: sin datos"))
        elif ind.value > above:
            unit = units_one.get(w, ind.unit) if ind.value == 1 else ind.unit
            checks.append((True, f"{ind.label}: sí, {number(ind.value)} {unit}"))
        else:
            checks.append(_absent(ind.label, "none"))      # registro completo o valor medido 0
    if not checks:
        return []
    met = sum(1 for ok, _ in checks if ok)
    no_data = sum(1 for ok, _ in checks if ok is None)
    return [f"Cumple {met} de {len(checks)}" + (f", {no_data} sin datos" if no_data else "")] + [t for _, t in checks]


def municipality(ine_code, repo, activities=(), profile="general", companions=()):
    activity_label = {a["id"]: a["label"] for a in settings.load("activities")["activities"]}
    for a in activities:
        if a not in activity_label:
            raise UnknownActivity(f"Actividad desconocida: {a}")
    info = repo.municipality(ine_code)
    if info is None:
        raise UnknownMunicipality(f"No hay ningún municipio de la Comunidad de Madrid con el código «{ine_code}».")
    name, population = info
    cfg = settings.load("indicators")
    labels = (settings.load("sources") or {}).get("labels", {})
    items = indicators(cfg, repo.municipality_indicators(ine_code), labels, repo.source_dates())
    counts = repo.activity_counts(ine_code) if activities else {}
    units_one = {i["key"]: i["unit_one"] for i in cfg["indicators"] if "unit_one" in i}
    fit = fit_sentences(cfg["fit"], {i.key: i for i in items}, activities, profile, companions, activity_label,
                        lambda a: counts.get(a, 0), lambda t: repo.poi_count(ine_code, t), units_one)
    return s.MunicipalityResponse(ine_code=ine_code, name=repo.municipality_names().get(ine_code, name),
                                  population=population, indicators=items, fit=fit,
                                  fit_own_criterion=bool(fit) and cfg["fit"].get("own_criterion") is True)
