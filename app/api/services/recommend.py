"""POST /recommend (arquitectura §4.2): candidatos -> distancia a pie -> contexto por hora -> reglas -> nota.

Determinista y sin IA. Pesos, umbrales, actividades, velocidades y criterios propios salen de config/."""
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np

import schemas as s
import settings
from engine import explanation as ex
from engine.rules import CATEGORIES, HourContext, is_heat_day, load_heat_zones
from engine.scoring import FACTORS, air_factor, compute_score, normalize_weights, proximity_factor, weather_factor
from engine.slots import best_hour, evaluate_hours, needs_indoor, window_hours
from repository import category_at, haversine_m
from routing.graph import bounded_distances, nearest_nodes
from services.common import data_source, walking_speed_kmh

LOCAL_TZ = ZoneInfo("Europe/Madrid")
MEDICAL_DISCLAIMER = "Recomendación orientativa con datos abiertos. No es consejo médico."
CONFIG = ("activities", "weights", "rules", "ica_thresholds", "recommend", "routing", "sources")


class UnknownActivity(ValueError):
    pass


@dataclass
class Scored:
    cand: object
    distance_m: float
    approximate: bool
    covered: bool
    hours: list
    best: object
    score: float
    fixed: dict
    factors: dict                      # factores del sitio (0-1) con los que se calcula su nota
    indoor_alternative: bool = False
    partial_air: bool = False          # hay medicion de aire solo para parte de la ventana

    @property
    def viable(self):
        return self.best is not None


def _plain(text):
    t = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return " ".join(t.split())


def _same_place(a, b, radius_m, same_name_radius_m):
    """Mismo sitio: mismo id; dos fuentes distintas a menos de radius_m (nombres distintos: «Parque del Buen Retiro»
    y «Jardines de El Buen Retiro»); o el mismo nombre a menos de same_name_radius_m (centroides de parques grandes)."""
    if a.cand.id == b.cand.id:
        return True
    d = float(haversine_m(a.cand.lon, a.cand.lat, b.cand.lon, b.cand.lat))
    if a.cand.source != b.cand.source and d <= radius_m:
        return True
    return _plain(a.cand.name) == _plain(b.cand.name) and d <= same_name_radius_m


def _page(scored, req, radius_m, same_name_radius_m):
    """Pagina sin repetir sitio; en «Sorprendeme», como mucho un resultado por actividad (RF-03)."""
    need = req.offset + req.limit
    kept, activities = [], set()
    for x in scored:
        if req.activity is None and x.cand.activity in activities:
            continue
        if any(_same_place(k, x, radius_m, same_name_radius_m) for k in kept):
            continue
        kept.append(x)
        activities.add(x.cand.activity)
        if len(kept) > need:
            break
    return kept[req.offset:need], len(kept) > need


def _category_of(factor):
    # inversa de air_factor: categoria del ICA a partir del factor 0-1
    return CATEGORIES[round((1 - factor) * (len(CATEGORIES) - 1))]


def _hour(h):
    c = h.ctx
    return s.HourEvaluation(hour=h.hour, score=h.score, outdoor_ok=h.outdoor_ok, reasons=h.reasons,
                            temperature_c=c.temperature_c if c else None, feels_like_c=c.feels_like_c if c else None,
                            precip_prob=c.precip_prob if c else None, aqi_category=c.aqi_category if c else None)


