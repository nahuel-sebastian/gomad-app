import type { AqiCategory, Companion, Profile } from "../../api/types";

// Escenarios de las personas de la demo (CLAUDE.md §5.2). Solo existen en
// el paso 1: cambian las condiciones del «mundo de ejemplo».

export type ScenarioId = "neutral" | "carmen" | "lucia" | "dani" | "ana" | "family";

// Condiciones de una hora del mundo de ejemplo
export interface MockHour {
    hour: string;
    temperature: number | null;
    feelsLike: number | null;
    precipProb: number | null;
    aqi: AqiCategory | null;
    // motivo principal del aire (p. ej. ozono)
    airNote?: string;
}

export interface ScenarioInfo {
    id: ScenarioId;
    label: string;
    description: string;
    // ajustes que se aplican al elegirlo
    preset: {
        profile: Profile;
        companions: Companion[];
        activity: string | null;
        // municipio de la ubicacion de ejemplo
        ine_code: string;
        // pantalla a la que conviene ir
        path: string;
    };
    // null = horas generadas desde la ventana pedida
    hours: MockHour[] | null;
    routeApproximate: boolean;
    warnings: string[];
}

export const SCENARIOS: ScenarioInfo[] = [
    {
        id: "neutral",
        label: "Día normal (por defecto)",
        description:
            "22 °C y aire razonablemente bueno. Mueve los pesos para ver «dos personas, mismo sitio, distinta respuesta».",
        preset: {
            profile: "general",
            companions: [],
            activity: "walk",
            ine_code: "28065",
            path: "/",
        },
        hours: null,
        routeApproximate: false,
        warnings: [
            "Zona verde: sin datos para algún destino (el planeamiento no lo cubre).",
        ],
    },
    {
        id: "carmen",
        label: "Carmen, 72 años: calor",
        description:
            "Julio, 36 °C a media tarde. «Ahora no: mejor a las 20:30», con alternativa cubierta.",
        preset: {
            profile: "senior",
            companions: [],
            activity: "walk",
            ine_code: "28065",
            path: "/resultados",
        },
        hours: [
            { hour: "2026-07-15T17:30:00", temperature: 36, feelsLike: 38, precipProb: 0, aqi: "fair" },
            { hour: "2026-07-15T18:30:00", temperature: 35, feelsLike: 37, precipProb: 0, aqi: "fair" },
            { hour: "2026-07-15T19:30:00", temperature: 32, feelsLike: 33, precipProb: 0, aqi: "fair" },
            { hour: "2026-07-15T20:30:00", temperature: 27, feelsLike: 27, precipProb: 0, aqi: "good" },
            { hour: "2026-07-15T21:30:00", temperature: 25, feelsLike: 25, precipProb: null, aqi: "fair" },
        ],
        routeApproximate: false,
        warnings: [
            "Calor: umbral de criterio propio mientras se fija el oficial (DEC-06).",
        ],
    },
    {
        id: "lucia",
        label: "Lucía, 28 años: ozono",
        description:
            "Corredora sensible a la contaminación. Ozono alto por la tarde; mejor mañana temprano.",
        preset: {
            profile: "sensitive",
            companions: [],
            activity: "run",
            ine_code: "28065",
            path: "/resultados",
        },
        hours: [
            { hour: "2026-10-15T18:00:00", temperature: 27, feelsLike: 27, precipProb: 0, aqi: "poor", airNote: "ozono" },
            { hour: "2026-10-15T19:00:00", temperature: 25, feelsLike: 25, precipProb: 0, aqi: "moderate", airNote: "ozono" },
            { hour: "2026-10-15T20:00:00", temperature: 23, feelsLike: 23, precipProb: 0, aqi: "moderate", airNote: "ozono" },
            { hour: "2026-10-16T07:00:00", temperature: 14, feelsLike: 13, precipProb: 5, aqi: "good" },
            { hour: "2026-10-16T08:00:00", temperature: 15, feelsLike: 15, precipProb: 5, aqi: "fair" },
        ],
        routeApproximate: false,
        warnings: [
            "Aire: último dato válido de las 17:00 (la estación no ha enviado la última hora).",
        ],
    },
    {
        id: "dani",
        label: "Dani y su hija, con carrito",
        description:
            "Parque con juegos infantiles y ruta sin vías rápidas.",
        preset: {
            profile: "stroller",
            companions: ["kids"],
            activity: "walk",
            ine_code: "28065",
            path: "/resultados",
        },
        hours: null,
        routeApproximate: false,
        warnings: [],
    },
    {
        id: "ana",
        label: "Ana y su perro",
        description: "Área canina, fuentes y papeleras en la ruta.",
        preset: {
            profile: "general",
            companions: ["dog"],
            activity: "walk",
            ine_code: "28065",
            path: "/resultados",
        },
        hours: null,
        routeApproximate: false,
        warnings: [],
    },
    {
        id: "family",
        label: "Familia que se muda",
        description:
            "Mira qué ofrece un municipio (San Lorenzo de El Escorial), sin rankings.",
        preset: {
            profile: "general",
            companions: ["kids"],
            activity: null,
            ine_code: "28131",
            path: "/municipios/28131",
        },
        hours: null,
        routeApproximate: true,
        warnings: [],
    },
];

let current: ScenarioId = "neutral";

export function setMockScenario(id: ScenarioId) {
    current = id;
}

export function getMockScenario(): ScenarioInfo {
    return SCENARIOS.find((s) => s.id === current) ?? SCENARIOS[0];
}
