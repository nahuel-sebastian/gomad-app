import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import MapView from "../components/MapView";
import * as mapPointsModule from "../data/mapPoints";
import { NAV_ZOOM } from "../data/navigation";
import { toLineString } from "../lib/geometry";
import { easeToMock, lastMapProps, mapZoom, withWebGL } from "./mapMock";

// El mapa sigue la ubicacion en modo navegacion (Task 183), con MapLibre simulado
vi.mock("react-map-gl/maplibre", async () => (await import("./mapMock")).mapLibreModule());
vi.mock("maplibre-gl", async () => (await import("./mapMock")).maplibreModule());

const ROUTE = toLineString([
    [-3.7329, 40.3057],
    [-3.7229, 40.3057],
]);
const P1 = { lat: 40.3057, lon: -3.73 };
const P2 = { lat: 40.3058, lon: -3.729 };

beforeEach(() => {
    withWebGL();
    easeToMock.mockClear();
    mapZoom.value = 14;
});

afterEach(() => {
    vi.restoreAllMocks();
});

async function renderMap(props: Partial<Parameters<typeof MapView>[0]>) {
    const view = render(<MapView markers={[]} route={ROUTE} {...props} />);
    await screen.findByTestId("maplibre");
    return view;
}

describe("MapView: seguir la ubicacion", () => {
    it("con follow y live, la camara va a cada posicion nueva con zoom de navegacion", async () => {
        const { rerender } = await renderMap({ follow: true, live: P1 });
        expect(easeToMock).toHaveBeenLastCalledWith(
            expect.objectContaining({ center: [P1.lon, P1.lat], zoom: NAV_ZOOM }),
        );
        mapZoom.value = 18;
        rerender(<MapView markers={[]} route={ROUTE} follow live={P2} />);
        expect(easeToMock).toHaveBeenLastCalledWith(
            expect.objectContaining({ center: [P2.lon, P2.lat], zoom: 18 }),
        );
    });

    it("sin follow, moverse no mueve la camara", async () => {
        const { rerender } = await renderMap({ live: P1 });
        rerender(<MapView markers={[]} route={ROUTE} live={P2} />);
        expect(easeToMock).not.toHaveBeenCalled();
    });

    it("arrastrar o hacer zoom con la mano avisa; el movimiento programado no", async () => {
        const onUserMove = vi.fn();
        await renderMap({ follow: true, live: P1, onUserMove });
        const props = lastMapProps() as Record<string, (e: unknown) => void>;
        act(() => props.onDragStart({ type: "dragstart" }));
        act(() => props.onZoomStart({ type: "zoomstart" }));
        expect(onUserMove).not.toHaveBeenCalled();
        act(() => props.onDragStart({ type: "dragstart", originalEvent: new Event("mousedown") }));
        act(() => props.onZoomStart({ type: "zoomstart", originalEvent: new Event("wheel") }));
        expect(onUserMove).toHaveBeenCalledTimes(2);
    });
});

describe("MapView: seguir la ubicacion sin enviarla", () => {
    const view = {
        getZoom: () => 17,
        getBounds: () => ({ getWest: () => -3.731, getSouth: () => 40.305, getEast: () => -3.729, getNorth: () => 40.306 }),
    };
    const wait = () => act(() => new Promise((r) => setTimeout(r, 400)));

    it("mientras sigue, los movimientos programados no piden puntos de la zona", async () => {
        const spy = vi.spyOn(mapPointsModule, "getMapPoints");
        await renderMap({ follow: true, live: P1, explore: true });
        const props = lastMapProps() as Record<string, (e: unknown) => void>;
        act(() => props.onMoveEnd({ type: "moveend", target: view }));
        await wait();
        expect(spy).not.toHaveBeenCalled();
        // lo que mueve la persona si pide puntos, como siempre
        act(() => props.onMoveEnd({ type: "moveend", target: view, originalEvent: new Event("mouseup") }));
        await wait();
        expect(spy).toHaveBeenCalledOnce();
    });

    it("los botones de zoom sueltan el seguimiento", async () => {
        const onUserMove = vi.fn();
        await renderMap({ follow: true, live: P1, onUserMove });
        act(() => screen.getByRole("button", { name: "Alejar mapa" }).click());
        expect(onUserMove).toHaveBeenCalledOnce();
    });
});
