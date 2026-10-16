import type {
    AqiCategory,
    DataSource,
    FactorScore,
    HourEvaluation,
    Profile,
    Recommendation,
    RecommendRequest,
    RecommendResponse,
    Weights,
} from "../../api/types";
import { formatDistance, formatHour, formatMinutes } from "../../lib/format";
import { aqiLabel } from "../../lib/labels";
import { ApiError } from "../errors";
import { ACTIVITIES_MOCK } from "./activities";
import { PLACES, type MockPlace } from "./places";
import { getMockScenario, type MockHour } from "./scenario";

// Motor de juguete para los datos de ejemplo. NO es el motor real: solo
// imita la forma de la respuesta y reacciona a pesos, perfil y filtros.

export const MEDICAL_DISCLAIMER =
    "Recomendación orientativa con datos abiertos. No es consejo médico.";

const AQI_VALUE: Record<AqiCategory, number> = {
    good: 10,
    fair: 8,
    moderate: 6,
    poor: 3.5,
    very_poor: 1.5,
    extremely_poor: 0.5,
};

const AQI_RANK: Record<AqiCategory, number> = {
    good: 0,
    fair: 1,
    moderate: 2,
    poor: 3,
    very_poor: 4,
    extremely_poor: 5,
};

// Recomendaciones literales del BOE (umbrales.md §1.4), por grupo
const BOE_RISK: Partial<Record<AqiCategory, string>> = {
    moderate:
        "Considera reducir las actividades prolongadas y enérgicas al aire libre.",
    poor: "Considera reducir las actividades al aire libre, y realizarlas en el interior o posponerlas para cuando la calidad del aire sea buena o razonablemente buena.",
};
const BOE_GENERAL: Partial<Record<AqiCategory, string>> = {
    poor: "Considera reducir las actividades prolongadas y enérgicas al aire libre, especialmente si experimentas tos, falta de aire o irritación de garganta.",
};

// Calor: umbral de criterio propio hasta DEC-06
const HEAT_LIMIT_C = 33;

const SPEED_KMH: Record<string, number> = { walk: 4.5, run: 9 };

const round1 = (n: number) => Math.round(n * 10) / 10;
const clamp10 = (n: number) => Math.min(10, Math.max(0, n));

function isRiskGroup(profile: Profile) {
    return profile === "sensitive" || profile === "senior";
}

// Aire malo para el perfil: grupos de riesgo desde «Regular», resto desde «Desfavorable»
function airBadFor(aqi: AqiCategory | null, profile: Profile) {
    if (!aqi) return false;
    return AQI_RANK[aqi] >= (isRiskGroup(profile) ? 2 : 3);
}

