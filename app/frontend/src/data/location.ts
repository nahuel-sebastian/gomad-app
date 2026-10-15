import type { LocationCandidate, LocationResponse } from "../api/types";
import { locateWithBrowser } from "./geolocation";
import { getJson } from "./http";
import { simulate } from "./mock/delay";
import { locationMock, SAMPLE_GPS } from "./mock/location";
import { sampleDataMode } from "./mode";

// GET /api/location?text=<texto> (3-200 caracteres; el texto no se guarda)
export function searchLocation(text: string): Promise<LocationResponse> {
    if (sampleDataMode()) return simulate(() => locationMock(text));
    return getJson<LocationResponse>(`/location?text=${encodeURIComponent(text)}`);
}

// «Usar mi ubicacion»: GPS real tras el gesto (sin guardarlo). En las pruebas, la de ejemplo;
// en desarrollo, si el GPS falla, tambien (y la pantalla lo dice).
export async function currentLocation(): Promise<LocationCandidate> {
    if (sampleDataMode()) return sampleLocation();
    try {
        return await locateWithBrowser(navigator.geolocation, window.isSecureContext);
    } catch (error) {
        if (import.meta.env.DEV) return sampleLocation();
        throw error;
    }
}

// Ubicacion de ejemplo: solo pruebas y respaldo del GPS en desarrollo
export function sampleLocation(): LocationCandidate {
    return SAMPLE_GPS;
}

export function isSampleLocation(candidate: LocationCandidate): boolean {
    return candidate.label === SAMPLE_GPS.label;
}
