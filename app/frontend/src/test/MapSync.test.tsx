import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { LOCATION_MESSAGES } from "../data/geolocation";
import * as recommendModule from "../data/recommend";
import { withWebGL } from "./mapMock";
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

    it("pulsar un marcador lleva el foco a su tarjeta", async () => {
        withWebGL();
        const { container } = renderAt("/resultados", WITH_SEARCH);
        const links = await cardLinks();
        const marker = [...container.querySelectorAll(".map-marker")].find((m) => m.textContent === "3")!;
        fireEvent.click(marker);
        await waitFor(() => expect(document.activeElement).toBe(links[2]));
        expect(selectedMarker(container)).toHaveTextContent("3");
    });

    it("pulsar un marcador lo selecciona aunque la ventana no tenga el foco", async () => {
        withWebGL();
        const { container } = renderAt("/resultados", WITH_SEARCH);
        await cardLinks();
        // sin foco en la ventana, focus() no lanza el evento focus
        vi.spyOn(HTMLElement.prototype, "focus").mockImplementation(() => {});
        const marker = [...container.querySelectorAll(".map-marker")].find((m) => m.textContent === "2")!;
        fireEvent.click(marker);
        await waitFor(() => expect(selectedMarker(container)).toHaveTextContent("2"));
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

    it("ofrece buscar desde aqui al alejarse, no recalcula solo y al pulsarlo cambia el origen", async () => {
        withWebGL();
        const spy = vi.spyOn(recommendModule, "recommend");
        const { unmount } = renderAt("/resultados", { origin: GPS_ORIGIN, search: { activity: "walk", label: "Caminar" } });
        await cardLinks();
        expect(spy).toHaveBeenCalledTimes(1);
        act(() => emit(GPS_ORIGIN.coordinate.lat + 0.0005, GPS_ORIGIN.coordinate.lon));   // ~55 m
        expect(screen.queryByRole("button", { name: /Buscar desde aquí/ })).toBeNull();
        expect(screen.getByRole("img", { name: "Estás aquí (en tiempo real)" })).toBeInTheDocument();
        await new Promise((r) => setTimeout(r, 0));
        // 5 s despues y a ~550 m
        vi.spyOn(Date, "now").mockReturnValue(Date.now() + 10_000);
        act(() => emit(GPS_ORIGIN.coordinate.lat + 0.005, GPS_ORIGIN.coordinate.lon));
        const offer = await screen.findByRole("button", { name: "Te has alejado 560 m: buscar desde aquí" });
        expect(spy).toHaveBeenCalledTimes(1);
        fireEvent.click(offer);
        await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
        expect(spy.mock.calls[1][0].origin).toEqual({ lat: GPS_ORIGIN.coordinate.lat + 0.005, lon: GPS_ORIGIN.coordinate.lon });
        await waitFor(() => expect(screen.queryByRole("button", { name: /buscar desde aquí/ })).toBeNull());
        unmount();
        expect(clearWatch).toHaveBeenCalledWith(7);
    });

    it("el anuncio va aparte del boton y fuera de la Comunidad lo dice sin recalcular", async () => {
        withWebGL();
        const spy = vi.spyOn(recommendModule, "recommend");
        const { container } = renderAt("/resultados", { origin: GPS_ORIGIN, search: { activity: "walk", label: "Caminar" } });
        await cardLinks();
        expect(container.querySelector(".map-live-status")).toBeNull();
        act(() => emit(GPS_ORIGIN.coordinate.lat, GPS_ORIGIN.coordinate.lon));
        const status = container.querySelector(".map-live-status")!;
        expect(status).toHaveAttribute("role", "status");
        expect(status).toHaveTextContent("");
        vi.spyOn(Date, "now").mockReturnValue(Date.now() + 10_000);
        act(() => emit(41.39, 2.17));      // Barcelona, pasado el intervalo
        const offer = await screen.findByRole("button", { name: /buscar desde aquí/ });
        expect(status.querySelector("button")).toBeNull();
        expect(offer.closest("[role='status']")).toBeNull();
        expect(status).toHaveTextContent(/Te has alejado/);
        fireEvent.click(offer);
        await waitFor(() => expect(status).toHaveTextContent(LOCATION_MESSAGES.outside));
        expect(spy).toHaveBeenCalledTimes(1);
    });

    it("con una ubicacion escrita no sigue la posicion ni pide permiso", async () => {
        withWebGL();
        const watch = vi.spyOn(navigator.geolocation, "watchPosition");
        renderAt("/resultados", WITH_SEARCH);
        await cardLinks();
        expect(watch).not.toHaveBeenCalled();
    });
});
