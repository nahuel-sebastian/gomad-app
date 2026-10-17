import type { MapPoint, MapPointKind, MapPointsResponse } from "../../api/types";

// Puntos FICTICIOS del mapa de ejemplo alrededor del origen de ejemplo (Getafe). Nombres
// inventados y marcados «(ejemplo)»: no son lugares reales.
const POINTS: MapPoint[] = [
    { id: "ejemplo:mapa-parque-1", kind: "park", name: "Parque de la Fuente (ejemplo)", lon: -3.7355, lat: 40.3071 },
    { id: "ejemplo:mapa-parque-2", kind: "park", name: "Jardín del Molino (ejemplo)", lon: -3.7281, lat: 40.3032 },
    { id: "ejemplo:mapa-piscina", kind: "pool", name: "Piscina de verano (ejemplo)", lon: -3.7262, lat: 40.3088 },
    { id: "ejemplo:mapa-poli", kind: "facility", name: "Pistas del Sur (ejemplo)", lon: -3.7391, lat: 40.3019 },
    { id: "ejemplo:mapa-fuente-1", kind: "fountain", name: null, lon: -3.7334, lat: 40.3062, working: true },
    { id: "ejemplo:mapa-fuente-2", kind: "fountain", name: null, lon: -3.7302, lat: 40.3049, working: false },
    { id: "ejemplo:mapa-banco", kind: "bench", name: null, lon: -3.7322, lat: 40.3052 },
    { id: "ejemplo:mapa-dea", kind: "aed", name: null, lon: -3.7341, lat: 40.3044 },
    { id: "ejemplo:mapa-canina", kind: "dog_area", name: null, lon: -3.7368, lat: 40.3081 },
].map(({ lon, lat, working, ...p }) => ({
    ...p,
    kind: p.kind as MapPointKind,
    coordinate: { lat, lon },
    working: working ?? null,
    source: "ejemplo",
}));

export function mapPointsMock(bbox: [number, number, number, number], kinds: MapPointKind[]): MapPointsResponse {
    const [w, s, e, n] = bbox;
    const points = POINTS.filter(
        (p) =>
            kinds.includes(p.kind) &&
            p.coordinate.lon >= w &&
            p.coordinate.lon <= e &&
            p.coordinate.lat >= s &&
            p.coordinate.lat <= n,
    );
    return { points, truncated: false, clipped: false };
}
