import type { Coordinate, RouteVariant } from "../api/types";
import { lineCoordinates } from "../lib/geometry";

export interface MapMarker {
    id: string;
    // numero visible, el mismo que en la lista
    number: number;
    name: string;
    coordinate: Coordinate;
}

interface MapViewProps {
    markers: MapMarker[];
    selectedId?: string | null;
    origin?: Coordinate | null;
    // geometria GeoJSON de la ruta a dibujar (si hay)
    route?: RouteVariant["geometry"];
    // tramo alternativo, mas tenue (p. ej. la ruta directa)
    secondaryRoute?: RouteVariant["geometry"];
    className?: string;
}

const SIZE = 100;

// Marcador de posicion del mapa (paso 1). Misma interfaz que tendra el mapa
// de MapLibre en el paso 3. La lista o el resumen en texto son el equivalente
// completo, asi que se oculta a los lectores de pantalla.
export default function MapView({
    markers,
    selectedId,
    origin,
    route,
    secondaryRoute,
    className,
}: MapViewProps) {
    const main = lineCoordinates(route);
    const secondary = lineCoordinates(secondaryRoute);
    const points: [number, number][] = [
        ...markers.map((m) => [m.coordinate.lon, m.coordinate.lat] as [number, number]),
        ...main,
        ...secondary,
        ...(origin ? [[origin.lon, origin.lat] as [number, number]] : []),
    ];
    const lons = points.map((p) => p[0]);
    const lats = points.map((p) => p[1]);
    const minLon = Math.min(...lons);
    const maxLon = Math.max(...lons);
    const minLat = Math.min(...lats);
    const maxLat = Math.max(...lats);
    const span = Math.max(maxLon - minLon, maxLat - minLat, 1e-4);
    const project = ([lon, lat]: [number, number]) => [
        8 + ((lon - minLon) / span) * (SIZE - 16),
        SIZE - 8 - ((lat - minLat) / span) * (SIZE - 16),
    ];
    const path = (coords: [number, number][]) =>
        coords.map((c) => project(c).map((n) => n.toFixed(2)).join(",")).join(" ");

    return (
        <div className={`map-view${className ? ` ${className}` : ""}`} aria-hidden="true">
            {points.length > 0 && (
                <svg className="map-view__svg" viewBox={`0 0 ${SIZE} ${SIZE}`} preserveAspectRatio="xMidYMid meet">
                    {secondary.length > 1 && (
                        <polyline className="map-view__route map-view__route--secondary" points={path(secondary)} />
                    )}
                    {main.length > 1 && <polyline className="map-view__route" points={path(main)} />}
                    {origin && (
                        <circle
                            className="map-view__origin"
                            cx={project([origin.lon, origin.lat])[0]}
                            cy={project([origin.lon, origin.lat])[1]}
                            r="2.2"
                        />
                    )}
                    {markers.map((m) => {
                        const [x, y] = project([m.coordinate.lon, m.coordinate.lat]);
                        const selected = m.id === selectedId;
                        return (
                            <g key={m.id} className={`map-view__marker${selected ? " map-view__marker--selected" : ""}`}>
                                <circle cx={x} cy={y} r={selected ? 4.4 : 3.6} />
                                <text x={x} y={y + 1.3} textAnchor="middle">
                                    {m.number}
                                </text>
                            </g>
                        );
                    })}
                </svg>
            )}
            <span className="map-view__note">Mapa de ejemplo (sin teselas)</span>
        </div>
    );
}
