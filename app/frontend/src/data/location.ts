import type { LocationResponse } from "../api/types";
import { simulate } from "./mock/delay";
import { locationMock } from "./mock/location";

// GET /api/location?text=<texto> (3-200 caracteres)
// paso 3: sustituir por la llamada real a /api/location (no guardar el texto)
export function searchLocation(text: string): Promise<LocationResponse> {
    return simulate(() => locationMock(text));
}
