import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import Map, { Layer, Marker, Source, type MapRef } from "react-map-gl/maplibre";
import "../styles/map.css";
import { lineCoordinates } from "../lib/geometry";
import type { MapViewProps } from "./MapView";
import { boundsOf, FIT_OPTIONS, MAP_ATTRIBUTION, mapPoints, TILE_STYLE_URL } from "./mapUtils";

// Mapa de MapLibre (V-F1). Solo lo carga MapView en diferido cuando hay WebGL, asi
// maplibre-gl no entra en el paquete inicial.

// MapLibre no lee variables CSS: mismos valores que --green-dark y --muted de main.css
const ROUTE_MAIN_COLOR = "#135c3a";
const ROUTE_SECONDARY_COLOR = "#55677a";

export default function MapCanvas(props: MapViewProps) {
    const { markers, origin, route, secondaryRoute } = props;
    const bounds = boundsOf(mapPoints(props));
    const mapRef = useRef<MapRef>(null);
    // clave por valor: un array nuevo con los mismos puntos no reencuadra
    const boundsKey = JSON.stringify(bounds);
    const fittedKey = useRef(boundsKey);

    useEffect(() => {
        // el primer encuadre lo hace initialViewState; despues, al cambiar los puntos
        if (boundsKey === fittedKey.current || !bounds) {
            return;
        }
        fittedKey.current = boundsKey;
        mapRef.current?.fitBounds(bounds, { ...FIT_OPTIONS, duration: 0 });
    }, [boundsKey, bounds]);

    return (
        <div className="map-canvas">
            <Map
                ref={mapRef}
                mapStyle={TILE_STYLE_URL}
                attributionControl={false}
                keyboard={false}
                initialViewState={bounds ? { bounds, fitBoundsOptions: FIT_OPTIONS } : undefined}
                // la lista es el equivalente completo: el lienzo no entra en el orden de tabulacion
                onLoad={(e) => e.target.getCanvas().setAttribute("tabindex", "-1")}
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
                    <Marker key={m.id} longitude={m.coordinate.lon} latitude={m.coordinate.lat}>
                        <span className="map-marker">{m.number}</span>
                    </Marker>
                ))}
            </Map>
            <p className="map-view__attribution">{MAP_ATTRIBUTION}</p>
        </div>
    );
}
