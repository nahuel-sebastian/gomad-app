import type { LocationCandidate, LocationResponse } from "../api/types";
import { simulate } from "./mock/delay";
import { locationMock, SAMPLE_GPS } from "./mock/location";

// GET /api/location?text=<texto> (3-200 caracteres)
// paso 3: sustituir por la llamada real a /api/location (no guardar el texto)
export function searchLocation(text: string): Promise<LocationResponse> {
    return simulate(() => locationMock(text));
}

// Ubicacion de «Usar mi ubicacion»
// paso 3: sustituir por el GPS del navegador tras el gesto (sin guardarla)
export function sampleLocation(): LocationCandidate {
    return SAMPLE_GPS;
}

export function isSampleLocation(candidate: LocationCandidate): boolean {
    return candidate.label === SAMPLE_GPS.label;
}
