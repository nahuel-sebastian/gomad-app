import type { RouteVariant } from "../api/types";

// El contrato declara `geometry` como objeto sin campos (Record<string, never>):
// aqui se construye y se lee como GeoJSON LineString, comprobando la forma.

export type LonLat = [number, number];

export function toLineString(coordinates: LonLat[]): RouteVariant["geometry"] {
    return { type: "LineString", coordinates } as unknown as RouteVariant["geometry"];
}

export function lineCoordinates(geometry: RouteVariant["geometry"] | undefined): LonLat[] {
    const g = geometry as unknown as { type?: unknown; coordinates?: unknown } | undefined;
    if (!g || g.type !== "LineString" || !Array.isArray(g.coordinates)) {
        return [];
    }
    return g.coordinates.filter(
        (c): c is LonLat =>
            Array.isArray(c) && typeof c[0] === "number" && typeof c[1] === "number",
    );
}
