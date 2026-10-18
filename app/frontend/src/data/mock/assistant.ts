import type {
    AssistantParams,
    AssistantRouteRequest,
    AssistantRouteResponse,
    Condition,
    InterpretResponse,
    PassBy,
} from "../../api/types";
import { formatDistance } from "../../lib/format";
import { AVOID_LABELS, PASS_BY_LABELS } from "../../lib/labels";
import { routeMock } from "./route";

// Interpretacion de ejemplo con palabras clave (como OCI Language + reglas,
// sin LLM, DEC-03). Solo imita la forma de la respuesta.

const MEDICAL = /m[eé]dic|tensi[oó]n|coraz[oó]n|asma|dolor|enfermedad|lesi[oó]n|medicaci[oó]n|pastilla|diabetes/;
// otra actividad -> como se nombra en el rechazo y si la busca «¿Qué te apetece hacer?» (como assistant.yaml)
const OUT_OF_CATALOG: [RegExp, string, boolean][] = [
    [/\b(nadar|piscina)\b/, "nadar", true],
    [/\bbici/, "montar en bici", false],
    [/\bpatin/, "patinar", false],
    [/\besqu[ií]/, "esquiar", false],
    [/\bescala/, "escalar", false],
];
const WALK_OR_RUN = /corr|running|trot|camin|andar|andando|pase/;
const MISSING_AMOUNT = "Solo falta la distancia o el tiempo: por ejemplo, «5 km» o «45 minutos».";
const NOT_UNDERSTOOD =
    "No he entendido qué ruta buscas. Dime cuánto quieres andar o correr y por dónde; por ejemplo: «5 km andando por un parque con fuentes». También puedes rellenar los campos de abajo.";

const PASS_BY_WORDS: [RegExp, PassBy][] = [
    [/parque/, "park"],
    [/fuente/, "fountain"],
    [/banco/, "bench"],
    [/supermercado|s[uú]per\b|tienda/, "supermarket"],
    [/perro|canina/, "dog_area"],
    [/juegos|columpio|ni[nñ]os/, "playground"],
];

export function interpretMock(text: string): InterpretResponse {
    const t = text.toLowerCase();
    if (MEDICAL.test(t)) {
        return {
            params: null,
            clarification: null,
            rejection:
                "No puedo ayudarte con eso: GoMad no da consejo médico. Consulta a tu centro de salud. Sí puedo prepararte una ruta para caminar o correr.",
        };
    }
    const other = OUT_OF_CATALOG.find(([re]) => re.test(t));
    if (other) {
        const [, name, inRecommender] = other;
        const where = inRecommender ? ` Para buscar dónde ${name}, usa «¿Qué te apetece hacer?» en Mi entorno.` : "";
        return {
            params: null,
            clarification: null,
            rejection: `El asistente no prepara rutas para ${name}: solo para caminar o correr.${where}`,
        };
    }
    const km = /(\d+(?:[.,]\d+)?)\s*(km|kil[oó]metros?)/.exec(t);
    const min = /(\d+)\s*(min|minutos?)/.exec(t);
    const hours = /(\d+(?:[.,]\d+)?)\s*(h|horas?)\b/.exec(t);
    const distance = km ? Number(km[1].replace(",", ".")) : null;
    const duration = min ? Number(min[1]) : hours ? Math.round(Number(hours[1].replace(",", ".")) * 60) : null;
    const params: AssistantParams = {
        activity: /corr|running|trot/.test(t) ? "run" : "walk",
        distance_km: distance !== null ? Math.min(42, distance) : null,
        duration_min: distance === null && duration !== null ? Math.min(480, duration) : null,
        // primero ida y vuelta (gana), despues solo ida; «sin volver» es solo ida.
        // «hasta» con hora («hasta las 9», «hasta la una») no es solo ida (como clock_numbers de assistant.yaml)
        loop: /ida y vuelta|(?<!sin )volver|circular|(?<!sin )vuelta/.test(t)
            ? true
            : !/solo ida|de ida|sin volver|sin vuelta|hasta (?!las? (?:\d|(?:una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)\b))/.test(
                  t,
              ),
        pass_by: PASS_BY_WORDS.filter(([re]) => re.test(t)).map(([, v]) => v),
        avoid: [
            ...(/tr[aá]fico|coches|avenida/.test(t) ? (["traffic"] as const) : []),
            ...(/cuesta|pendiente|subida|llano/.test(t) ? (["hills"] as const) : []),
        ],
    };
    if (distance === null && duration === null) {
        // como el diccionario: sin nada del catalogo, no entendido; si no, lo entendido y que falta la cantidad
        const understood = WALK_OR_RUN.test(t) || params.pass_by.length > 0 || params.avoid.length > 0;
        return understood
            ? { params, clarification: MISSING_AMOUNT, rejection: null }
            : { params: null, clarification: NOT_UNDERSTOOD, rejection: null };
    }
    return { params, clarification: null, rejection: null };
}

export function assistantRouteMock(req: AssistantRouteRequest): AssistantRouteResponse {
    const { params } = req;
    const targetKm =
        params.distance_km ??
        ((params.duration_min ?? 30) / 60) * (params.activity === "run" ? 9 : 4.5);
    // destino de ejemplo a la mitad de la distancia si es circular
    const reach = (params.loop === false ? targetKm : targetKm / 2) * 1000;
    const destination = {
        lat: req.origin.lat + reach / 111320 / 1.4,
        lon: req.origin.lon + reach / 85000 / 1.4,
    };
    const routes = routeMock({ origin: req.origin, destination, profile: "general", weights: null });
    const distanceM = Math.round(targetKm * 1000 * 0.97);
    const route = {
        ...routes.healthy,
        distance_m: distanceM,
        duration_min: Math.round((distanceM / 1000 / (params.activity === "run" ? 9 : 4.5)) * 60),
        description: "",
    };
    route.description = `Ruta ${params.loop === false ? "de ida" : "de ida y vuelta"} de ${formatDistance(distanceM)} (ejemplo).`;

    const conditions: Condition[] = [
        {
            condition: `Distancia de ${formatDistance(targetKm * 1000)} (±10 %)`,
            met: true,
            detail: `${formatDistance(distanceM)}, dentro del margen.`,
        },
        {
            condition: params.loop === false ? "Solo ida" : "Ida y vuelta",
            met: true,
            detail: params.loop === false ? "Termina lejos del punto de salida." : "Vuelve al punto de salida.",
        },
    ];
    for (const p of params.pass_by ?? []) {
        const met = p !== "supermarket";
        conditions.push({
            condition: `Pasar por: ${PASS_BY_LABELS[p].toLowerCase()}`,
            met,
            detail:
                p === "bench"
                    ? "Hay bancos, pero ninguno entre el km 3 y el 5."
                    : met
                      ? "Sí, en el tramo central de la ruta."
                      : "No hay ninguno a menos de 300 m de la ruta.",
        });
    }
    for (const a of params.avoid ?? []) {
        conditions.push({
            condition: `Evitar: ${AVOID_LABELS[a].toLowerCase()}`,
            met: a === "traffic",
            detail: a === "traffic" ? "Solo 80 m junto a tráfico intenso." : "Sin datos de desnivel todavía.",
        });
    }
    if (conditions.every((c) => c.met)) {
        conditions.push({
            condition: "Fuentes en la ruta",
            met: false,
            detail: "No hay fuentes en los últimos 2 km.",
        });
    }
    const failed = conditions.filter((c) => !c.met).length;
    return {
        route,
        conditions,
        explanation: `${route.description} Cumple ${conditions.length - failed} de ${conditions.length} condiciones.`,
        written_by_ai: false,
    };
}
