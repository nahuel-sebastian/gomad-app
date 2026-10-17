import { setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import Map, { Layer, Marker, Source, type ErrorEvent, type MapRef } from "react-map-gl/maplibre";
import "../styles/map.css";
import { lineCoordinates } from "../lib/geometry";
import type { MapViewProps } from "./MapView";
import {
    boundsOf,
    FALLBACK_STYLE,
    FIT_MAX_ZOOM,
    fitPadding,
    MAP_ATTRIBUTION,
    mapPoints,
    TILE_STYLE_URL,
    type Padding,
} from "./mapUtils";

// Mapa de MapLibre (V-F1). Solo lo carga MapView en diferido cuando hay WebGL, asi
// maplibre-gl no entra en el paquete inicial.

// MapLibre 6 busca su worker junto a su propio modulo; con Vite (dev y build) no esta ahi.
// Vite empaqueta el worker aparte (con lo que comparte con el modulo principal) y da su URL.
setWorkerUrl(workerUrl);

// MapLibre no lee variables CSS: mismos valores que --green-dark y --muted de main.css
const ROUTE_MAIN_COLOR = "#135c3a";
const ROUTE_SECONDARY_COLOR = "#55677a";

export default function MapCanvas(props: MapViewProps) {
    const { markers, selectedId, origin, route, secondaryRoute, onSelect } = props;
    const bounds = boundsOf(mapPoints(props));
    const mapRef = useRef<MapRef>(null);
    // clave por valor: un array nuevo con los mismos puntos no reencuadra
    const boundsKey = JSON.stringify(bounds);
    const fittedKey = useRef(boundsKey);
    const containerRef = useRef<HTMLDivElement>(null);
    // margenes leidos del CSS antes de pintar; el mapa se crea cuando ya se conocen
    const [padding, setPadding] = useState<Padding | null>(null);

    // si MapLibre no puede crear el mapa (sin WebGL2, sin memoria de GPU), react-map-gl solo
    // llama a onError: se relanza en el render para que MapErrorBoundary pinte el esquema
    const [creationError, setCreationError] = useState<Error | null>(null);
    const styleLoaded = useRef(false);

    const handleError = (e: ErrorEvent) => {
        if (!e.target) {
            setCreationError(e.error ?? new Error("No se pudo crear el mapa"));
        } else if (!styleLoaded.current) {
            // no llega el estilo de teselas: fondo liso para que se dibujen ruta y marcadores
            styleLoaded.current = true;
            e.target.setStyle(FALLBACK_STYLE);
        }
    };

    useLayoutEffect(() => {
        if (containerRef.current) setPadding(fitPadding(containerRef.current));
    }, []);

    useEffect(() => {
        // el primer encuadre lo hace initialViewState; despues, al cambiar los puntos
        if (boundsKey === fittedKey.current || !bounds || !padding) {
            return;
        }
        fittedKey.current = boundsKey;
        mapRef.current?.fitBounds(bounds, { padding, maxZoom: FIT_MAX_ZOOM, duration: 0 });
    }, [boundsKey, bounds, padding]);

    if (creationError) {
        throw creationError;
    }

    return (
        <div className="map-canvas" ref={containerRef}>
            {padding && (
                <Map
                    ref={(map: MapRef | null) => {
                        mapRef.current = map;
                        // la lista es el equivalente completo: el lienzo no entra en el orden de
                        // tabulacion desde que existe (onLoad espera a estilo y teselas)
                        map?.getCanvas().setAttribute("tabindex", "-1");
                    }}
                    mapStyle={TILE_STYLE_URL}
                    attributionControl={false}
                    keyboard={false}
                    onError={handleError}
                    onStyleData={() => {
                        styleLoaded.current = true;
                    }}
                    initialViewState={
                        bounds ? { bounds, fitBoundsOptions: { padding, maxZoom: FIT_MAX_ZOOM } } : undefined
                    }
                    style={{ width: "100%", height: "100%" }}>
                    {lineCoordinates(secondaryRoute).length > 1 && (
                        <Source id="route-secondary" type="geojson" data={secondaryRoute!}>
                            <Layer
                                id="route-secondary-line"
                                type="line"
                                layout={{ "line-cap": "round", "line-join": "round" }}
                                paint={{ "line-color": ROUTE_SECONDARY_COLOR, "line-width": 4, "line-dasharray": [2, 1.5] }}
                            />
                        </Source>
                    )}
                    {lineCoordinates(route).length > 1 && (
                        <Source id="route-main" type="geojson" data={route!}>
                            <Layer
                                id="route-main-line"
                                type="line"
                                layout={{ "line-cap": "round", "line-join": "round" }}
                                paint={{ "line-color": ROUTE_MAIN_COLOR, "line-width": 6 }}
                            />
                        </Source>
                    )}
                    {origin && (
                        <Marker longitude={origin.lon} latitude={origin.lat}>
                            <span className="map-marker map-marker--origin" />
                        </Marker>
                    )}
                    {markers.map((m) => (
                        <Marker
                            key={m.id}
                            longitude={m.coordinate.lon}
                            latitude={m.coordinate.lat}
                            onClick={(e) => {
                                // que el clic no llegue al mapa
                                e.originalEvent.stopPropagation();
                                onSelect?.(m.id);
                            }}>
                            <span className={`map-marker${m.id === selectedId ? " map-marker--selected" : ""}`}>
                                {m.number}
                            </span>
                        </Marker>
                    ))}
                </Map>
            )}
            <div className="map-zoom" role="group" aria-label="Zoom del mapa">
                <button type="button" aria-label="Acercar mapa" onClick={() => mapRef.current?.zoomIn()} disabled={!padding}>+</button>
                <button type="button" aria-label="Alejar mapa" onClick={() => mapRef.current?.zoomOut()} disabled={!padding}>−</button>
            </div>
            <p className="map-view__attribution">{MAP_ATTRIBUTION}</p>
        </div>
    );
}
