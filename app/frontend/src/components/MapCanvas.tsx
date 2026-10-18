import { setWorkerUrl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Map, {
    Layer,
    Marker,
    Popup,
    Source,
    type ErrorEvent,
    type MapLayerMouseEvent,
    type MapRef,
} from "react-map-gl/maplibre";
import "../styles/map.css";
import { NAV_ZOOM } from "../data/navigation";
import { lineCoordinates } from "../lib/geometry";
import MapLegend from "./MapLegend";
import MapPin from "./MapPin";
import { pinImage, PIN_HEIGHT, PIN_PIXEL_RATIO } from "./mapPinImage";
import { KIND_ORDER, KIND_STYLES } from "./mapIcons";
import type { MapViewProps } from "./MapView";
import {
    boundsOf,
    EXPLORE_FIT_MAX_ZOOM,
    FALLBACK_STYLE,
    FIT_MAX_ZOOM,
    fitPadding,
    MAP_ATTRIBUTION,
    mapPoints,
    nearbyFeatures,
    pointInfo,
    POI_MIN_ZOOM,
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
const NEARBY_LAYERS = ["nearby-points"];

type BaseStyleMap = {
    getStyle(): { layers?: { id: string; "source-layer"?: string }[] } | undefined;
    setLayoutProperty(layer: string, name: string, value: unknown): unknown;
};

// El estilo de teselas trae sus propios puntos de interes (aparcamientos, paradas, parques...) con
// iconos que no son datos de GoMad ni salen en la leyenda: se ocultan. Los nombres de calles y
// lugares se quedan (son otras capas).
function hideBasePoiLayers(map: BaseStyleMap) {
    for (const layer of map.getStyle()?.layers ?? []) {
        if (layer["source-layer"] === "poi") map.setLayoutProperty(layer.id, "visibility", "none");
    }
}

type RenderedMap = {
    getLayer(id: string): unknown;
    queryRenderedFeatures(
        geometry: [[number, number], [number, number]],
        options: { layers: string[] },
    ): { properties?: { id?: unknown } | null }[];
    getBounds(): { contains(lnglat: [number, number]): boolean };
    getCanvas(): { clientWidth: number; clientHeight: number };
};

type StyleImageMap = {
    setMissingStyleImageResolver(resolver: (id: string) => void): unknown;
    hasImage(id: string): boolean;
    addImage(id: string, image: ImageData, options: { pixelRatio: number }): unknown;
    updateImage?(id: string, image: ImageData): unknown;
    isStyleLoaded?(): boolean;
};

// MapLibre pide cada imagen de pin la primera vez que la necesita (tambien tras setStyle). En
// MapLibre 6 el evento «styleimagemissing» llega tarde para esa peticion: el icono no salia hasta
// mover el mapa otra vez. El resolvedor si la resuelve en el momento.
function registerPinImages(map: StyleImageMap, fontReady: { current: boolean }) {
    map.setMissingStyleImageResolver((id) => {
        if (map.hasImage(id)) return;
        const image = pinImage(id, fontReady.current);
        if (image) map.addImage(id, image, { pixelRatio: PIN_PIXEL_RATIO });
    });
}

// Las imagenes deben estar en el estilo antes de que la capa nearby las solicite.
// El resolvedor anterior sigue cubriendo cambios de estilo y peticiones posteriores.
function preloadPinImages(map: StyleImageMap, fontReady: boolean) {
    if (typeof map.hasImage !== "function" || typeof map.addImage !== "function") return;
    for (const kind of KIND_ORDER) {
        for (const id of [`pin-${kind}`, `pin-off-${kind}`]) {
            if (map.hasImage(id)) continue;
            const image = pinImage(id, fontReady);
            if (image) map.addImage(id, image, { pixelRatio: PIN_PIXEL_RATIO });
        }
    }
}

function upgradeFontPinImages(map: StyleImageMap) {
    if (typeof map.hasImage !== "function" || typeof map.addImage !== "function") return;
    if (map.isStyleLoaded?.() === false) return;
    for (const kind of KIND_ORDER) {
        if (!KIND_STYLES[kind].fontGlyph) continue;
        for (const id of [`pin-${kind}`, `pin-off-${kind}`]) {
            const image = pinImage(id, true);
            if (!image) continue;
            if (map.hasImage(id)) map.updateImage?.(id, image);
            else map.addImage(id, image, { pixelRatio: PIN_PIXEL_RATIO });
        }
    }
}

export default function MapCanvas(props: MapViewProps) {
    const { markers, selectedId, origin, route, secondaryRoute, onSelect, explore = false, live, legendSlot, follow = false, onUserMove } = props;
    const { nearby, zoom, checkedPoiKinds, refresh } = useNearbyPoints(explore);
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
    // mismo objeto mientras no cambien los puntos: MapLibre no recalcula la capa en cada render
    const nearbyData = useMemo(() => nearbyFeatures(nearbyPoints, []), [nearbyPoints]);
    // anuncio para lectores de pantalla del punto pulsado
    const [info, setInfo] = useState("");
    // etiqueta pegada al icono con tipo y nombre: al pasar el raton, o fija al pulsar (con el dedo)
    const [tip, setTip] = useState<{ id: string; text: string; lon: number; lat: number; pinned: boolean } | null>(null);
    // si el punto deja de estar en la capa (otra vista, menos zoom), su etiqueta tambien
    const shownTip = tip && nearbyPoints.some((p) => p.id === tip.id) ? tip : null;
    const imagesFor = useRef<unknown>(null);
    const fontReady = useRef(false);
    useEffect(() => {
        let active = true;
        if (!document.fonts?.load) return;
        void document.fonts.load("12px icomoon").then((faces) => {
            if (!active || faces.length === 0) return;
            fontReady.current = true;
            const map = imagesFor.current as StyleImageMap | null;
            if (map) upgradeFontPinImages(map);
        }).catch(() => {
            // Los trazos originales mantienen visibles los puntos si falla la fuente.
        });
        return () => { active = false; };
    }, []);
    const bounds = boundsOf(mapPoints(props));
    // al encuadrar, el mapa explorable se queda por debajo del zoom de los puntos informativos
    const fitMaxZoom = explore ? EXPLORE_FIT_MAX_ZOOM : FIT_MAX_ZOOM;
    const mapRef = useRef<MapRef>(null);
    // clave por valor: un array nuevo con los mismos puntos no reencuadra
    const boundsKey = JSON.stringify(bounds);
    const fittedKey = useRef(boundsKey);
    const containerRef = useRef<HTMLDivElement>(null);
    // margenes leidos del CSS antes de pintar; el mapa se crea cuando ya se conocen
    const [padding, setPadding] = useState<Padding | null>(null);
    // franja de abajo tapada por la hoja de Resultados en movil (--map-covered-bottom)
    const coveredBottom = useRef(0);
    // lo que el mapa pinta de verdad en pantalla (fuera de la hoja), para que la leyenda cuente lo
    // mismo que se ve: sin los puntos ocultos por solaparse ni los que quedan fuera. null = aun no
    // se sabe (sin MapLibre real, p. ej. en pruebas): se cuenta todo lo cargado
    const [onScreen, setOnScreen] = useState<{
        key: string;
        pointIds: Set<string>;
        markerIds: Set<string>;
        live: boolean;
    } | null>(null);

    // si MapLibre no puede crear el mapa (sin WebGL2, sin memoria de GPU), react-map-gl solo
    // llama a onError: se relanza en el render para que MapErrorBoundary pinte el esquema
    const [creationError, setCreationError] = useState<Error | null>(null);
    const styleLoaded = useRef(false);

    const tipFor = (e: MapLayerMouseEvent, pinned: boolean) => {
        const feature = e.features?.[0];
        const geometry = feature?.geometry as { type: string; coordinates?: [number, number] } | undefined;
        if (!feature || !geometry?.coordinates) return null;
        const properties = (feature.properties ?? {}) as Partial<NearbyProperties>;
        const [lon, lat] = geometry.coordinates;
        return { id: String(properties.id), text: pointInfo(properties), lon, lat, pinned };
    };

    const handleClick = (e: MapLayerMouseEvent) => {
        const next = tipFor(e, true);
        setTip(next);
        setInfo(next?.text ?? "");
    };

    const handleMouseMove = (e: MapLayerMouseEvent) => {
        const next = tipFor(e, false);
        if (next) setTip(next);
        else setTip((current) => (current?.pinned ? current : null));
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
        if (containerRef.current) {
            setPadding(fitPadding(containerRef.current));
            coveredBottom.current =
                parseFloat(getComputedStyle(containerRef.current).getPropertyValue("--map-covered-bottom")) || 0;
        }
    }, []);

    // al terminar de pintar: que puntos y destinos se ven
    const handleIdle = (map: RenderedMap) => {
        const { clientWidth: width, clientHeight: height } = map.getCanvas();
        const box: [[number, number], [number, number]] = [
            [0, 0],
            [width, Math.max(0, height - coveredBottom.current)],
        ];
        const features = map.getLayer("nearby-points") ? map.queryRenderedFeatures(box, { layers: ["nearby-points"] }) : [];
        const pointIds = new Set(features.map((f) => String(f.properties?.id)));
        const view = map.getBounds();
        const markerIds = new Set(
            markers.filter((m) => view.contains([m.coordinate.lon, m.coordinate.lat])).map((m) => m.id),
        );
        const liveInView = Boolean(live && view.contains([live.lon, live.lat]));
        const key = [...pointIds].sort().join("|") + "#" + [...markerIds].sort().join("|") + "#" + liveInView;
        setOnScreen((current) => (current?.key === key ? current : { key, pointIds, markerIds, live: liveInView }));
    };
    const visiblePoints = onScreen ? nearbyPoints.filter((p) => onScreen.pointIds.has(p.id)) : nearbyPoints;
    const visibleMarkers = onScreen ? markers.filter((m) => onScreen.markerIds.has(m.id)) : markers;

    useEffect(() => {
        // el primer encuadre lo hace initialViewState; despues, al cambiar los puntos
        if (boundsKey === fittedKey.current || !bounds || !padding) {
            return;
        }
        fittedKey.current = boundsKey;
        mapRef.current?.fitBounds(bounds, { padding, maxZoom: fitMaxZoom, duration: 0 });
    }, [boundsKey, bounds, padding, fitMaxZoom]);

    // navegacion: la camara sigue la posicion en tiempo real; sin follow no se mueve
    useEffect(() => {
        const map = mapRef.current;
        if (!follow || !live || !map || !padding) return;
        const reduced = typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        map.easeTo({
            center: [live.lon, live.lat],
            zoom: Math.max(map.getZoom(), NAV_ZOOM),
            duration: reduced ? 0 : 500,
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [follow, live?.lat, live?.lon, padding]);

    // solo lo que mueve la persona (con evento de origen); el easeTo programado no lo tiene
    const handleUserMove = (e: { originalEvent?: unknown }) => {
        if (e.originalEvent) onUserMove?.();
    };

    if (creationError) {
        throw creationError;
    }

    // boton de la leyenda: sobre el mapa o en legendSlot (portal)
    const mapButtons = (
        <>
            <MapLegend
            markerKinds={visibleMarkers.flatMap((m) => (m.kind ? [apiKinds.get(m.id) ?? m.kind] : []))}
            points={visiblePoints}
            loadedPoints={nearbyPoints}
            zoom={explore ? zoom : null}
            truncated={explore && (nearby?.truncated ?? false)}
            live={Boolean(live) && (onScreen?.live ?? true)}
                checkedPoiKinds={explore ? checkedPoiKinds : []}
            />
        </>
    );

    return (
        <div className="map-canvas" ref={containerRef}>
            {padding && (
                <Map
                    ref={(map: MapRef | null) => {
                        mapRef.current = map;
                        const raw = map?.getMap?.() as unknown as StyleImageMap | undefined;
                        if (raw && imagesFor.current !== raw) {
                            imagesFor.current = raw;
                            registerPinImages(raw, fontReady);
                        }
                        // la leyenda resume lo que hay: el lienzo no entra en el orden de
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
                    onLoad={(e) => {
                        hideBasePoiLayers(e.target as unknown as BaseStyleMap);
                        preloadPinImages(e.target as unknown as StyleImageMap, fontReady.current);
                        refresh(e.target as unknown as ViewSource);
                    }}
                    onIdle={(e) => handleIdle(e.target as unknown as RenderedMap)}
                    onMoveEnd={(e) => refresh(e.target as unknown as ViewSource)}
                    onDragStart={handleUserMove}
                    onZoomStart={handleUserMove}
                    interactiveLayerIds={explore ? NEARBY_LAYERS : undefined}
                    onClick={explore ? handleClick : undefined}
                    onMouseMove={explore ? handleMouseMove : undefined}
                    onMouseLeave={explore ? () => setTip((current) => (current?.pinned ? current : null)) : undefined}
                    cursor={shownTip && !shownTip.pinned ? "pointer" : undefined}
                    initialViewState={
                        bounds ? { bounds, fitBoundsOptions: { padding, maxZoom: fitMaxZoom } } : undefined
                    }
                    style={{ width: "100%", height: "100%" }}>
                    {lineCoordinates(secondaryRoute).length > 1 && (
                        <Source id="route-secondary" type="geojson" data={secondaryRoute!}>
                            <Layer
                                id="route-secondary-line"
                                type="line"
                                layout={{ "line-cap": "round", "line-join": "round" }}
                                paint={{ "line-color": ROUTE_SECONDARY_COLOR, "line-width": 2.5, "line-dasharray": [2, 1.5] }}
                            />
                        </Source>
                    )}
                    {lineCoordinates(route).length > 1 && (
                        <Source id="route-main" type="geojson" data={route!}>
                            <Layer
                                id="route-main-line"
                                type="line"
                                layout={{ "line-cap": "round", "line-join": "round" }}
                                paint={{ "line-color": ROUTE_MAIN_COLOR, "line-width": 4 }}
                            />
                        </Source>
                    )}
                    {explore && nearby && (
                        // sin grupos: los puntos cercanos no son destinos y un numero se confundia con
                        // los pines numerados; los iconos que se pisan se ocultan y salen al acercar
                        <Source id="nearby" type="geojson" data={nearbyData}>
                            <Layer
                                id="nearby-points"
                                type="symbol"
                                layout={{
                                    "icon-image": ["get", "icon"],
                                    "icon-anchor": "bottom",
                                    "icon-allow-overlap": false,
                                }}
                            />
                        </Source>
                    )}
                    {shownTip && (
                        // solo a la vista: al pulsar, el mismo texto se anuncia en la region de estado
                        <Popup
                            longitude={shownTip.lon}
                            latitude={shownTip.lat}
                            anchor="bottom"
                            offset={PIN_HEIGHT + 2}
                            closeButton={false}
                            closeOnClick={false}
                            className="map-point-popup">
                            <span aria-hidden="true">{shownTip.text}</span>
                        </Popup>
                    )}
                    {origin && (
                        <Marker longitude={origin.lon} latitude={origin.lat}>
                            <span className="map-marker map-marker--origin" />
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
                                // mapa explorable: acercar al destino hasta ver los puntos informativos
                                const map = mapRef.current;
                                if (explore && map) {
                                    map.easeTo({
                                        center: [m.coordinate.lon, m.coordinate.lat],
                                        zoom: Math.max(map.getZoom(), POI_MIN_ZOOM),
                                        padding: padding ?? undefined,
                                    });
                                }
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
                {legendSlot === undefined && mapButtons}
            </div>
            {explore && (
                <p className="sr-only map-point-info" role="status">
                    {info}
                </p>
            )}
            <p className="map-view__attribution">{MAP_ATTRIBUTION}</p>
            {legendSlot && createPortal(mapButtons, legendSlot)}
        </div>
    );
}