class _Run:
    """Estado de una peticion: contexto cargado una vez y reutilizado por todos los candidatos."""

    def __init__(self, req, repo, graphs, cfg, weights, window):
        self.req, self.repo, self.cfg, self.weights, self.window = req, repo, cfg, weights, window
        self.catalog = {a["id"]: a for a in cfg["activities"]["activities"]}
        self.labels = (cfg["sources"] or {}).get("labels", {})
        self.located = graphs.locate([(req.origin.lon, req.origin.lat)], cfg["routing"]["snap_max_m"])
        self.net = None
        self.forecasts, self.issued, self.loaded = {}, {}, set()
        self.air, self.stations, self.station_of, self.contexts = None, [], {}, {}
        self.dates = repo.source_dates()
        self.names = repo.municipality_names()
        # DEC-06: umbral de calor de la zona meteosalud de cada municipio (heat_zones.csv)
        self.heat = cfg["rules"].get("heat") or {}
        self.zones = load_heat_zones(settings.CONFIG_DIR / self.heat["zone_table"]) if self.heat else {}

    def _distances(self, cands):
        dist = np.array([c.straight_m for c in cands], dtype=float) * self.cfg["recommend"]["straight_line_detour"]
        approx = np.ones(len(cands), dtype=bool)
        if self.located is not None:
            zone, nodes, snaps = self.located
            if self.net is None:
                self.net = bounded_distances(zone.graph, int(nodes[0]), self.req.max_distance_m)
            cn, cd = nearest_nodes(zone.graph, [c.lon for c in cands], [c.lat for c in cands],
                                   self.cfg["routing"]["snap_max_m"])
            ok = cn >= 0
            dist[ok] = self.net[cn[ok]] + cd[ok] + snaps[0]
            approx = ~ok
        return dist, approx

    def _load_context(self, cands):
        if not self.window:
            return
        new = sorted({c.ine_code for c in cands} - self.loaded)
        if new:
            # el dia completo: las horas fuera de la ventana solo sirven para la Tmax del dia (DEC-06)
            by, issued = self.repo.forecast(new, self.window[0].replace(hour=0), self.window[-1].replace(hour=23))
            self.forecasts.update(by)
            self.issued.update(issued)
            self.loaded |= set(new)
        if self.air is None:
            self.air = self.repo.air_categories(self.window[0], self.window[-1], self.cfg["ica_thresholds"],
                                                self.cfg["recommend"]["air_reading_valid_h"])
            self.stations = [st for st in self.repo.stations() if st.id in self.air]
        if self.stations:
            d = haversine_m(np.array([c.lon for c in cands])[:, None], np.array([c.lat for c in cands])[:, None],
                            np.array([st.lon for st in self.stations])[None, :],
                            np.array([st.lat for st in self.stations])[None, :])
            for c, i in zip(cands, d.argmin(axis=1)):
                self.station_of[c.id] = self.stations[int(i)]

    def _hour_contexts(self, c):
        station = self.station_of.get(c.id)
        key = (c.ine_code, station.id if station else None)
        if key not in self.contexts:
            fc = self.forecasts.get(c.ine_code)
            readings = self.air.get(station.id, []) if station else []
            valid_h = self.cfg["recommend"]["air_reading_valid_h"]
            zone = self.heat.get("zones", {}).get(self.zones.get(c.ine_code))
            threshold = zone["max_temp_c"] if zone else None
            out = {}
            for h in self.window:
                f = fc.get(h) if fc else None
                if fc and f is None:
                    continue          # hay prevision del municipio, pero no para esta hora: «Sin prevision»
                temp, feels, prob = f if f else (None, None, None)
                out[h] = HourContext(h, temp, feels, prob, category_at(readings, h, valid_h),
                                     self._day_max(fc, h.date()), threshold)
            self.contexts[key] = out
        return self.contexts[key]

    @staticmethod
    def _day_max(fc, day):
        temps = [v[0] for ts, v in (fc or {}).items() if ts.date() == day and v[0] is not None]
        return max(temps) if temps else None

    def score(self, cands):
        if not cands:
            return []
        dist, approx = self._distances(cands)
        keep = dist <= self.req.max_distance_m
        cands = [c for c, k in zip(cands, keep) if k]
        dist, approx = dist[keep], approx[keep]
        self._load_context(cands)
        out = []
        for c, d, a in zip(cands, dist, approx):
            covered = self.catalog[c.activity].get("outdoor") is False or bool(c.covered)
            fixed = {"proximity": proximity_factor(d, self.req.max_distance_m), "suitability": c.suitability,
                     "green": c.green}
            contexts = self._hour_contexts(c)
            weights = self._comparable_weights(contexts)
            hours = evaluate_hours(contexts, self.window, covered, self.req.profile, self.cfg["rules"], fixed, weights,
                                   self.req.companions)
            best = best_hour(hours, self.heat.get("tiebreak"))
            factors = self._site_factors(fixed, covered, hours, best)
            score = compute_score(factors, self.weights).value
            known = [h.ctx.aqi_category is not None for h in hours if h.ctx is not None]
            out.append(Scored(c, float(d), bool(a), covered, hours, best, score, fixed, factors,
                              partial_air=not covered and any(known) and not all(known)))
        return out

    def _comparable_weights(self, contexts):
        # para elegir la hora, un factor con dato solo en algunas horas no cuenta: si no, la hora sin dato
        # (renormalizada) ganaria a una con dato regular. Las reglas siguen usando el dato donde lo hay, y la nota
        # del sitio lo usa (_site_factors). Si quitarlo deja todos los pesos a 0, se compara con el.
        weights = dict(self.weights)
        for factor, attr in (("air", "aqi_category"), ("weather", "precip_prob")):
            known = [getattr(c, attr) is not None for c in contexts.values()]
            if any(known) and not all(known):
                weights[factor] = 0.0
        return weights if sum(weights.values()) > 0 else dict(self.weights)

    @staticmethod
    def _site_factors(fixed, covered, hours, best):
        """Factores de la nota del sitio: los de la mejor hora; el aire, el de esa hora o la ultima medicion de
        la ventana. Sin hora viable, sin aire ni tiempo (la nota es la del sitio)."""
        if covered or best is None or best.ctx is None:
            return {**fixed, "air": None, "weather": None}
        aqi = best.ctx.aqi_category
        if aqi is None:
            measured = [h.ctx.aqi_category for h in hours if h.ctx is not None and h.ctx.aqi_category is not None]
            aqi = measured[-1] if measured else None
        return {**fixed, "air": air_factor(aqi), "weather": weather_factor(best.ctx.precip_prob)}

    def _own_rule(self, first):
        if first is None or first.outdoor_ok is not False:
            return False
        rules = self.cfg["rules"]
        for r in first.reasons:
            if r.startswith("Lluvia") and (rules.get("rain") or {}).get("own_criterion"):
                return True
            if r.startswith("Día de calor") and (rules.get("heat") or {}).get("own_criterion"):
                return True
            if r.startswith("Calidad del aire") and self.req.profile in (rules.get("air") or {}).get(
                    "own_criterion_profiles", []):
                return True
        return False

    def _sources(self, x):
        c = x.cand
        out = [data_source(c.source, self.labels, self.dates.get(c.source))]
        if c.green is not None and c.source != "vpla_redes":     # el verde sale de VPLA: no repetir la fuente
            out.append(data_source("vpla_redes", self.labels, self.dates.get("vpla_redes")))
        if c.ine_code in self.issued:
            out.append(data_source("aemet", self.labels, self.issued[c.ine_code]))
        station = self.station_of.get(c.id)
        if station and not x.covered:
            sid = "aire_dia" if station.network == "CM" else "ay_aire"
            out.append(s.DataSource(source=sid, label=f"{self.labels.get(sid, sid)} · estación {station.name}",
                                    date=self.air[station.id][-1][0]))
        if self.req.weights is None:
            out.append(data_source("config:weights", self.labels, None,
                                   bool(self.cfg["weights"].get("own_criterion"))))
        if x.approximate:
            detour = ex.fmt_number(self.cfg["recommend"]["straight_line_detour"])
            out.append(s.DataSource(source="config:recommend", label=f"Distancia aproximada: línea recta × {detour}",
                                    date=None, own_criterion=True))
        return out

    def recommendation(self, x, surprise):
        c, req = x.cand, self.req
        duration = x.distance_m / 1000 / walking_speed_kmh(req.profile, self.cfg["weights"]) * 60
        ref = x.best.ctx if x.best else None
        shown = ref or next((h.ctx for h in x.hours if h.ctx is not None), None)
        factors = x.factors
        score = compute_score(factors, self.weights)
        factor_scores = [
            s.FactorScore(factor=f, value=None if factors[f] is None else round(10 * factors[f], 1),
                          weight=round(score.effective_weights.get(f, 0.0), 4),
                          text=ex.factor_text(f, None if factors[f] is None else 10 * factors[f],
                                              distance_m=x.distance_m, green=c.green,
                                              aqi_category=_category_of(factors["air"]) if factors["air"] is not None
                                              else (shown.aqi_category if shown else None),
                                              precip_prob=shown.precip_prob if shown else None, covered=x.covered))
            for f in FACTORS]
        sources = self._sources(x)
        first = x.hours[0] if x.hours else None
        text = ex.explain(ex.ExplanationInput(
            name=c.name, distance_m=x.distance_m, duration_min=duration, score=x.score,
            factors=[(f.factor, f.value, f.weight) for f in factor_scores], first=first, best=x.best,
            indoor_alternative=x.indoor_alternative,
            activity_label=self.catalog[c.activity]["label"] if surprise else None,
            own_criterion_rule=self._own_rule(first),
            sources=[(d.label, d.date) for d in sources if d.source in ("aemet", "aire_dia", "ay_aire")],
            approximate_distance=x.approximate))
        return s.Recommendation(
            destination=s.DestinationSummary(id=c.id, name=c.name, type=c.type, covered=True if x.covered else c.covered,
                                             municipality=self.names.get(c.ine_code, c.ine_code), ine_code=c.ine_code,
                                             coordinate=s.Coordinate(lat=c.lat, lon=c.lon), source=sources[0]),
            distance_m=round(x.distance_m, 1), duration_min=round(duration, 1),
            score=round(min(10.0, max(0.0, x.score)), 2), factors=factor_scores,
            best_hour=x.best.hour if x.best else None, hours=[_hour(h) for h in x.hours],
            indoor_alternative=x.indoor_alternative, explanation=text, sources=sources)

    def warnings(self, picked):
        out = []
        name = lambda x: self.names.get(x.cand.ine_code, x.cand.ine_code)
        no_green = sorted({name(x) for x in picked if x.cand.green is None})
        if no_green:
            out.append(f"Verde: sin datos en {', '.join(no_green)}.")
        if self.window:
            no_fc = sorted({name(x) for x in picked if x.cand.ine_code not in self.forecasts})
            if no_fc:
                out.append(f"Previsión: sin datos para {', '.join(no_fc)}.")
            if any(not x.covered and all(h.ctx is None or h.ctx.aqi_category is None for h in x.hours) for x in picked):
                out.append("Aire: sin medición reciente cerca; la nota no lo tiene en cuenta.")
        if any(x.partial_air for x in picked):
            out.append("Aire: solo hay medición para parte de la ventana; se usa la última para la nota, no para elegir la hora.")
        if not self.heat:
            out.append("Calor: no hay umbral de calor cargado; no se evalúa.")
        elif any(not x.covered and any(h.ctx is not None and is_heat_day(h.ctx) for h in x.hours) for x in picked)                 and not any(r.startswith("Día de calor") for x in picked for h in x.hours for r in h.reasons):
            out.append("Día de calor en tu zona")      # sin perfil de riesgo: solo aviso (con riesgo, va en cada hora)
        if any(x.approximate for x in picked):
            detour = ex.fmt_number(self.cfg["recommend"]["straight_line_detour"])
            out.append(f"Distancias aproximadas donde no hay red peatonal cargada (línea recta × {detour}, criterio propio).")
        return out


