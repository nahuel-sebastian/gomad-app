import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
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
