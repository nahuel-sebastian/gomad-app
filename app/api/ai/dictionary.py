"""Diccionario del catalogo RF-21 (DEC-03): texto (+ analisis de OCI Language) -> AssistantParams, aclaracion o rechazo.

Reglas puras, sin red. Palabras, mensajes y topes en config/assistant.yaml (seccion interpret y messages).
La IA no decide nada aqui: solo se buscan palabras del catalogo cerrado."""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import get_args

import schemas as s

PASS_BY = get_args(s.AssistantParams.model_fields["pass_by"].annotation.__args__[0])
AVOID = get_args(s.AssistantParams.model_fields["avoid"].annotation.__args__[0])
ACTIVITIES = get_args(s.AssistantParams.model_fields["activity"].annotation)
PUNCTUATION = set(",.;:!?¿¡")
REQUIRED = {"interpret": ["activities", "pass_by", "avoid", "avoid_direct", "negations", "negation_window",
                          "negation_breaks", "one_way", "out_of_catalog", "medical", "distance_units",
                          "duration_units", "duration_phrases", "quantity_entity_types", "max_distance_km",
                          "max_duration_min", "default_activity"],
            "messages": ["medical", "out_of_catalog", "missing_amount", "which_activity", "too_long"],
            "oci": ["timeout_s", "language_code"],
            "templates": ["summary", "score", "failed", "join_last"]}


@dataclass
class Analysis:
    """Lo que devuelve OCI Language para un texto: entidades (texto, tipo) y frases clave."""
    entities: list = field(default_factory=list)
    phrases: list = field(default_factory=list)


def normalize(text):
    """Minusculas, sin tildes y con espacios simples; conserva la puntuacion que corta negaciones."""
    plain = "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).lower()
    plain = re.sub(r"[^\w\s,.;:!?¿¡]", " ", plain)
    return " ".join(plain.split())


def validate_assistant_config(cfg):
    for section, keys in REQUIRED.items():
        missing = [k for k in keys if k not in (cfg or {}).get(section, {})]
        if missing:
            raise ValueError(f"assistant.yaml: faltan {section}.{missing}")
    it = cfg["interpret"]
    for key, allowed in (("pass_by", PASS_BY), ("avoid", AVOID), ("avoid_direct", AVOID), ("activities", ACTIVITIES)):
        unknown = set(it[key]) - set(allowed)
        if unknown:
            raise ValueError(f"assistant.yaml: {key} con valores fuera del contrato: {sorted(unknown)}")
    if it["default_activity"] not in ACTIVITIES:
        raise ValueError("assistant.yaml: default_activity fuera del contrato")


def _tokens(text):
    return [(m.start(), m.group()) for m in re.finditer(r"\w+|[,.;:!?¿¡]", text)]


def _matches(text, groups):
    """[(inicio, fin, grupo, valor)] sin solapes: la palabra mas larga gana («parque infantil» frente a «parque»)."""
    found = []
    for group, mapping in groups.items():
        for value, words in mapping.items():
            for word in words:
                for m in re.finditer(r"(?<!\w)" + re.escape(normalize(word)) + r"\w*", text):
                    found.append((m.start(), m.end(), group, value, len(word)))
    found.sort(key=lambda f: (-f[4], f[0]))
    taken, result = [], []
    for start, end, group, value, _ in found:
        if all(end <= a or start >= b for a, b in taken):
            taken.append((start, end))
            result.append((start, end, group, value))
    return sorted(result)


def _negated(tokens, start, it):
    negations, breaks = set(it["negations"]), set(it["negation_breaks"])
    before = [t for pos, t in tokens if pos < start][-it["negation_window"]:]
    for token in reversed(before):
        if token in PUNCTUATION or token in breaks:
            return False
        if token in negations:
            return True
    return False


def _quantity(text, units):
    alternatives = "|".join(sorted((re.escape(u) for u in units), key=len, reverse=True))
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(" + alternatives + r")(?!\w)", text)
    if not m:
        return None
    return float(m.group(1).replace(",", ".")) * units[m.group(2)]


def _duration(text, it):
    for phrase, minutes in sorted(it["duration_phrases"].items(), key=lambda kv: -len(kv[0])):
        if re.search(r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)", text):
            return float(minutes)
    return _quantity(text, it["duration_units"])


def _amounts(text, analysis, it):
    """(km, minutos): primero las entidades de cantidad de OCI, despues el texto."""
    km = minutes = None
    if analysis:
        for entity_text, entity_type in analysis.entities:
            if entity_type in it["quantity_entity_types"]:
                e = normalize(entity_text)
                km = km if km is not None else _quantity(e, it["distance_units"])
                minutes = minutes if minutes is not None else _duration(e, it)
    km = km if km is not None else _quantity(text, it["distance_units"])
    minutes = minutes if minutes is not None else _duration(text, it)
    return (km or None), (minutes or None)


def _answer(params=None, clarification=None, rejection=None):
    return s.InterpretResponse(params=params, clarification=clarification, rejection=rejection)


def interpret_text(text, analysis, cfg):
    it, messages = cfg["interpret"], cfg["messages"]
    base = normalize(text)
    extra = [normalize(t) for t in (analysis.phrases + [e[0] for e in analysis.entities])] if analysis else []
    # el texto y lo que aporta OCI se buscan igual; la coma separa trozos para que no se mezclen negaciones
    full = " , ".join([base, *extra])
    tokens = _tokens(full)
    simple = lambda name: {name: {name: it[name]}}
    found = _matches(full, {"activity": it["activities"], "pass_by": it["pass_by"], "avoid": it["avoid"],
                            "avoid_direct": it["avoid_direct"], **simple("one_way"), **simple("out_of_catalog"),
                            **simple("medical")})
    groups = {}
    for start, _, group, value in found:
        negated = _negated(tokens, start, it)
        if group == "avoid" and not negated:
            continue                       # «con cuestas»: no es evitar
        if group == "pass_by" and negated:
            continue                       # «sin pasar por el super»
        groups.setdefault("avoid" if group == "avoid_direct" else group, set()).add(value)
    if "medical" in groups:
        return _answer(rejection=messages["medical"])
    if "out_of_catalog" in groups:
        return _answer(rejection=messages["out_of_catalog"])
    activities = groups.get("activity", set())
    if len(activities) > 1:
        return _answer(clarification=messages["which_activity"])
    km, minutes = _amounts(base, analysis, it)
    if km is None and minutes is None:
        return _answer(clarification=messages["missing_amount"])
    if (km or 0) > it["max_distance_km"] or (minutes or 0) > it["max_duration_min"]:
        return _answer(clarification=messages["too_long"])
    params = s.AssistantParams(
        activity=next(iter(activities)) if activities else it["default_activity"],
        distance_km=None if km is None else round(km, 2),
        duration_min=None if minutes is None or km is not None else max(1, round(minutes)),
        loop="one_way" not in groups,
        pass_by=[p for p in PASS_BY if p in groups.get("pass_by", set())],
        avoid=[a for a in AVOID if a in groups.get("avoid", set())])
    return _answer(params=params)
