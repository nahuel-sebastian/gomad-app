import type {
    AqiCategory,
    Avoid,
    Companion,
    DestinationSummary,
    Factor,
    IndicatorCategory,
    PassBy,
    PoiType,
    Profile,
    Setting,
} from "../api/types";

// Textos en espanol de los valores del contrato

// Categorias oficiales del ICA (BOE-A-2020-10426, umbrales.md §1.3)
const AQI_LABELS: Record<AqiCategory, string> = {
    good: "Buena",
    fair: "Razonablemente buena",
    moderate: "Regular",
    poor: "Desfavorable",
    very_poor: "Muy desfavorable",
    extremely_poor: "Extremadamente desfavorable",
};

export function aqiLabel(category: AqiCategory | null): string {
    return category ? AQI_LABELS[category] : "Sin datos";
}

// Nivel de cada categoria del ICA en la escala de 6
export const AQI_LEVEL: Record<AqiCategory, number> = {
    good: 1,
    fair: 2,
    moderate: 3,
    poor: 4,
    very_poor: 5,
    extremely_poor: 6,
};
export const AQI_LEVELS = 6;

export const DESTINATION_TYPE_LABELS: Record<DestinationSummary["type"], string> = {
    facility: "Instalación deportiva",
    park: "Parque",
    recreation_area: "Área recreativa",
    trail: "Senda",
    bathing_area: "Zona de baño",
};

export const FACTOR_LABELS: Record<Factor, string> = {
    proximity: "Cercanía y rapidez",
    suitability: "Adecuación a la actividad",
    green: "Sombra y zona verde",
    air: "Aire limpio",
    weather: "Meteorología",
};

export const PROFILE_LABELS: Record<Profile, string> = {
    general: "General",
    senior: "Persona mayor",
    stroller: "Familia con carrito",
    sensitive: "Sensible a la contaminación",
};

export const COMPANION_LABELS: Record<Companion, string> = {
    dog: "Con perro",
    kids: "Con niños",
};

export const SETTING_LABELS: Record<Setting, string> = {
    any: "Cualquiera",
    outdoor: "Exterior",
    indoor: "Interior",
};

export const POI_LABELS: Record<PoiType, { one: string; many: string }> = {
    fountain: { one: "fuente", many: "fuentes" },
    bench: { one: "banco", many: "bancos" },
    bin: { one: "papelera", many: "papeleras" },
    toilet: { one: "aseo", many: "aseos" },
    dog_area: { one: "área canina", many: "áreas caninas" },
    playground: { one: "zona de juegos", many: "zonas de juegos" },
    aed: { one: "desfibrilador", many: "desfibriladores" },
    outdoor_gym: { one: "aparato biosaludable", many: "aparatos biosaludables" },
    supermarket: { one: "supermercado", many: "supermercados" },
};

export function poiCount(type: PoiType, count: number): string {
    const label = POI_LABELS[type];
    return `${count} ${count === 1 ? label.one : label.many}`;
}

export const CATEGORY_LABELS: Record<IndicatorCategory, string> = {
    sport: "Deporte",
    nature: "Naturaleza",
    mobility: "Movilidad",
    health: "Salud",
    education: "Educación",
    connectivity: "Conectividad",
    social: "Servicios sociales",
};

export const PASS_BY_LABELS: Record<PassBy, string> = {
    park: "Parque",
    fountain: "Fuentes",
    bench: "Bancos",
    supermarket: "Supermercado",
    dog_area: "Área canina",
    playground: "Juegos infantiles",
};

export const AVOID_LABELS: Record<Avoid, string> = {
    traffic: "Tráfico",
    hills: "Cuestas",
};

// Veredicto en texto a partir de la nota (P-02: criterio propio del front)
export const VERDICT_THRESHOLDS = { veryGood: 8, good: 6.5 };

export type Tone = "good" | "warn" | "bad" | "nodata";

export function verdictFor(score: number): { text: string; tone: Tone } {
    if (score >= VERDICT_THRESHOLDS.veryGood) {
        return { text: "Muy buena opción", tone: "good" };
    }
    if (score >= VERDICT_THRESHOLDS.good) {
        return { text: "Buena opción", tone: "good" };
    }
    return { text: "Opción aceptable", tone: "warn" };
}
