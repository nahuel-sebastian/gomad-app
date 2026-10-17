import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import MapPin from "../components/MapPin";
import MapView, { type MapMarker } from "../components/MapView";
import { withWebGL } from "./mapMock";
import { destinationKind, KIND_ORDER, KIND_STYLES, OUT_OF_SERVICE_COLOR } from "../components/mapIcons";

vi.mock("react-map-gl/maplibre", async () => (await import("./mapMock")).mapLibreModule());
vi.mock("maplibre-gl", async () => (await import("./mapMock")).maplibreModule());

afterEach(() => {
    vi.restoreAllMocks();
});

function luminance(hex: string): number {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const lin = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}

const contrastWithWhite = (hex: string) => 1.05 / (luminance(hex) + 0.05);

describe("iconos del mapa por tipo", () => {
    it("cada tipo tiene etiqueta, color con contraste >= 4,5:1 frente al blanco y trazo", () => {
        expect(KIND_ORDER).toHaveLength(11);
        for (const kind of KIND_ORDER) {
            const style = KIND_STYLES[kind];
            expect(style.label).not.toBe("");
            expect(style.path).toMatch(/^M/);
            expect(contrastWithWhite(style.color)).toBeGreaterThanOrEqual(4.5);
        }
        expect(contrastWithWhite(OUT_OF_SERVICE_COLOR)).toBeGreaterThanOrEqual(4.5);
        // el color no va solo: cada tipo tiene un icono distinto
        expect(new Set(KIND_ORDER.map((k) => KIND_STYLES[k].path)).size).toBe(KIND_ORDER.length);
    });

    it("destinationKind usa el tipo del destino (la piscina la decide la API)", () => {
        expect(destinationKind("facility")).toBe("facility");
        expect(destinationKind("park")).toBe("park");
        expect(destinationKind("algo_raro")).toBe("facility");
        // sin parametro de actividad: «pool_activity» vive solo en config/map.yaml
        expect(destinationKind.length).toBe(1);
    });
});

describe("MapPin", () => {
    it("lleva el icono de su tipo y un texto alternativo con numero, nombre y tipo", () => {
        const { container } = render(<MapPin kind="pool" number={2} name="Piscina Municipal" />);
        const pin = screen.getByRole("img", { name: "2. Piscina Municipal (Piscina)" });
        expect(pin).toHaveClass("map-marker", "map-marker--pin");
        expect(pin).toHaveTextContent("2");
        expect(container.querySelector("svg path")).toHaveAttribute("d", KIND_STYLES.pool.path);
        expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
        expect(pin.style.getPropertyValue("--pin-color")).toBe(KIND_STYLES.pool.color);
    });

    it("el seleccionado lo dice en su texto alternativo", () => {
        render(<MapPin kind="park" number={1} name="Parque Uno" selected />);
        const pin = screen.getByRole("img", { name: "1. Parque Uno (Parque o zona verde), seleccionado" });
        expect(pin).toHaveClass("map-marker--selected");
    });
});

describe("MapView con pines por tipo", () => {
    it("los destinos con tipo se pintan como pin y el seleccionado sigue a la lista", async () => {
        withWebGL();
        const markers: MapMarker[] = [
            { id: "a", number: 1, name: "Parque Uno", kind: "park", coordinate: { lon: -3.728, lat: 40.309 } },
            { id: "b", number: 2, name: "Piscina", kind: "pool", coordinate: { lon: -3.722, lat: 40.302 } },
        ];
        const { container, rerender } = render(<MapView markers={markers} selectedId="a" />);
        await screen.findByTestId("maplibre");
        expect(screen.getByRole("img", { name: "1. Parque Uno (Parque o zona verde), seleccionado" })).toBeInTheDocument();
        expect(screen.getByRole("img", { name: "2. Piscina (Piscina)" })).toBeInTheDocument();
        rerender(<MapView markers={markers} selectedId="b" />);
        expect(container.querySelector(".map-marker--selected")).toHaveTextContent("2");
    });
});
