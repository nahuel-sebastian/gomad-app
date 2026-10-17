import type { LocationCandidate } from "../api/types";
import { MUNICIPALITIES, type MunicipalityItem } from "./mock/municipalities";

// «Usar mi ubicacion» (RF-01): GPS del navegador tras el gesto; la posicion no se guarda en ningun sitio.
export const LOCATION_MESSAGES = {
    insecure:
        "Tu navegador solo comparte la ubicación en páginas seguras (HTTPS). Escribe una dirección o un municipio.",
    denied: "No has dado permiso para usar tu ubicación. Escribe una dirección o un municipio.",
    unavailable: "No hemos podido saber dónde estás. Escribe una dirección o un municipio.",
    outside:
        "Tu ubicación está fuera de la Comunidad de Madrid. Escribe una dirección o un municipio de la Comunidad.",
};

// etiqueta de la ubicacion tomada del GPS (la usa el mapa para seguirla en tiempo real)
export const BROWSER_LOCATION_LABEL = "Tu ubicación";

export class LocationError extends Error {}

type Ring = [number, number][];

function inRing(lon: number, lat: number, ring: Ring): boolean {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
        const [xi, yi] = ring[i];
        const [xj, yj] = ring[j];
        if (yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
}

// Municipio cuyo contorno (simplificado, scripts/municipality_shapes.py) contiene el punto; null si ninguno.
// Los contornos (~220 KB) se cargan solo la primera vez que alguien pulsa «Usar mi ubicacion».
export async function municipalityAt(lat: number, lon: number): Promise<MunicipalityItem | null> {
    const shapes = (await import("./municipalityShapes.json")).default as unknown as Record<string, Ring[]>;
    for (const [ine, polygons] of Object.entries(shapes)) {
        if (polygons.some((ring) => inRing(lon, lat, ring))) {
            return MUNICIPALITIES.find((m) => m.ine_code === ine) ?? null;
        }
    }
    return null;
}

function currentPosition(geo: Geolocation, timeoutMs: number): Promise<GeolocationPosition> {
    return new Promise((resolve, reject) =>
        geo.getCurrentPosition(resolve, reject, { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: 60_000 }),
    );
}

export async function locateWithBrowser(
    geo: Geolocation | undefined,
    secure: boolean,
    timeoutMs = 10_000,
): Promise<LocationCandidate> {
    if (!secure) throw new LocationError(LOCATION_MESSAGES.insecure);
    if (!geo) throw new LocationError(LOCATION_MESSAGES.unavailable);
    let position: GeolocationPosition;
    try {
        position = await currentPosition(geo, timeoutMs);
    } catch (error) {
        const denied = (error as GeolocationPositionError | undefined)?.code === 1;
        throw new LocationError(denied ? LOCATION_MESSAGES.denied : LOCATION_MESSAGES.unavailable);
    }
    const { latitude: lat, longitude: lon } = position.coords;
    const municipality = await municipalityAt(lat, lon);
    if (!municipality) throw new LocationError(LOCATION_MESSAGES.outside);
    return {
        label: BROWSER_LOCATION_LABEL,
        municipality: municipality.name,
        ine_code: municipality.ine_code,
        coordinate: { lat, lon },
        precision: "address",
    };
}
