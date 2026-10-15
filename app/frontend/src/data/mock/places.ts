import type { DestinationSummary } from "../../api/types";

// Destinos FICTICIOS del mundo de ejemplo. Nombres inventados y marcados
// «(ejemplo)»: no son parques ni instalaciones reales.

export interface MockPlace {
    id: string;
    name: string;
    type: DestinationSummary["type"];
    covered: boolean | null;
    // adecuacion 0-1 por actividad (criterio propio, como activities.yaml)
    suitability: Record<string, number>;
    distance_m: number;
    // rumbo desde el origen, en grados, para situarlo en el mapa
    bearing: number;
    // verde 0-10; null = sin datos (fuera del planeamiento)
    green: number | null;
    // resta al aire por estar junto a una avenida
    airPenalty: number;
    playground?: boolean;
    dogArea?: boolean;
    sourceLabel: string;
    sourceId: string;
}

const PARK = { walk: 1, run: 0.8 };

export const PLACES: MockPlace[] = [
    {
        id: "ejemplo:parque-arroyo",
        name: "Parque del Arroyo (ejemplo)",
        type: "park",
        covered: false,
        suitability: PARK,
        distance_m: 1800,
        bearing: 40,
        green: 9,
        airPenalty: 0,
        playground: true,
        sourceLabel: "Parques: EIEL 2023 (IDEM)",
        sourceId: "eiel_parques",
    },
    {
        id: "ejemplo:jardin-plaza-nueva",
        name: "Jardín de la Plaza Nueva (ejemplo)",
        type: "park",
        covered: false,
        suitability: PARK,
        distance_m: 600,
        bearing: 200,
        green: null,
        airPenalty: 2.5,
        sourceLabel: "Parques: Nomecalles",
        sourceId: "nmc_parques",
    },
    {
        id: "ejemplo:pinar-cerros",
        name: "Pinar de los Cerros (ejemplo)",
        type: "trail",
        covered: false,
        suitability: { walk: 1, run: 1 },
        distance_m: 2900,
        bearing: 120,
        green: 9.5,
        airPenalty: 0,
        dogArea: true,
        sourceLabel: "Sendas verdes: IDEM",
        sourceId: "sendas",
    },
    {
        id: "ejemplo:paseo-canal",
        name: "Paseo del Canal (ejemplo)",
        type: "trail",
        covered: false,
        suitability: { walk: 0.9, run: 0.9 },
        distance_m: 1300,
        bearing: 300,
        green: 6,
        airPenalty: 1,
        sourceLabel: "Vías pecuarias: IDEM",
        sourceId: "vias_pecuarias",
    },
    {
        id: "ejemplo:area-la-fuente",
        name: "Área recreativa La Fuente (ejemplo)",
        type: "recreation_area",
        covered: false,
        suitability: { walk: 1, run: 0.7 },
        distance_m: 2500,
        bearing: 80,
        green: 8,
        airPenalty: 0,
        playground: true,
        dogArea: true,
        sourceLabel: "Áreas recreativas: IDEM",
        sourceId: "areas_recreativas",
    },
    {
        id: "ejemplo:parque-moreras",
        name: "Parque Infantil Las Moreras (ejemplo)",
        type: "park",
        covered: false,
        suitability: { walk: 0.9, run: 0.5 },
        distance_m: 1100,
        bearing: 160,
        green: 7,
        airPenalty: 0.5,
        playground: true,
        sourceLabel: "Parques: EIEL 2023 (IDEM)",
        sourceId: "eiel_parques",
    },
    {
        id: "ejemplo:polideportivo-norte",
        name: "Polideportivo Municipal Norte (ejemplo)",
        type: "facility",
        covered: true,
        suitability: { swim: 1, padel: 0.9, basketball: 1, gym: 1 },
        distance_m: 1500,
        bearing: 10,
        green: 3,
        airPenalty: 0,
        sourceLabel: "Instalaciones deportivas: EIEL 2023 (IDEM)",
        sourceId: "eiel_deporte",
    },
    {
        id: "ejemplo:piscina-verano-sur",
        name: "Piscina de Verano Sur (ejemplo)",
        type: "facility",
        covered: false,
        suitability: { swim: 1 },
        distance_m: 2200,
        bearing: 230,
        green: 6,
        airPenalty: 0,
        sourceLabel: "Instalaciones deportivas: Nomecalles",
        sourceId: "nmc_deporte",
    },
    {
        id: "ejemplo:pistas-barrio",
        name: "Pistas Deportivas del Barrio (ejemplo)",
        type: "facility",
        covered: false,
        suitability: { padel: 1, tennis: 1, football: 1, basketball: 0.9, run: 0.6 },
        distance_m: 900,
        bearing: 270,
        green: 2,
        airPenalty: 1.5,
        sourceLabel: "Instalaciones deportivas: OpenStreetMap",
        sourceId: "osm",
    },
    {
        id: "ejemplo:pabellon-encinas",
        name: "Pabellón Las Encinas (ejemplo)",
        type: "facility",
        covered: true,
        suitability: { gym: 1, basketball: 0.9, padel: 0.8, tennis: 0.7, football: 0.6 },
        distance_m: 2600,
        bearing: 330,
        green: null,
        airPenalty: 0,
        sourceLabel: "Instalaciones deportivas: Nomecalles",
        sourceId: "nmc_deporte",
    },
    {
        id: "ejemplo:zona-bano-embalse",
        name: "Zona de baño del Embalse (ejemplo)",
        type: "bathing_area",
        covered: false,
        suitability: { swim: 0.9 },
        distance_m: 2800,
        bearing: 140,
        green: 8,
        airPenalty: 0,
        sourceLabel: "Zonas de baño: Comunidad de Madrid",
        sourceId: "zonas_bano",
    },
    {
        id: "ejemplo:senda-rio",
        name: "Senda del Río (ejemplo)",
        type: "trail",
        covered: false,
        suitability: { walk: 1, run: 1 },
        distance_m: 4500,
        bearing: 60,
        green: 9,
        airPenalty: 0,
        dogArea: true,
        sourceLabel: "Sendas verdes: IDEM",
        sourceId: "sendas",
    },
];
