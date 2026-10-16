import { forwardRef, useImperativeHandle, type ReactNode } from "react";
import { vi } from "vitest";

// Simulacro de react-map-gl/maplibre para jsdom (sin WebGL): cada componente pinta un
// elemento de DOM con sus datos en atributos para poder comprobarlos.
// Uso: vi.mock("react-map-gl/maplibre", async () => (await import("../test/mapMock")).mapLibreModule());

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
        useImperativeHandle(ref, () => ({ fitBounds: fitBoundsMock }));
        return (
            <div data-testid="maplibre" data-style={String(props.mapStyle)}>
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

// Hace que el navegador simulado diga que tiene WebGL
export function withWebGL() {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({} as never);
}
