import { forwardRef, useImperativeHandle, useRef, type ReactNode } from "react";
import { vi } from "vitest";

// Simulacro de react-map-gl/maplibre para jsdom (sin WebGL): cada componente pinta un
// elemento de DOM con sus datos en atributos para poder comprobarlos.
// Uso: vi.mock("react-map-gl/maplibre", async () => (await import("../test/mapMock")).mapLibreModule());
// y vi.mock("maplibre-gl", async () => (await import("../test/mapMock")).maplibreModule());

type Props = Record<string, unknown> & { children?: ReactNode };

// registra las props de cada render del mapa simulado
const mapPropsMock = vi.fn();

// fitBounds del mapa simulado (lo que llama MapCanvas al reencuadrar)
export const fitBoundsMock = vi.fn();

export function lastMapProps(): Props {
    return mapPropsMock.mock.lastCall?.[0] ?? {};
}

export function mapLibreModule() {
    const Map = forwardRef<unknown, Props>(function MockMap(props, ref) {
        mapPropsMock(props);
        // como MapLibre: el lienzo nace enfocable y onLoad no llega en jsdom
        const canvas = useRef<HTMLCanvasElement>(null);
        useImperativeHandle(ref, () => ({ fitBounds: fitBoundsMock, getCanvas: () => canvas.current }));
        return (
            <div data-testid="maplibre" data-style={String(props.mapStyle)}>
                <canvas ref={canvas} tabIndex={0} aria-label="Map" />
                {props.children as ReactNode}
            </div>
        );
    });
    const Marker = ({ children, onClick, longitude, latitude }: Props) => (
        <div
            data-lon={String(longitude)}
            data-lat={String(latitude)}
            onClick={() =>
                (onClick as ((e: unknown) => void) | undefined)?.({
                    originalEvent: { stopPropagation() {} },
                })
            }>
            {children}
        </div>
    );
    const Source = ({ id, data, children }: Props) => (
        <div
            data-source={String(id)}
            data-coords={JSON.stringify((data as { coordinates?: unknown }).coordinates)}>
            {children}
        </div>
    );
    const Layer = ({ id }: Props) => <div data-layer={String(id)} />;
    return { default: Map, Map, Marker, Source, Layer };
}

// URL del worker que MapCanvas pasa a maplibre-gl (en jsdom no se carga maplibre-gl real)
export const setWorkerUrlMock = vi.fn();

export function maplibreModule() {
    return { setWorkerUrl: setWorkerUrlMock };
}

// Hace que el navegador simulado diga que tiene WebGL
export function withWebGL() {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as never);
}
