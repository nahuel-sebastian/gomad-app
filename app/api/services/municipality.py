"""GET /municipality/{ine_code} (F5, RF-17, RF-18, RF-19): indicadores DEC-09 de un municipio con su fuente y fecha
y encaje con las preferencias de la persona.

Determinista y sin IA. Sin ranking, nota ni comparacion con otros municipios. Que indicadores hay, su etiqueta,
su orden y que mira cada perfil salen de config/indicators.yaml; los valores, de la tabla municipality_indicator
(ingest, Task 35)."""
import schemas as s
import settings
from services.common import data_source

POI_LABELS = {"dog_area": ("Áreas caninas", "área", "áreas")}   # route_poi del encaje: etiqueta, singular, plural


class UnknownMunicipality(LookupError):
    pass


class UnknownActivity(ValueError):
    pass


def number(value):
    """Formato espanol: enteros sin decimales; el resto con uno (con dos si con uno saldria 0)."""
    digits = 0 if float(value).is_integer() else (1 if abs(value) >= 0.05 else 2)
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def indicators(cfg, rows, labels, dates):
    """Un Indicator por entrada del YAML, en su orden; sin fila o con NULL -> value None («sin datos»)."""
    out = []
    for ind in cfg["indicators"]:
        value, unit, year, source = rows.get(ind["key"], (None, ind["unit"], ind["year"], ind["source"][0]))
        out.append(s.Indicator(category=ind["category"], key=ind["key"], label=ind["label"], value=value, unit=unit,
                               year=year, source=data_source(source, labels, dates.get(source))))
    return out


def fit_sentences(fit_cfg, by_key, activities, profile, companions, activity_label, activity_count, poi_count):
    """Encaje RF-18: «Cumple N de M[, K sin datos]» y una frase por preferencia. Sin nota, orden ni percentil.

    activity_count(actividad) y poi_count(tipo) dicen cuantos hay en el municipio."""
    above = fit_cfg["met_if_above"]
    checks = []                                   # (True cumple | False no | None sin datos, frase)
    for a in dict.fromkeys(activities):
        n = activity_count(a)
        checks.append((True, f"{activity_label[a]}: sí, {n} {'sitio' if n == 1 else 'sitios'}") if n > above
                      else (False, f"{activity_label[a]}: no hay en este municipio"))
    wanted = list(fit_cfg["profiles"].get(profile, []))
    for c in dict.fromkeys(companions):
        spec = fit_cfg["companions"].get(c, [])
        wanted.extend([spec] if isinstance(spec, dict) else spec)
    seen = set()
    for w in wanted:
        if isinstance(w, dict):                   # punto de ruta (OSM/Ayto., cobertura parcial)
            label, one, many = POI_LABELS[w["route_poi"]]
            n = poi_count(w["route_poi"])
            if n > above:
                checks.append((True, f"{label}: sí, {n} {one if n == 1 else many}"))
            elif w.get("when_absent") == "no_data":
                checks.append((None, f"{label}: sin datos"))          # perro: nunca «No»
            else:
                checks.append((False, f"{label}: no hay en este municipio"))
            continue
        if w in seen:
            continue
        seen.add(w)
        ind = by_key[w]
        if ind.value is None:
            checks.append((None, f"{ind.label}: sin datos"))
        elif ind.value > above:
            checks.append((True, f"{ind.label}: sí, {number(ind.value)} {ind.unit}"))
        else:
            checks.append((False, f"{ind.label}: no hay en este municipio"))
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
    fit = fit_sentences(cfg["fit"], {i.key: i for i in items}, activities, profile, companions, activity_label,
                        lambda a: counts.get(a, 0), lambda t: repo.poi_count(ine_code, t))
    return s.MunicipalityResponse(ine_code=ine_code, name=repo.municipality_names().get(ine_code, name),
                                  population=population, indicators=items, fit=fit)
