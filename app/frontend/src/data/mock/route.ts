import type {
    Coordinate,
    RoutePoi,
    RouteRequest,
    RouteResponse,
    RouteVariant,
} from "../../api/types";
import { formatDistance, formatMinutes } from "../../lib/format";
import { toLineString } from "../../lib/geometry";
import { poiCount } from "../../lib/labels";
import { getMockScenario } from "./scenario";

// Rutas de ejemplo: geometria inventada entre origen y destino

function haversine(a: Coordinate, b: Coordinate): number {
    const r = 6371000;
    const dLat = ((b.lat - a.lat) * Math.PI) / 180;
    const dLon = ((b.lon - a.lon) * Math.PI) / 180;
    const h =
        Math.sin(dLat / 2) ** 2 +
        Math.cos((a.lat * Math.PI) / 180) *
            Math.cos((b.lat * Math.PI) / 180) *
            Math.sin(dLon / 2) ** 2;
    return 2 * r * Math.asin(Math.sqrt(h));
}

// Puntos intermedios con un desvio lateral (0 = recta)
function line(a: Coordinate, b: Coordinate, bend: number): [number, number][] {
    const points: [number, number][] = [];
    for (let i = 0; i <= 8; i++) {
        const t = i / 8;
        const offset = Math.sin(Math.PI * t) * bend;
        const lat = a.lat + (b.lat - a.lat) * t - (b.lon - a.lon) * offset;
        const lon = a.lon + (b.lon - a.lon) * t + (b.lat - a.lat) * offset;
        points.push([Math.round(lon * 1e5) / 1e5, Math.round(lat * 1e5) / 1e5]);
    }
    return points;
}

function poisAlong(coords: [number, number][], types: RoutePoi["type"][]): RoutePoi[] {
    return types.map((type, i) => {
        const [lon, lat] = coords[1 + (i % (coords.length - 2))];
        return { type, coordinate: { lat, lon }, source: type === "aed" ? "desfibriladores" : "osm" };
    });
}

function describe(v: Omit<RouteVariant, "description">): string {
    const parts = [formatDistance(v.distance_m), formatMinutes(v.duration_min)];
    parts.push(v.green_pct === null ? "zona verde sin datos" : `${Math.round(v.green_pct)} % por zona verde`);
    parts.push(v.traffic_m > 0 ? `${formatDistance(v.traffic_m)} junto a tráfico intenso` : "sin tramos con tráfico intenso");
    const counts = new Map<RoutePoi["type"], number>();
    v.pois.forEach((p) => counts.set(p.type, (counts.get(p.type) ?? 0) + 1));
    counts.forEach((n, type) => parts.push(poiCount(type, n)));
    return `${parts.join(", ")}.`;
}

export function routeMock(req: RouteRequest): RouteResponse {
    const scenario = getMockScenario();
    const approximate = scenario.routeApproximate;
    const slow = req.profile === "senior" || req.profile === "stroller";
    const speed = slow ? 3.5 : 4.5;
    const straight = Math.max(200, haversine(req.origin, req.destination));

    const directCoords = line(req.origin, req.destination, approximate ? 0 : 0.04);
    const directBase = {
        kind: "direct" as const,
        geometry: toLineString(directCoords),
        distance_m: Math.round(straight * (approximate ? 1 : 1.2)),
        duration_min: 0,
        green_pct: approximate ? null : 18,
        traffic_m: approximate ? 0 : Math.round(straight * 0.45),
        pois: poisAlong(directCoords, ["bench"]),
        approximate,
    };
    directBase.duration_min = Math.round((directBase.distance_m / 1000 / speed) * 60);

    if (approximate) {
        const variant = { ...directBase, pois: [] as RoutePoi[] };
        return {
            direct: { ...variant, description: describe(variant) },
            healthy: { ...variant, kind: "healthy", description: describe(variant) },
            warnings: [
                "Fuera de los municipios piloto: ruta aproximada en línea recta, sin datos de verde ni tráfico.",
            ],
            sources: [
                { source: "osm", label: "Red peatonal: OpenStreetMap", date: "2026-10-12T04:00:00", own_criterion: false },
            ],
        };
    }

    const healthyCoords = line(req.origin, req.destination, 0.18);
    const extraPois: RoutePoi["type"][] = [];
    if (scenario.id === "ana") extraPois.push("dog_area", "bin", "bin", "bin");
    if (scenario.id === "dani") extraPois.push("playground");
    const healthyBase = {
        kind: "healthy" as const,
        geometry: toLineString(healthyCoords),
        distance_m: Math.round(directBase.distance_m * 1.17),
        duration_min: 0,
        green_pct: 64,
        traffic_m: Math.round(straight * 0.04),
        pois: poisAlong(healthyCoords, [
            "fountain",
            "fountain",
            "bench",
            "bench",
            "bench",
            "bench",
            "bench",
            "aed",
            ...extraPois,
        ]),
        approximate: false,
    };
    healthyBase.duration_min = Math.round((healthyBase.distance_m / 1000 / speed) * 60);

    return {
        direct: { ...directBase, description: describe(directBase) },
        healthy: { ...healthyBase, description: describe(healthyBase) },
        warnings: scenario.id === "dani" ? ["La ruta recomendada evita las vías rápidas: mejor con carrito."] : [],
        sources: [
            { source: "osm", label: "Red peatonal y mobiliario: OpenStreetMap", date: "2026-10-12T04:00:00", own_criterion: false },
            { source: "vpla_redes", label: "Zona verde: planeamiento 2025 (IDEM)", date: "2026-10-01T04:00:00", own_criterion: false },
            { source: "desfibriladores", label: "Desfibriladores: Comunidad de Madrid", date: "2026-10-15T04:00:00", own_criterion: false },
            { source: "routing", label: "Penalización por tráfico y bonificación por verde", date: null, own_criterion: true },
        ],
    };
}
