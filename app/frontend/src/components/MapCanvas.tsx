import { setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import type { MapPoint } from "../api/types";
import Map, {
    Layer,
    Marker,
    Source,
    type ErrorEvent,
    type MapLayerMouseEvent,
    type MapRef,
} from "react-map-gl/maplibre";
import "../styles/map.css";
import { lineCoordinates } from "../lib/geometry";
import MapLegend from "./MapLegend";
import MapPin from "./MapPin";
import { KIND_STYLES, OUT_OF_SERVICE_COLOR } from "./mapIcons";
import NearbyList from "./NearbyList";
import { pinImage, PIN_PIXEL_RATIO } from "./mapPinImage";
import type { MapViewProps } from "./MapView";
import {
    boundsOf,
    closestPoints,
    FALLBACK_STYLE,
    FIT_MAX_ZOOM,
    fitPadding,
    MAP_ATTRIBUTION,
    mapPoints,
    NEARBY_LIST_SIZE,
    nearbyFeatures,
    pointInfo,
    TILE_STYLE_URL,
    type NearbyProperties,
    type Padding,
} from "./mapUtils";
import { useNearbyPoints, type ViewSource } from "./useNearbyPoints";

// Mapa de MapLibre (V-F1). Solo lo carga MapView en diferido cuando hay WebGL, asi
// maplibre-gl no entra en el paquete inicial.

// MapLibre 6 busca su worker junto a su propio modulo; con Vite (dev y build) no esta ahi.
// Vite empaqueta el worker aparte (con lo que comparte con el modulo principal) y da su URL.
setWorkerUrl(workerUrl);

// MapLibre no lee variables CSS: mismos valores que --green-dark y --muted de main.css
const ROUTE_MAIN_COLOR = "#135c3a";
const ROUTE_SECONDARY_COLOR = "#55677a";
// grupos de puntos cercanos: --navy de main.css
const CLUSTER_COLOR = "#12395b";
const NEARBY_LAYERS = ["nearby-clusters", "nearby-points"];

type StyleImageMap = {
    on(type: "styleimagemissing", listener: (e: { id: string }) => void): unknown;
    hasImage(id: string): boolean;
    addImage(id: string, image: ImageData, options: { pixelRatio: number }): unknown;
};

// MapLibre pide cada imagen de pin la primera vez que la necesita (tambien tras setStyle)
function registerPinImages(map: StyleImageMap) {
    map.on("styleimagemissing", (e) => {
        if (map.hasImage(e.id)) return;
        const image = pinImage(e.id);
        if (image) map.addImage(e.id, image, { pixelRatio: PIN_PIXEL_RATIO });
    });
}

export default function MapCanvas(props: MapViewProps) {
    const { markers, selectedId, origin, route, secondaryRoute, onSelect, explore = false, live } = props;
    const { nearby, zoom, center, checkedPoiKinds, refresh } = useNearbyPoints(explore);
    // los destinos que ya tienen pin numerado no se repiten como punto cercano
    const markerKey = markers.map((m) => m.id).join("|");
    const nearbyPoints = useMemo(() => {
        const ids = new Set(markerKey.split("|"));
        return explore && nearby ? nearby.points.filter((p) => !ids.has(p.id)) : [];
    }, [explore, nearby, markerKey]);
    // tipo que da la API a cada id (p. ej. «pool»): manda sobre el del resultado
    // (globalThis.Map: «Map» aqui es el componente de react-map-gl)
    const apiKinds = useMemo(
        () => new globalThis.Map((nearby?.points ?? []).map((p) => [p.id, p.kind] as const)),
        [nearby],
    );
    // mismo objeto mientras no cambien los puntos: MapLibre no recalcula los grupos en cada render
    const nearbyData = useMemo(() => nearbyFeatures(nearbyPoints, []), [nearbyPoints]);
    const [info, setInfo] = useState("");
    const listed = useMemo(
        () => (center ? closestPoints(nearbyPoints, center, NEARBY_LIST_SIZE) : []),
        [nearbyPoints, center],
    );
    // lugar elegido en «Lugares a la vista»: se resalta en el mapa y se anuncia
    const [highlight, setHighlight] = useState<MapPoint | null>(null);
    const highlighted = highlight && nearbyPoints.some((p) => p.id === highlight.id) ? highlight : null;
    const pick = (p: MapPoint) => {
        setHighlight(p);
        setInfo(`${pointInfo(p)}. Resaltado en el mapa.`);
    };
    const imagesFor = useRef<unknown>(null);
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

    const handleClick = (e: MapLayerMouseEvent) => {
        const feature = e.features?.[0];
        if (!feature) {
            setInfo("");
            return;
        }
        const properties = (feature.properties ?? {}) as Partial<NearbyProperties> & { cluster?: boolean };
        const geometry = feature.geometry as { type: string; coordinates?: [number, number] };
        if (properties.cluster && geometry.coordinates) {
            // un grupo: acercar para separarlo
            e.target.easeTo({ center: geometry.coordinates, zoom: e.target.getZoom() + 2 });
            return;
        }
        setInfo(pointInfo(properties));
    };

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
                        const raw = map?.getMap?.() as unknown as StyleImageMap | undefined;
                        if (raw && imagesFor.current !== raw) {
                            imagesFor.current = raw;
                            registerPinImages(raw);
                        }
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
                    onLoad={(e) => refresh(e.target as unknown as ViewSource)}
                    onMoveEnd={(e) => refresh(e.target as unknown as ViewSource)}
                    interactiveLayerIds={explore ? NEARBY_LAYERS : undefined}
                    onClick={explore ? handleClick : undefined}
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
                    {explore && nearby && (
                        <Source
                            id="nearby"
                            type="geojson"
                            data={nearbyData}
                            cluster
                            clusterMaxZoom={16}
                            clusterRadius={44}>
                            <Layer
                                id="nearby-clusters"
                                type="circle"
                                filter={["has", "point_count"]}
                                paint={{
                                    "circle-color": CLUSTER_COLOR,
                                    "circle-radius": ["step", ["get", "point_count"], 15, 20, 19, 100, 23],
                                    "circle-stroke-color": "#ffffff",
                                    "circle-stroke-width": 2,
                                }}
                            />
                            <Layer
                                id="nearby-count"
                                type="symbol"
                                filter={["has", "point_count"]}
                                layout={{
                                    "text-field": ["get", "point_count_abbreviated"],
                                    "text-font": ["Noto Sans Bold"],
                                    "text-size": 13,
                                    "text-allow-overlap": true,
                                }}
                                paint={{ "text-color": "#ffffff" }}
                            />
                            <Layer
                                id="nearby-points"
                                type="symbol"
                                filter={["!", ["has", "point_count"]]}
                                layout={{
                                    "icon-image": ["get", "icon"],
                                    "icon-anchor": "bottom",
                                    "icon-allow-overlap": true,
                                }}
                            />
                        </Source>
                    )}
                    {origin && (
                        <Marker longitude={origin.lon} latitude={origin.lat}>
                            <span className="map-marker map-marker--origin" />
                        </Marker>
                    )}
                    {highlighted && (
                        <Marker
                            longitude={highlighted.coordinate.lon}
                            latitude={highlighted.coordinate.lat}
                            anchor="bottom">
                            <span
                                className="map-marker map-marker--highlight"
                                style={
                                    {
                                        "--pin-color":
                                            highlighted.working === false
                                                ? OUT_OF_SERVICE_COLOR
                                                : KIND_STYLES[highlighted.kind].color,
                                    } as CSSProperties
                                }
                                role="img"
                                aria-label={`${pointInfo(highlighted)}, resaltado en el mapa`}>
                                <svg viewBox="0 0 960 960" aria-hidden="true" focusable="false">
                                    <path d={KIND_STYLES[highlighted.kind].path} />
                                </svg>
                            </span>
                        </Marker>
                    )}
                    {live && (
                        <Marker longitude={live.lon} latitude={live.lat}>
                            <span
                                className="map-marker map-marker--live"
                                role="img"
                                aria-label="Estás aquí (en tiempo real)"
                            />
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
                            {m.kind ? (
                                <MapPin kind={apiKinds.get(m.id) ?? m.kind} number={m.number} name={m.name} selected={m.id === selectedId} />
                            ) : (
                                <span className={`map-marker${m.id === selectedId ? " map-marker--selected" : ""}`}>
                                    {m.number}
                                </span>
                            )}
                        </Marker>
                    ))}
                </Map>
            )}
            <div className="map-zoom" role="group" aria-label="Zoom del mapa">
                <button type="button" aria-label="Acercar mapa" onClick={() => mapRef.current?.zoomIn()} disabled={!padding}>+</button>
                <button type="button" aria-label="Alejar mapa" onClick={() => mapRef.current?.zoomOut()} disabled={!padding}>−</button>
            </div>
            <div className="map-panels">
                <MapLegend
                    markerKinds={markers.flatMap((m) => (m.kind ? [apiKinds.get(m.id) ?? m.kind] : []))}
                    points={nearbyPoints}
                    zoom={explore ? zoom : null}
                    truncated={explore && (nearby?.truncated ?? false)}
                    live={Boolean(live)}
                    checkedPoiKinds={explore ? checkedPoiKinds : []}
                />
                {explore && <NearbyList points={listed} onPick={pick} />}
            </div>
            {explore && (
                <p className={`map-point-info${info ? "" : " map-point-info--empty"}`} role="status">
                    {info}
                </p>
            )}
            <p className="map-view__attribution">{MAP_ATTRIBUTION}</p>
        </div>
    );
}
