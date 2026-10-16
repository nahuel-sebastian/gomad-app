import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { boundsOf } from "./mapUtils";
import MapView, { MapErrorBoundary, type MapMarker } from "./MapView";
import { lastMapProps, withWebGL } from "../test/mapMock";

// jsdom no tiene WebGL: se simula react-map-gl con componentes de DOM simples
vi.mock("react-map-gl/maplibre", async () => (await import("../test/mapMock")).mapLibreModule());

const ORIGIN = { lon: -3.7315, lat: 40.3057 };
const MARKERS: MapMarker[] = [
    { id: "a", number: 1, name: "Parque Castilla-La Mancha", coordinate: { lon: -3.728, lat: 40.309 } },
    { id: "b", number: 2, name: "Polideportivo San Isidro", coordinate: { lon: -3.722, lat: 40.302 } },
];

afterEach(() => {
    vi.restoreAllMocks();
});

describe("MapView", () => {
    it("sin WebGL dibuja el esquema sin cargar MapLibre", () => {
        const { container } = render(<MapView markers={MARKERS} origin={ORIGIN} />);
        expect(container.querySelector(".map-view__svg")).not.toBeNull();
        expect(screen.queryByTestId("maplibre")).toBeNull();
        expect(screen.getByText("Mapa simplificado (sin teselas)")).toBeInTheDocument();
    });

    it("con WebGL carga el mapa de MapLibre con las teselas de OpenFreeMap", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} origin={ORIGIN} />);
        expect(await screen.findByTestId("maplibre")).toHaveAttribute(
            "data-style",
            "https://tiles.openfreemap.org/styles/liberty",
        );
    });

    it("muestra la atribucion de OpenStreetMap y OpenFreeMap", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} />);
        expect(await screen.findByText("© OpenStreetMap · OpenFreeMap")).toBeVisible();
    });

    it("el mapa esta oculto a lectores y fuera del teclado", async () => {
        withWebGL();
        const { container } = render(<MapView markers={MARKERS} />);
        await screen.findByTestId("maplibre");
        expect(container.querySelector(".map-view")).toHaveAttribute("aria-hidden", "true");
        const props = lastMapProps();
        expect(props.keyboard).toBe(false);
        expect(props.attributionControl).toBe(false);
        expect(
            container.querySelectorAll("button, a, input, [tabindex]:not([tabindex='-1'])"),
        ).toHaveLength(0);
    });

    it("los marcadores no dependen del estilo: uno numerado por destino y el origen", async () => {
        withWebGL();
        const { container } = render(<MapView markers={MARKERS} origin={ORIGIN} />);
        await screen.findByTestId("maplibre");
        const numbers = [...container.querySelectorAll(".map-marker:not(.map-marker--origin)")].map(
            (m) => m.textContent,
        );
        expect(numbers).toEqual(["1", "2"]);
        expect(container.querySelectorAll(".map-marker--origin")).toHaveLength(1);
    });

    it("si MapLibre falla vuelve al esquema", () => {
        vi.spyOn(console, "error").mockImplementation(() => {});
        const Boom = () => {
            throw new Error("WebGL context lost");
        };
        render(
            <MapErrorBoundary fallback={<p>esquema</p>}>
                <Boom />
            </MapErrorBoundary>,
        );
        expect(screen.getByText("esquema")).toBeInTheDocument();
    });
});

describe("boundsOf", () => {
    it("da la caja de los puntos", () => {
        expect(
            boundsOf([
                [-3.73, 40.3],
                [-3.7, 40.32],
            ]),
        ).toEqual([
            [-3.73, 40.3],
            [-3.7, 40.32],
        ]);
    });

    it("con un punto da una caja minima", () => {
        const [[w, s], [e, n]] = boundsOf([[-3.73, 40.3]])!;
        expect(e - w).toBeCloseTo(0.01);
        expect(n - s).toBeCloseTo(0.01);
    });

    it("sin puntos da null", () => {
        expect(boundsOf([])).toBeNull();
    });
});
