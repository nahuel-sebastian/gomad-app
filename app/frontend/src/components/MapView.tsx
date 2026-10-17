import { Component, lazy, Suspense, useState, type ReactNode } from "react";
import type { Coordinate, RouteVariant } from "../api/types";
import { lineCoordinates } from "../lib/geometry";
import { hasWebGL } from "./mapUtils";

export interface MapMarker {
    id: string;
    // numero visible, el mismo que en la lista
    number: number;
    name: string;
    coordinate: Coordinate;
}

export interface MapViewProps {
    markers: MapMarker[];
    selectedId?: string | null;
    origin?: Coordinate | null;
    // geometria GeoJSON de la ruta a dibujar (si hay)
    route?: RouteVariant["geometry"];
    // tramo alternativo, mas tenue (p. ej. la ruta directa)
    secondaryRoute?: RouteVariant["geometry"];
    className?: string;
    // se llama al pulsar un marcador, con su id
    onSelect?: (id: string) => void;
}

const SIZE = 100;

// Esquema SVG sin teselas: respaldo cuando no hay WebGL, mientras carga MapLibre
// o si MapLibre falla
function Schematic({ markers, selectedId, origin, route, secondaryRoute }: MapViewProps) {
    const [zoom, setZoom] = useState(1);
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
        <div>
            {points.length > 0 && (
                <svg aria-hidden="true" className="map-view__svg" viewBox={`${(SIZE - SIZE / zoom) / 2} ${(SIZE - SIZE / zoom) / 2} ${SIZE / zoom} ${SIZE / zoom}`} preserveAspectRatio="xMidYMid meet">
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
            <div className="map-zoom" role="group" aria-label="Zoom del mapa">
                <button type="button" aria-label="Acercar mapa" disabled={zoom >= 4} onClick={() => setZoom((value) => Math.min(4, value * 2))}>+</button>
                <button type="button" aria-label="Alejar mapa" disabled={zoom <= 1} onClick={() => setZoom((value) => Math.max(1, value / 2))}>−</button>
            </div>
            <span className="map-view__note">Mapa simplificado (sin teselas)</span>
        </div>
    );
}

const MapCanvas = lazy(() => import("./MapCanvas"));

// Si falla la carga diferida de MapCanvas o MapLibre no puede crear el mapa (MapCanvas
// relanza ese error en el render), se pinta el respaldo
export class MapErrorBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
    state = { failed: false };

    static getDerivedStateFromError() {
        return { failed: true };
    }

    render() {
        return this.state.failed ? this.props.fallback : this.props.children;
    }
}

// Mapa de la app: MapLibre con teselas si hay WebGL y, si no, el esquema. La lista o el
// resumen en texto son el equivalente completo (RF-11), asi que se oculta a los lectores
// de pantalla y no tiene nada enfocable.
export default function MapView(props: MapViewProps) {
    const [webgl] = useState(hasWebGL);
    const schematic = <Schematic {...props} />;

    return (
        <div
            className={`map-view gomad-component gomad-map-view${props.className ? ` ${props.className}` : ""}`}>
            {webgl ? (
                <MapErrorBoundary fallback={schematic}>
                    <Suspense fallback={schematic}>
                        <MapCanvas {...props} />
                    </Suspense>
                </MapErrorBoundary>
            ) : (
                schematic
            )}
        </div>
    );
}
