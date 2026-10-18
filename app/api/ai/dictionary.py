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
                          "negation_breaks", "round_trip", "one_way", "whole_words", "clock_prefixes", "clock_numbers", "out_of_catalog", "out_of_catalog_in_recommender", "medical", "distance_units",
                          "duration_units", "duration_phrases", "quantity_entity_types", "max_distance_km",
                          "max_duration_min", "default_activity"],
            "messages": ["medical", "not_understood", "out_of_catalog", "out_of_catalog_named", "out_of_catalog_where",
                         "missing_amount", "which_activity", "too_long", "understood"],
            "oci": ["timeout_s", "language_code", "cooldown_s"],
            "templates": ["summary", "score", "failed", "join_last"],
            "route": ["search_radius_m", "candidates", "pass_by_radius_m", "default_destination",
                      "avoid_traffic_max_share", "avoid_traffic_weights", "destination_kinds", "poi_kinds", "no_data",
                      "labels", "endings", "texts"]}


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
    if not set(it["out_of_catalog_in_recommender"]) <= set(it["out_of_catalog"]):
        raise ValueError("assistant.yaml: out_of_catalog_in_recommender con actividades que no estan en out_of_catalog")
    understood = cfg["messages"]["understood"]
    missing = {"sentence", "activities", "round_trip", "one_way", "pass_by", "avoid"} - set(understood)
    if missing or set(understood["activities"]) != set(ACTIVITIES):
        raise ValueError(f"assistant.yaml: messages.understood incompleto: {sorted(missing) or 'activities'}")
    r = cfg["route"]
    covered = set(r["destination_kinds"]) | set(r["poi_kinds"]) | set(r["no_data"])
    if covered != set(PASS_BY):
        raise ValueError(f"assistant.yaml: route no cubre cada pasar por: {sorted(set(PASS_BY) ^ covered)}")
    if set(r["labels"]) != set(PASS_BY) | set(AVOID) or not set(r["endings"]) >= covered - set(r["no_data"]):
        raise ValueError("assistant.yaml: faltan etiquetas o finales de route")
    if r["default_destination"] not in r["destination_kinds"]:
        raise ValueError("assistant.yaml: default_destination tiene que ser un destino")


def _tokens(text):
    return [(m.start(), m.group()) for m in re.finditer(r"\w+|[,.;:!?¿¡]", text)]


def _matches(text, groups, whole=()):
    """[(inicio, fin, grupo, valor)] sin solapes: la palabra mas larga gana («parque infantil» frente a «parque»)."""
    found = []
    for group, mapping in groups.items():
        for value, words in mapping.items():
            for word in words:
                tail = r"(?!\w)" if word in whole else r"\w*"
                for m in re.finditer(r"(?<!\w)" + re.escape(normalize(word)) + tail, text):
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


def _clock_at(text, pos, prefixes, before, numbers=()):
    """True si en pos empieza una hora («hasta las 9» o «hasta las nueve», before=False: el prefijo seguido de un
    numero en cifra o en letra de numbers) o si pos va justo detras de un prefijo de hora («a las» 20 h, before=True)."""
    hour = r"\d" + "".join("|" + re.escape(normalize(n)) + r"(?!\w)" for n in numbers)
    for prefix in prefixes:
        p = normalize(prefix)
        if before and re.search(r"(?<!\w)" + re.escape(p) + r"\s*$", text[:pos]):
            return True
        if not before and re.match(re.escape(p) + r"\s*(?:" + hour + ")", text[pos:]):   # no «hasta la fuente»
            return True
    return False


def _quantity(text, units, clock_prefixes=()):
    alternatives = "|".join(sorted((re.escape(u) for u in units), key=len, reverse=True))
    for m in re.finditer(r"(\d+(?:[.,]\d+)?)\s*(" + alternatives + r")(?!\w)", text):
        if _clock_at(text, m.start(), clock_prefixes, before=True):
            continue                         # «a las 20 h»: una hora del dia, no una duracion
        return float(m.group(1).replace(",", ".")) * units[m.group(2)]
    return None


