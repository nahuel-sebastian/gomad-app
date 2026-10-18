import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { POI_MIN_ZOOM } from "../components/mapUtils";
import * as recommendModule from "../data/recommend";
import { easeToMock, mapZoom, withWebGL } from "./mapMock";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "./render";

// Seleccion sincronizada lista <-> mapa en Resultados (RF-11) con el mapa de MapLibre simulado
vi.mock("react-map-gl/maplibre", async () => (await import("./mapMock")).mapLibreModule());
vi.mock("maplibre-gl", async () => (await import("./mapMock")).maplibreModule());

const WITH_SEARCH = {
    origin: SAMPLE_ORIGIN,
    search: { activity: "walk", label: "Caminar" },
};

beforeAll(() => {
    // jsdom no implementa scrollIntoView
    Element.prototype.scrollIntoView ??= () => {};
});

afterEach(() => {
    vi.restoreAllMocks();
});

async function cardLinks() {
    const list = await screen.findByRole("list", { name: "Resultados" });
    await screen.findByTestId("maplibre");
    return within(list).getAllByRole("link");
}

function selectedMarker(container: HTMLElement) {
    return container.querySelector(".map-marker--selected");
}

describe("Resultados: lista y mapa sincronizados", () => {
    it("enfocar una tarjeta activa su marcador", async () => {
        withWebGL();
        const { container } = renderAt("/resultados", WITH_SEARCH);
        const links = await cardLinks();
        links[1].focus();
        await waitFor(() => expect(selectedMarker(container)).toHaveTextContent("2"));
    });

    it("pasar el puntero por una tarjeta activa su marcador", async () => {
        withWebGL();
        const { container } = renderAt("/resultados", WITH_SEARCH);
        const links = await cardLinks();
        fireEvent.mouseOver(links[2]);
        await waitFor(() => expect(selectedMarker(container)).toHaveTextContent("3"));
    });

    it("pulsar un marcador lo selecciona y acerca el mapa hasta ver los iconos, sin llevar el foco a la lista", async () => {
        withWebGL();
        easeToMock.mockClear();
        mapZoom.value = 14;
        const { container } = renderAt("/resultados", WITH_SEARCH);
        const links = await cardLinks();
        const marker = [...container.querySelectorAll(".map-marker")].find((m) => m.textContent === "3")!;
        const before = document.activeElement;
        fireEvent.click(marker);
        await waitFor(() => expect(selectedMarker(container)).toHaveTextContent("3"));
        expect(document.activeElement).toBe(before);
        expect(document.activeElement).not.toBe(links[2]);
        expect(easeToMock).toHaveBeenCalledTimes(1);
        const { center, zoom } = easeToMock.mock.calls[0][0];
        expect(zoom).toBe(POI_MIN_ZOOM);
        expect(center).toHaveLength(2);
    });

    it("pulsar un marcador con mas zoom no aleja el mapa", async () => {
        withWebGL();
        easeToMock.mockClear();
        mapZoom.value = POI_MIN_ZOOM + 2;
        const { container } = renderAt("/resultados", WITH_SEARCH);
        await cardLinks();
        const marker = [...container.querySelectorAll(".map-marker")].find((m) => m.textContent === "2")!;
        fireEvent.click(marker);
        expect(easeToMock.mock.calls[0][0].zoom).toBe(POI_MIN_ZOOM + 2);
        mapZoom.value = 14;
    });

    it("axe sin violaciones con el mapa real", async () => {
        withWebGL();
        const { container } = renderAt("/resultados", WITH_SEARCH);
        await cardLinks();
        await expectNoAxeViolations(container);
    });
});

describe("Resultados: ubicacion en tiempo real (C2)", () => {
    const GPS_ORIGIN = { ...SAMPLE_ORIGIN, label: "Tu ubicación" };
    let emit: (lat: number, lon: number) => void = () => {};
    const clearWatch = vi.fn();

    beforeEach(() => {
        vi.stubGlobal("isSecureContext", true);
        Object.defineProperty(navigator, "geolocation", {
            configurable: true,
            value: {
                watchPosition: (ok: PositionCallback) => {
                    emit = (lat, lon) => ok({ coords: { latitude: lat, longitude: lon } } as GeolocationPosition);
                    return 7;
                },
                clearWatch,
                getCurrentPosition: vi.fn(),
            },
        });
    });

    afterEach(() => {
        vi.unstubAllGlobals();
        Reflect.deleteProperty(navigator, "geolocation");
        clearWatch.mockClear();
    });

    it("al alejarse mueve el punto en tiempo real sin ofrecer buscar desde aqui ni recalcular", async () => {
        withWebGL();
        const spy = vi.spyOn(recommendModule, "recommend");
        const { container, unmount } = renderAt("/resultados", { origin: GPS_ORIGIN, search: { activity: "walk", label: "Caminar" } });
        await cardLinks();
        expect(spy).toHaveBeenCalledTimes(1);
        act(() => emit(GPS_ORIGIN.coordinate.lat + 0.0005, GPS_ORIGIN.coordinate.lon));   // ~55 m
        expect(screen.getByRole("img", { name: "Estás aquí (en tiempo real)" })).toBeInTheDocument();
        await new Promise((r) => setTimeout(r, 0));
        // 5 s despues y a ~550 m
        vi.spyOn(Date, "now").mockReturnValue(Date.now() + 10_000);
        act(() => emit(GPS_ORIGIN.coordinate.lat + 0.005, GPS_ORIGIN.coordinate.lon));
        await new Promise((r) => setTimeout(r, 0));
        expect(screen.queryByRole("button", { name: /buscar desde aquí/i })).toBeNull();
        expect(screen.queryByText(/Te has alejado/)).toBeNull();
        expect(container.querySelector(".map-live-offer, .map-live-status")).toBeNull();
        expect(spy).toHaveBeenCalledTimes(1);
        unmount();
        expect(clearWatch).toHaveBeenCalledWith(7);
    });

    it("con una ubicacion escrita no sigue la posicion ni pide permiso", async () => {
        withWebGL();
        const watch = vi.spyOn(navigator.geolocation, "watchPosition");
        renderAt("/resultados", WITH_SEARCH);
        await cardLinks();
        expect(watch).not.toHaveBeenCalled();
    });
});
