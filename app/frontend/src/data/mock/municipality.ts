import type { Indicator, MunicipalityResponse } from "../../api/types";
import { ApiError } from "../errors";
import { MUNICIPALITIES } from "./municipalities";

// Indicadores INVENTADOS a partir del codigo INE (deterministas). La pantalla
// avisa de que son cifras de ejemplo, no las del municipio.

// Municipios grandes que no estan en la EIEL (no tienen conectividad)
const NOT_IN_EIEL = new Set(["28079", "28065", "28092", "28074", "28005", "28058"]);

function seeded(code: string) {
    let x = Number(code) * 9301 + 49297;
    return () => {
        x = (x * 9301 + 49297) % 233280;
        return x / 233280;
    };
}

const SAMPLE_SOURCE = (label: string, own = false) => ({
    source: "ejemplo",
    label: `${label} (ejemplo)`,
    date: "2026-10-14T04:00:00",
    own_criterion: own,
});

export function municipalityMock(ineCode: string): MunicipalityResponse {
    const item = MUNICIPALITIES.find((m) => m.ine_code === ineCode);
    if (!item) {
        throw new ApiError(404, "No existe ningún municipio con ese código.");
    }
    const rnd = seeded(ineCode);
    const big = ineCode === "28079";
    const scale = big ? 40 : 1;
    const n = (max: number) => Math.round(rnd() * max * scale) + 1;
    const inEiel = !NOT_IN_EIEL.has(ineCode);

    const indicators: Indicator[] = [
        { category: "sport", key: "sport_facilities", label: "Instalaciones deportivas", value: n(30), unit: "instalaciones", year: 2025, source: SAMPLE_SOURCE("Nomecalles") },
        { category: "sport", key: "pools", label: "Piscinas", value: n(4), unit: "piscinas", year: 2023, source: SAMPLE_SOURCE("EIEL 2023") },
        { category: "nature", key: "green_m2_per_inhabitant", label: "Zona verde por habitante", value: big ? null : Math.round(rnd() * 150 + 10), unit: "m²/hab", year: 2025, source: SAMPLE_SOURCE(big ? "Planeamiento 2025 · no cubre este municipio" : "Planeamiento 2025") },
        { category: "nature", key: "parks", label: "Parques", value: n(25), unit: "parques", year: 2025, source: SAMPLE_SOURCE("Nomecalles") },
        { category: "mobility", key: "bus_stops", label: "Paradas de autobús", value: n(80), unit: "paradas", year: 2025, source: SAMPLE_SOURCE("Nomecalles") },
        { category: "mobility", key: "rail_stations", label: "Estaciones de metro y cercanías", value: Math.round(rnd() * 3 * scale), unit: "estaciones", year: 2025, source: SAMPLE_SOURCE("Nomecalles") },
        { category: "health", key: "health_centres", label: "Centros de salud y consultorios", value: n(5), unit: "centros", year: 2026, source: SAMPLE_SOURCE("Comunidad de Madrid") },
        { category: "health", key: "pharmacies", label: "Farmacias", value: n(12), unit: "farmacias", year: 2026, source: SAMPLE_SOURCE("Comunidad de Madrid") },
        { category: "health", key: "aeds", label: "Desfibriladores", value: n(10), unit: "desfibriladores", year: 2026, source: SAMPLE_SOURCE("Comunidad de Madrid") },
        { category: "education", key: "schools", label: "Centros educativos", value: n(20), unit: "centros", year: 2025, source: SAMPLE_SOURCE("Comunidad de Madrid") },
        { category: "connectivity", key: "coverage_4g", label: "Cobertura 4G", value: inEiel ? Math.round(rnd() * 30 + 70) : null, unit: "% de núcleos", year: 2023, source: SAMPLE_SOURCE(inEiel ? "EIEL 2023" : "EIEL 2023 · no cubre este municipio") },
        { category: "social", key: "social_centres", label: "Centros de atención social", value: n(6), unit: "centros", year: 2026, source: SAMPLE_SOURCE("Comunidad de Madrid") },
    ];

    return {
        ine_code: item.ine_code,
        name: item.name,
        population: ineCode === "28001" ? null : Math.round(rnd() * 90000 * scale + 500),
        indicators,
        fit: [
            "Tiene instalaciones donde practicar pádel y nadar (ejemplo).",
            "Hay parques con juegos infantiles cerca del centro (ejemplo).",
            "La conectividad móvil no se conoce en todos los núcleos.",
        ],
    };
}
