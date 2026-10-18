import type { MapPointKind, MapPointsResponse } from "../api/types";
import { ApiError } from "./errors";
import { getJson } from "./http";
import { simulate } from "./mock/delay";
import { mapPointsMock } from "./mock/mapPoints";
import { sampleDataMode } from "./mode";

// [oeste, sur, este, norte] de la vista del mapa (no es la ubicacion de la persona)
export type Bbox = [number, number, number, number];

// Una API anterior a la incorporación de papeleras rechaza toda la petición si recibe «bin».
// Tras comprobarlo una vez, seguimos mostrando los demás puntos hasta recargar la página.
let binUnsupported = false;

export function mapPointKindAvailable(kind: MapPointKind): boolean {
    return kind !== "bin" || !binUnsupported;
}

// GET /api/map/points: destinos y puntos utiles de la zona visible (correccion C2).
// La caja va con 5 decimales (~1 m): mas no aporta nada.
export async function getMapPoints(bbox: Bbox, kinds: MapPointKind[]): Promise<MapPointsResponse> {
    if (sampleDataMode()) return simulate(() => mapPointsMock(bbox, kinds));
    const request = (requestedKinds: MapPointKind[]) => {
        const params = new URLSearchParams({ bbox: bbox.map((v) => v.toFixed(5)).join(",") });
        for (const kind of requestedKinds) params.append("kinds", kind);
        return getJson<MapPointsResponse>(`/map/points?${params.toString()}`);
    };
    const requestedKinds = binUnsupported ? kinds.filter((kind) => kind !== "bin") : kinds;
    try {
        return await request(requestedKinds);
    } catch (error) {
        if (!(error instanceof ApiError) || error.status !== 422 || !requestedKinds.includes("bin")) throw error;
        const response = await request(requestedKinds.filter((kind) => kind !== "bin"));
        binUnsupported = true;
        return response;
    }
}
