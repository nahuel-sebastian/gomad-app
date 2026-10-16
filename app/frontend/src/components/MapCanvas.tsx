import "maplibre-gl/dist/maplibre-gl.css";
import Map, { Marker } from "react-map-gl/maplibre";
import "../styles/map.css";
import type { MapViewProps } from "./MapView";
import { boundsOf, FIT_OPTIONS, MAP_ATTRIBUTION, mapPoints, TILE_STYLE_URL } from "./mapUtils";

// Mapa de MapLibre (V-F1). Solo lo carga MapView en diferido cuando hay WebGL, asi
// maplibre-gl no entra en el paquete inicial.

export default function MapCanvas(props: MapViewProps) {
    const { markers, origin } = props;
    const bounds = boundsOf(mapPoints(props));

    return (
        <div className="map-canvas">
            <Map
                mapStyle={TILE_STYLE_URL}
                attributionControl={false}
                keyboard={false}
                initialViewState={bounds ? { bounds, fitBoundsOptions: FIT_OPTIONS } : undefined}
                // la lista es el equivalente completo: el lienzo no entra en el orden de tabulacion
                onLoad={(e) => e.target.getCanvas().setAttribute("tabindex", "-1")}
                style={{ width: "100%", height: "100%" }}>
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
