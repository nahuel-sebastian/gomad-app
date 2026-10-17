import type { MapPointKind, MapPointsResponse } from "../api/types";
import { getJson } from "./http";
import { simulate } from "./mock/delay";
import { mapPointsMock } from "./mock/mapPoints";
import { sampleDataMode } from "./mode";

// [oeste, sur, este, norte] de la vista del mapa (no es la ubicacion de la persona)
export type Bbox = [number, number, number, number];

// GET /api/map/points: destinos y puntos utiles de la zona visible (correccion C2).
// La caja va con 5 decimales (~1 m): mas no aporta nada.
export function getMapPoints(bbox: Bbox, kinds: MapPointKind[]): Promise<MapPointsResponse> {
    if (sampleDataMode()) return simulate(() => mapPointsMock(bbox, kinds));
    const params = new URLSearchParams({ bbox: bbox.map((v) => v.toFixed(5)).join(",") });
    for (const kind of kinds) params.append("kinds", kind);
    return getJson<MapPointsResponse>(`/map/points?${params.toString()}`);
}
