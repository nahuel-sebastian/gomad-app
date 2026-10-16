import type { SourcesResponse } from "../../api/types";

// Fuentes de ejemplo con las licencias reales de cada portal (CLAUDE.md §2.11);
// las fechas son de ejemplo, relativas a ahora.

function ago(minutes: number): string {
    const d = new Date(Date.now() - minutes * 60000);
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function sourcesMock(): SourcesResponse {
    return {
        sources: [
            {
                id: "aire_dia",
                name: "Calidad del aire: datos del día",
                publisher: "Comunidad de Madrid",
                license: "CC BY 4.0",
                url: "https://datos.comunidad.madrid/dataset/calidad_aire_datos_dia",
                last_refresh: ago(12),
                last_failure: null,
            },
            {
                id: "aemet",
                name: "Predicción horaria por municipio",
                publisher: "AEMET",
                license: "Aviso legal de AEMET (reutilización con cita de la fuente)",
                url: "https://opendata.aemet.es/centrodedescargas/inicio",
                last_refresh: ago(70),
                last_failure: ago(10),
            },
            {
                id: "eiel_deporte",
                name: "EIEL 2023: instalaciones deportivas y parques",
                publisher: "Comunidad de Madrid (IDEM)",
                license: "CC BY 4.0",
                url: "https://www.comunidad.madrid/servicios/mapas/geoportal-comunidad-madrid",
                last_refresh: ago(60 * 24 * 9),
                last_failure: null,
            },
            {
                id: "nmc_deporte",
                name: "Nomecalles: deporte, parques y transporte",
                publisher: "Instituto de Estadística de la Comunidad de Madrid",
                license: "CC BY 4.0",
                url: "https://gestiona.comunidad.madrid/nomecalles_web/",
                last_refresh: ago(60 * 11),
                last_failure: null,
            },
            {
                id: "ay_aire",
                name: "Calidad del aire en tiempo real (Madrid capital)",
                publisher: "Ayuntamiento de Madrid",
                license: "CC BY 4.0",
                url: "https://datos.madrid.es/dataset/212531-0-calidad-aire-tiempo-real",
                last_refresh: ago(25),
                last_failure: null,
            },
            {
                id: "osm",
                name: "Red peatonal y mobiliario urbano",
                publisher: "OpenStreetMap (extracto de Geofabrik)",
                license: "ODbL 1.0 · © colaboradores de OpenStreetMap",
                url: "https://www.openstreetmap.org/copyright",
                last_refresh: ago(60 * 24 * 3),
                last_failure: null,
            },
            {
                id: "mdt05",
                name: "Modelo digital del terreno MDT05 (desnivel)",
                publisher: "Instituto Geográfico Nacional",
                license: "CC BY 4.0 · © Instituto Geográfico Nacional",
                url: "https://www.ign.es",
                last_refresh: null,
                last_failure: null,
            },
        ],
    };
}