function generatedHours(start: string, count: number): MockHour[] {
    const base = new Date(`${start.slice(0, 13)}:00:00`);
    const temps = [22, 22, 21, 20, 19, 18, 17, 16, 15, 15, 14, 14];
    return Array.from({ length: count }, (_, i) => {
        const d = new Date(base.getTime() + i * 3600_000);
        const pad = (n: number) => String(n).padStart(2, "0");
        const hour = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00:00`;
        return {
            hour,
            temperature: temps[i % temps.length],
            feelsLike: temps[i % temps.length],
            precipProb: i === 2 ? null : 5,
            aqi: i === 0 ? "fair" : "good",
        };
    });
}

function weatherValue(h: MockHour): number | null {
    if (h.temperature === null) return null;
    const t = h.temperature;
    let v = 10;
    if (t >= HEAT_LIMIT_C) v = 1;
    else if (t >= 28) v = 5;
    else if (t > 24) v = 8;
    else if (t < 5) v = 4;
    if (h.precipProb !== null && h.precipProb >= 50) v = Math.min(v, 3);
    return v;
}

function outdoorOk(h: MockHour, profile: Profile): boolean | null {
    if (h.temperature === null && h.aqi === null) return null;
    if (h.temperature !== null && h.temperature >= HEAT_LIMIT_C) return false;
    if (h.precipProb !== null && h.precipProb >= 50) return false;
    return !airBadFor(h.aqi, profile);
}

function reasonsFor(h: MockHour, profile: Profile): string[] {
    const reasons: string[] = [];
    if (h.temperature !== null && h.temperature >= HEAT_LIMIT_C) {
        reasons.push(
            `Calor extremo: ${h.temperature} °C (sensación ${h.feelsLike ?? h.temperature} °C).`,
        );
    }
    if (h.precipProb !== null && h.precipProb >= 50) {
        reasons.push(`Probabilidad de lluvia del ${h.precipProb} %.`);
    }
    if (h.aqi && AQI_RANK[h.aqi] >= 2) {
        const note = h.airNote ? ` por ${h.airNote}` : "";
        reasons.push(`Calidad del aire ${aqiLabel(h.aqi).toLowerCase()}${note}.`);
        const boe = isRiskGroup(profile) ? BOE_RISK[h.aqi] : BOE_GENERAL[h.aqi];
        if (boe) reasons.push(`Recomendación oficial (BOE): ${boe}`);
    }
    if (reasons.length === 0) {
        reasons.push(
            h.temperature !== null
                ? `Buenas condiciones: ${h.temperature} °C.`
                : "Sin datos de previsión para esta hora.",
        );
    }
    return reasons;
}

interface Context {
    req: RecommendRequest;
    activity: string;
    weights: Weights;
    hours: MockHour[];
    asAlternative: boolean;
}

function factorsFor(place: MockPlace, h: MockHour, ctx: Context): FactorScore[] {
    const { req, activity, weights } = ctx;
    const profile = req.profile ?? "general";
    const companions = req.companions ?? [];
    const covered = place.covered === true;

    const proximity = round1(clamp10(10 * (1 - (0.9 * place.distance_m) / req.max_distance_m)));

    let suit = (place.suitability[activity] ?? 0.6) * 10;
    const extras: string[] = [];
    if (companions.includes("kids") && place.playground) {
        suit += 1;
        extras.push("tiene juegos infantiles");
    }
    if (companions.includes("dog") && place.dogArea) {
        suit += 1;
        extras.push("tiene área canina");
    }
    if (profile === "stroller" && place.type === "trail") {
        suit -= 2;
        extras.push("camino de tierra, peor con carrito");
    }
    const activityLabel =
        ACTIVITIES_MOCK.activities.find((a) => a.id === activity)?.label ?? activity;

    let air: number | null;
    let airText: string;
    if (covered) {
        air = 9;
        airText = "Instalación cubierta: no depende del aire exterior.";
    } else if (h.aqi === null) {
        air = null;
        airText = "Sin datos de aire en esta hora (no cuenta en la nota).";
    } else {
        let v = AQI_VALUE[h.aqi] - place.airPenalty;
        if (profile === "sensitive" && AQI_RANK[h.aqi] >= 2) v -= 2;
        air = round1(clamp10(v));
        airText = `Aire ${aqiLabel(h.aqi).toLowerCase()}${place.airPenalty >= 2 ? ", junto a una avenida" : ""}.`;
    }

    let weather: number | null;
    let weatherText: string;
    if (covered) {
        weather = 9;
        weatherText = "A cubierto: no depende del tiempo.";
    } else {
        weather = weatherValue(h);
        weatherText =
            weather === null
                ? "Sin datos de previsión (no cuenta en la nota)."
                : `${h.temperature} °C${h.precipProb !== null ? `, ${h.precipProb} % de lluvia` : ""}.`;
    }

    const minutes = minutesFor(place, activity, profile);

    return [
        {
            factor: "proximity",
            value: proximity,
            weight: weights.proximity,
            text: `A ${formatDistance(place.distance_m)} (${formatMinutes(minutes)}).`,
        },
        {
            factor: "suitability",
            value: round1(clamp10(suit)),
            weight: weights.suitability,
            text: `${ctx.asAlternative ? "Alternativa cubierta" : `Apto para ${activityLabel.toLowerCase()}`}${extras.length ? `; ${extras.join(", ")}` : ""}.`,
        },
        {
            factor: "green",
            value: place.green,
            weight: weights.green,
            text:
                place.green === null
                    ? "Sin datos de zona verde (no cuenta en la nota)."
                    : place.green >= 8
                      ? "Mucha zona verde y sombra."
                      : place.green >= 5
                        ? "Algo de zona verde."
                        : "Poca zona verde.",
        },
        { factor: "air", value: air, weight: weights.air, text: airText },
        { factor: "weather", value: weather, weight: weights.weather, text: weatherText },
    ];
}

function scoreOf(factors: FactorScore[]): number {
    let sum = 0;
    let total = 0;
    for (const f of factors) {
        if (f.value === null) continue;
        sum += f.value * f.weight;
        total += f.weight;
    }
    return total === 0 ? 0 : round1(sum / total);
}

function minutesFor(place: MockPlace, activity: string, profile: Profile) {
    const slow = profile === "senior" || profile === "stroller";
    const speed = slow ? 3.5 : (SPEED_KMH[activity] ?? 4.5);
    return Math.round((place.distance_m / 1000 / speed) * 60);
}

function coordinateFrom(origin: RecommendRequest["origin"], place: MockPlace) {
    const rad = (place.bearing * Math.PI) / 180;
    const dLat = (place.distance_m * Math.cos(rad)) / 111320;
    const dLon =
        (place.distance_m * Math.sin(rad)) /
        (111320 * Math.cos((origin.lat * Math.PI) / 180));
    return {
        lat: Math.round((origin.lat + dLat) * 1e5) / 1e5,
        lon: Math.round((origin.lon + dLon) * 1e5) / 1e5,
    };
}

function build(place: MockPlace, ctx: Context, sampleDate: string): Recommendation {
    const profile = ctx.req.profile ?? "general";
    const covered = place.covered === true;
    const hours: HourEvaluation[] = ctx.hours.map((h) => {
        const factors = factorsFor(place, h, ctx);
        return {
            hour: h.hour,
            score: h.temperature === null && h.aqi === null ? null : scoreOf(factors),
            outdoor_ok: outdoorOk(h, profile),
            reasons: reasonsFor(h, profile),
            temperature_c: h.temperature,
            feels_like_c: h.feelsLike,
            precip_prob: h.precipProb,
            aqi_category: h.aqi,
        };
    });
    // la mejor hora: la de mayor nota (la primera si empatan)
    let bestIndex = 0;
    hours.forEach((h, i) => {
        if ((h.score ?? -1) > (hours[bestIndex].score ?? -1)) bestIndex = i;
    });
    const best = ctx.hours[bestIndex];
    const factors = factorsFor(place, best, ctx);
    const score = scoreOf(factors);
    const nowBad = hours[0].outdoor_ok === false;
    const indoorAlternative = covered && nowBad;

    let explanation: string;
    if (indoorAlternative) {
        explanation =
            "Alternativa cubierta: puedes ir ahora aunque fuera haga calor, llueva o el aire no sea bueno.";
    } else if (!covered && nowBad && bestIndex > 0) {
        explanation = `Ahora no: ${hours[0].reasons[0].replace(/\.$/, "").toLowerCase()}. Mejor a las ${formatHour(best.hour)}.`;
    } else {
        const green = factors.find((f) => f.factor === "green")!;
        explanation = `Está a ${formatDistance(place.distance_m)}; ${green.text.toLowerCase().replace(/\.$/, "")} y ${factors.find((f) => f.factor === "air")!.text.toLowerCase()}`;
    }
    const suitText = factors.find((f) => f.factor === "suitability")!.text;
    if (suitText.includes(";")) {
        explanation += ` ${suitText.split("; ")[1].replace(/^./, (c) => c.toUpperCase())}`;
    }

    const sources: DataSource[] = [
        { source: place.sourceId, label: place.sourceLabel, date: "2026-10-14T04:00:00", own_criterion: false },
        { source: "open_meteo", label: "Previsión horaria (Open-Meteo)", date: sampleDate, own_criterion: false },
        {
            source: "aire_dia",
            label: "Aire: Comunidad de Madrid (estación más cercana)",
            date: sampleDate,
            own_criterion: false,
        },
        { source: "vpla_redes", label: "Zona verde: planeamiento 2025 (IDEM)", date: null, own_criterion: false },
        { source: "weights", label: "Pesos de la nota y umbral de calor", date: null, own_criterion: true },
    ];

    return {
        destination: {
            id: place.id,
            name: place.name,
            type: place.type,
            covered: place.covered,
            municipality: "Getafe",
            ine_code: "28065",
            coordinate: coordinateFrom(ctx.req.origin, place),
            source: sources[0],
        },
        distance_m: place.distance_m,
        duration_min: minutesFor(place, ctx.activity, profile),
        score,
        factors,
        best_hour: hours[bestIndex].score === null ? null : best.hour,
        hours,
        indoor_alternative: indoorAlternative,
        explanation,
        sources,
    };
}

function isZero(w: Weights) {
    return Object.values(w).every((v) => v === 0);
}

export function recommendMock(req: RecommendRequest): RecommendResponse {
    if (req.window_end <= req.window_start) {
        throw new ApiError(422, "La ventana horaria no es válida.");
    }
    const scenario = getMockScenario();
    const warnings = [...scenario.warnings];
    let weights = req.weights ?? ACTIVITIES_MOCK.default_weights;
    if (isZero(weights)) {
        weights = ACTIVITIES_MOCK.default_weights;
        warnings.push("Todos los pesos estaban a 0: se usan los pesos por defecto.");
    }
    const windowHours = Math.max(
        1,
        Math.min(12, Math.round((Date.parse(req.window_end) - Date.parse(req.window_start)) / 3600_000)),
    );
    const hours = scenario.hours ?? generatedHours(req.window_start, Math.max(3, windowHours));
    const setting = req.setting ?? "any";
    const sampleDate = hours[0].hour;

    const inRange = PLACES.filter((p) => p.distance_m <= req.max_distance_m).filter((p) =>
        setting === "outdoor" ? p.covered !== true : setting === "indoor" ? p.covered === true : true,
    );

    let ranked: Recommendation[];
    if (req.activity === null || req.activity === undefined) {
        // «Sorprendeme»: cada sitio con su mejor actividad; primero uno por tipo
        const all = inRange
            .map((p) => {
                const activity = Object.entries(p.suitability).sort((a, b) => b[1] - a[1])[0][0];
                return build(p, { req, activity, weights, hours, asAlternative: false }, sampleDate);
            })
            .sort((a, b) => b.score - a.score);
        const seen = new Set<string>();
        const firsts: Recommendation[] = [];
        const rest: Recommendation[] = [];
        for (const r of all) {
            if (!seen.has(r.destination.type) && firsts.length < 3) {
                seen.add(r.destination.type);
                firsts.push(r);
            } else {
                rest.push(r);
            }
        }
        ranked = [...firsts, ...rest];
    } else {
        const activity = req.activity;
        ranked = inRange
            .filter((p) => p.suitability[activity] !== undefined)
            .map((p) => build(p, { req, activity, weights, hours, asAlternative: false }, sampleDate))
            .sort((a, b) => b.score - a.score);
        // RF-09: con mal tiempo ahora, se ofrece la mejor alternativa cubierta
        const profile = req.profile ?? "general";
        if (setting !== "outdoor" && outdoorOk(hours[0], profile) === false && !ranked.some((r) => r.indoor_alternative)) {
            const covered = inRange.find((p) => p.covered === true);
            if (covered) {
                const alt = build(covered, { req, activity, weights, hours, asAlternative: true }, sampleDate);
                ranked.splice(1, 0, alt);
            }
        }
    }

    const offset = req.offset ?? 0;
    const limit = req.limit ?? 3;
    return {
        results: ranked.slice(offset, offset + limit),
        has_more: ranked.length > offset + limit,
        warnings: ranked.length === 0 ? [] : warnings,
        medical_disclaimer: MEDICAL_DISCLAIMER,
    };
}
