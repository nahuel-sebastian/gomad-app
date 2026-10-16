import { lineCoordinates, type LonLat } from "../lib/geometry";
import type { MapViewProps } from "./MapView";

// Funciones del mapa sin React (aparte para que MapView y MapCanvas solo exporten componentes)

// Teselas de OpenFreeMap: gratis y sin clave (decidido el 16/10); PMTiles local el lunes (L-4)
export const TILE_STYLE_URL = "https://tiles.openfreemap.org/styles/liberty";
// la que pide OpenFreeMap en su TileJSON: «OpenFreeMap © OpenMapTiles Data from OpenStreetMap»
export const MAP_ATTRIBUTION = "© OpenStreetMap · OpenMapTiles · OpenFreeMap";

// Estilo de respaldo si no llega el de OpenFreeMap: fondo liso del color de .map-view, para
// que se puedan dibujar la ruta y los marcadores (react-map-gl solo anade fuentes con estilo)
export const FALLBACK_STYLE = {
    version: 8 as const,
    sources: {},
    layers: [{ id: "background", type: "background" as const, paint: { "background-color": "#e9eff3" } }],
};

export type Bounds = [LonLat, LonLat];

// con un solo punto se abre +-0,005 grados (unos 500 m): criterio propio
const MIN_HALF_SPAN = 0.005;
export const FIT_MAX_ZOOM = 16;
const FIT_DEFAULT_PADDING_PX = 40;

export interface Padding {
    top: number;
    right: number;
    bottom: number;
    left: number;
}

// Margenes del encuadre: las variables CSS --map-fit-{top,right,bottom,left} del contenedor
// (p. ej. en movil, la barra de arriba y la hoja de resultados tapan parte del mapa)
export function fitPadding(element: Element): Padding {
    const style = getComputedStyle(element);
    const side = (name: keyof Padding) =>
        parseFloat(style.getPropertyValue(`--map-fit-${name}`)) || FIT_DEFAULT_PADDING_PX;
    return { top: side("top"), right: side("right"), bottom: side("bottom"), left: side("left") };
}

// Caja [[oeste, sur], [este, norte]] de los puntos; null si no hay ninguno
export function boundsOf(points: LonLat[]): Bounds | null {
    if (points.length === 0) {
        return null;
    }
    const lons = points.map((p) => p[0]);
    const lats = points.map((p) => p[1]);
    let [w, e] = [Math.min(...lons), Math.max(...lons)];
    let [s, n] = [Math.min(...lats), Math.max(...lats)];
    if (e - w < 2 * MIN_HALF_SPAN && n - s < 2 * MIN_HALF_SPAN) {
        const [cx, cy] = [(w + e) / 2, (s + n) / 2];
        [w, e] = [cx - MIN_HALF_SPAN, cx + MIN_HALF_SPAN];
        [s, n] = [cy - MIN_HALF_SPAN, cy + MIN_HALF_SPAN];
    }
    return [
        [w, s],
        [e, n],
    ];
}

// Todos los puntos que debe encuadrar el mapa: destinos, origen y rutas
export function mapPoints({ markers, origin, route, secondaryRoute }: MapViewProps): LonLat[] {
    return [
        ...markers.map((m) => [m.coordinate.lon, m.coordinate.lat] as LonLat),
        ...(origin ? [[origin.lon, origin.lat] as LonLat] : []),
        ...lineCoordinates(route),
        ...lineCoordinates(secondaryRoute),
    ];
}

// true si el navegador puede crear un contexto WebGL2 (MapLibre 6 no tiene respaldo WebGL1)
export function hasWebGL(): boolean {
    try {
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("webgl2");
        if (!context) {
            return false;
        }
        // se libera enseguida: los navegadores limitan los contextos abiertos
        (context as WebGLRenderingContext).getExtension?.("WEBGL_lose_context")?.loseContext();
        return true;
    } catch {
        return false;
    }
}