def _duration(text, it):
    for phrase, minutes in sorted(it["duration_phrases"].items(), key=lambda kv: -len(kv[0])):
        if re.search(r"(?<!\w)" + re.escape(normalize(phrase)) + r"(?!\w)", text):
            return float(minutes)
    return _quantity(text, it["duration_units"], it["clock_prefixes"])


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
                            "avoid_direct": it["avoid_direct"], **simple("round_trip"), **simple("one_way"),
                            "out_of_catalog": it["out_of_catalog"], **simple("medical")}, set(it["whole_words"]))
    groups, other = {}, []
    # lo que ya menciona el texto lo decide el texto (con sus negaciones): una frase de OCI suelta («supermercado»
    # de «sin pasar por supermercado») no lo deshace; OCI solo suma valores que el texto no menciona
    in_text = {(group, value) for start, _, group, value in found if start < len(base)}
    for start, _, group, value in found:
        if start >= len(base) and (group, value) in in_text:
            continue
        negated = _negated(tokens, start, it)
        if group == "avoid" and not negated:
            continue                       # «con cuestas»: no es evitar
        if group == "pass_by" and negated:
            continue                       # «sin pasar por el super»
        if group == "one_way" and _clock_at(full, start, it["clock_prefixes"], before=False, numbers=it["clock_numbers"]):
            continue                       # «hasta las 9» o «hasta las nueve»: una hora, no «solo ida»
        if group == "round_trip" and negated:
            group = "one_way"              # «no quiero volver»
        groups.setdefault("avoid" if group == "avoid_direct" else group, set()).add(value)
        if group == "out_of_catalog":
            other.append(value)            # en orden de aparicion: se nombra la primera
    if "medical" in groups:
        return _answer(rejection=messages["medical"])
    if other:
        return _answer(rejection=_out_of_catalog(other[0], it, messages))
    activities = groups.get("activity", set())
    km, minutes = _amounts(base, analysis, it)
    if not groups and km is None and minutes is None:
        return _answer(clarification=messages["not_understood"])
    too_long = (km or 0) > it["max_distance_km"] or (minutes or 0) > it["max_duration_min"]
    if too_long:
        km = minutes = None                # se pide otra cantidad; el resto de lo entendido se conserva
    params = s.AssistantParams(
        activity=next(iter(activities)) if len(activities) == 1 else it["default_activity"],
        distance_km=None if km is None else round(km, 2),
        duration_min=None if minutes is None or km is not None else max(1, round(minutes)),
        loop="round_trip" in groups or "one_way" not in groups,
        pass_by=[p for p in PASS_BY if p in groups.get("pass_by", set())],
        avoid=[a for a in AVOID if a in groups.get("avoid", set())])
    # una sola pregunta cada vez, delante lo que ya se ha apuntado (va tambien en params para el formulario)
    problem = ("which_activity" if len(activities) > 1 else "too_long" if too_long
               else "missing_amount" if km is None and minutes is None else None)
    if problem is None:
        return _answer(params=params)
    return _answer(params=params, clarification=_understood(groups, params, cfg) + messages[problem])


def _out_of_catalog(activity, it, messages):
    """Rechazo que nombra la actividad («Nadar no lo prepara...») y, si la busca el recomendador, donde buscarla."""
    text = messages["out_of_catalog_named"].format(activity=activity[:1].upper() + activity[1:])
    if activity in it["out_of_catalog_in_recommender"]:
        text += messages["out_of_catalog_where"].format(activity=activity)
    return text


def _join(items, cfg):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + cfg["templates"]["join_last"] + items[-1]


def _understood(groups, params, cfg):
    """«He apuntado: caminar, pasar por parque. » con lo que dice el texto; vacio si no dice nada que listar."""
    labels, u = cfg["route"]["labels"], cfg["messages"]["understood"]
    items = []
    if len(groups.get("activity", ())) == 1:
        items.append(u["activities"][params.activity])
    if "round_trip" in groups or "one_way" in groups:
        items.append(u["round_trip"] if params.loop else u["one_way"])
    if params.pass_by:
        items.append(u["pass_by"].format(labels=_join([labels[p] for p in params.pass_by], cfg)))
    if params.avoid:
        items.append(u["avoid"].format(labels=_join([labels[a] for a in params.avoid], cfg)))
    return u["sentence"].format(items=", ".join(items)) if items else ""