def recommend(req, repo, graphs, now=None):
    cfg = {name: settings.load(name) for name in CONFIG}
    catalog = {a["id"] for a in cfg["activities"]["activities"]}
    if req.activity is not None and req.activity not in catalog:
        raise UnknownActivity(f"Actividad desconocida: {req.activity}")
    weights, warnings = normalize_weights(req.weights.model_dump() if req.weights else None,
                                          cfg["weights"]["defaults"])
    window = window_hours(req.window_start, req.window_end, now or datetime.now(LOCAL_TZ))
    if not window:
        warnings.append("La ventana horaria elegida ya ha pasado: elige otra.")
    run = _Run(req, repo, graphs, cfg, weights, window)
    rc = cfg["recommend"]
    activities = [req.activity] if req.activity else [a["id"] for a in cfg["activities"]["activities"]]
    scored = run.score(repo.candidates(req.origin.lon, req.origin.lat, req.max_distance_m, activities, req.setting,
                                       rc["max_candidates"]))
    # solo cuentan los sitios al aire libre con prevision: uno sin datos no impide proponer cubierto (RF-09)
    outdoor = [x for x in scored if not x.covered and x.cand.ine_code in run.forecasts]
    if outdoor and all(needs_indoor(x.hours) for x in outdoor):
        for x in scored:
            x.indoor_alternative = x.covered
        fallback = rc.get("indoor_fallback_activity")
        if req.setting != "outdoor" and not any(x.covered for x in scored) and fallback in catalog:
            extra = run.score(repo.candidates(req.origin.lon, req.origin.lat, req.max_distance_m, [fallback],
                                              "indoor", rc["max_candidates"]))
            for x in extra:
                x.indoor_alternative = True
            scored += extra
        warnings.append("Ahora no se recomienda actividad al aire libre en la ventana elegida: te proponemos sitios cubiertos."
                        if any(x.covered for x in scored) else
                        "Ahora no se recomienda actividad al aire libre en la ventana elegida: prueba otra franja.")
    scored.sort(key=lambda x: (not x.viable, -x.score, x.distance_m))
    picked, has_more = _page(scored, req, rc["dedupe_radius_m"], rc["same_name_radius_m"])
    results = [run.recommendation(x, surprise=req.activity is None) for x in picked]
    warnings += run.warnings(picked)
    if not scored:
        warnings.append(f"No hay destinos para esta actividad a menos de {ex.fmt_distance(req.max_distance_m)}.")
    return s.RecommendResponse(results=results, has_more=has_more, warnings=list(dict.fromkeys(warnings)),
                               medical_disclaimer=MEDICAL_DISCLAIMER)
