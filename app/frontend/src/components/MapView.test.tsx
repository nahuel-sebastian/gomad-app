import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { toLineString, type LonLat } from "../lib/geometry";
import { boundsOf, fitPadding, hasWebGL, mapPoints } from "./mapUtils";
import MapView, { MapErrorBoundary, type MapMarker } from "./MapView";
import {
    fitBoundsMock,
    lastMapProps,
    setMapScenario,
    setStyleMock,
    setWorkerUrlMock,
    withWebGL,
} from "../test/mapMock";

// jsdom no tiene WebGL: se simula react-map-gl con componentes de DOM simples
vi.mock("react-map-gl/maplibre", async () => (await import("../test/mapMock")).mapLibreModule());
vi.mock("maplibre-gl", async () => (await import("../test/mapMock")).maplibreModule());

const ORIGIN = { lon: -3.7315, lat: 40.3057 };
const MARKERS: MapMarker[] = [
    { id: "a", number: 1, name: "Parque Castilla-La Mancha", coordinate: { lon: -3.728, lat: 40.309 } },
    { id: "b", number: 2, name: "Polideportivo San Isidro", coordinate: { lon: -3.722, lat: 40.302 } },
];

const MAIN_COORDS: LonLat[] = [
    [-3.7315, 40.3057],
    [-3.73, 40.307],
    [-3.728, 40.309],
];
const MAIN = toLineString(MAIN_COORDS);
const OTHER = toLineString([
    [-3.7315, 40.3057],
    [-3.729, 40.306],
    [-3.728, 40.309],
]);

afterEach(() => {
    vi.restoreAllMocks();
    setMapScenario("ok");
    setStyleMock.mockClear();
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

    it("indica a MapLibre la URL de su worker empaquetado por Vite", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} />);
        await screen.findByTestId("maplibre");
        expect(setWorkerUrlMock).toHaveBeenCalledWith(expect.stringContaining("maplibre-gl-worker"));
    });

    it("muestra la atribucion de OpenStreetMap, OpenMapTiles y OpenFreeMap", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} />);
        expect(await screen.findByText("© OpenStreetMap · OpenMapTiles · OpenFreeMap")).toBeVisible();
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

describe("MapLibre que falla", () => {
    it("hasWebGL solo acepta WebGL2 (MapLibre 6 no usa WebGL1)", () => {
        vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(((type: string) =>
            type === "webgl" ? {} : null) as never);
        expect(hasWebGL()).toBe(false);
    });

    it("si MapLibre no puede crear el mapa vuelve al esquema", async () => {
        withWebGL();
        vi.spyOn(console, "error").mockImplementation(() => {});
        setMapScenario("creation-fails");
        const { container } = render(<MapView markers={MARKERS} origin={ORIGIN} />);
        await waitFor(() => expect(container.querySelector(".map-view__svg")).not.toBeNull());
        expect(screen.queryByTestId("maplibre")).toBeNull();
    });

    it("si no llega el estilo de teselas pone un fondo liso para que se dibuje la ruta", async () => {
        withWebGL();
        setMapScenario("style-fails");
        render(<MapView markers={[]} origin={ORIGIN} route={MAIN} />);
        await screen.findByTestId("maplibre");
        expect(setStyleMock).toHaveBeenCalledTimes(1);
        const style = setStyleMock.mock.calls[0][0];
        expect(style.version).toBe(8);
        expect(style.layers).toEqual([expect.objectContaining({ type: "background" })]);
    });

    it("un fallo de tesela con el estilo ya cargado no cambia el estilo", async () => {
        withWebGL();
        setMapScenario("tile-error");
        render(<MapView markers={MARKERS} />);
        await screen.findByTestId("maplibre");
        expect(setStyleMock).not.toHaveBeenCalled();
    });
});

describe("MapCanvas: ruta", () => {
    it("dibuja la ruta elegida y la otra con capas distintas", async () => {
        withWebGL();
        const { container } = render(
            <MapView markers={[]} origin={ORIGIN} route={MAIN} secondaryRoute={OTHER} />,
        );
        await screen.findByTestId("maplibre");
        const main = container.querySelector("[data-source='route-main']");
        expect(JSON.parse(main!.getAttribute("data-coords")!)).toEqual(MAIN_COORDS);
        expect(container.querySelector("[data-layer='route-main-line']")).not.toBeNull();
        expect(container.querySelector("[data-source='route-secondary']")).not.toBeNull();
        expect(container.querySelector("[data-layer='route-secondary-line']")).not.toBeNull();
    });

    it("sin ruta no hay capas de ruta", async () => {
        withWebGL();
        const { container } = render(<MapView markers={MARKERS} />);
        await screen.findByTestId("maplibre");
        expect(container.querySelector("[data-source^='route-']")).toBeNull();
    });

    it("encuadra la ruta y el origen", () => {
        const [[w, s], [e, n]] = boundsOf(mapPoints({ markers: [], origin: ORIGIN, route: MAIN }))!;
        expect(w).toBeLessThanOrEqual(ORIGIN.lon);
        expect(e).toBeGreaterThanOrEqual(Math.max(...MAIN_COORDS.map((c) => c[0])));
        expect(s).toBeLessThan(n);
    });

    it("reencuadra cuando cambian los puntos", async () => {
        withWebGL();
        const { rerender } = render(<MapView markers={MARKERS.slice(0, 1)} />);
        await screen.findByTestId("maplibre");
        fitBoundsMock.mockClear();
        rerender(<MapView markers={MARKERS} />);
        expect(fitBoundsMock).toHaveBeenCalledTimes(1);
        rerender(<MapView markers={[...MARKERS]} />);
        expect(fitBoundsMock).toHaveBeenCalledTimes(1);
    });
});

describe("MapCanvas: seleccion", () => {
    it("el marcador seleccionado lleva la clase de seleccion", async () => {
        withWebGL();
        const { container } = render(<MapView markers={MARKERS} selectedId={MARKERS[1].id} />);
        await screen.findByTestId("maplibre");
        const selected = container.querySelectorAll(".map-marker--selected");
        expect(selected).toHaveLength(1);
        expect(selected[0]).toHaveTextContent("2");
    });

    it("pulsar un marcador llama a onSelect con su id", async () => {
        withWebGL();
        const onSelect = vi.fn();
        render(<MapView markers={MARKERS} onSelect={onSelect} />);
        fireEvent.click(await screen.findByText("2"));
        expect(onSelect).toHaveBeenCalledWith(MARKERS[1].id);
    });
});

describe("encuadre con margenes", () => {
    it("fitPadding lee los margenes de las variables CSS y si no, 40 px", () => {
        const el = document.createElement("div");
        expect(fitPadding(el)).toEqual({ top: 40, right: 40, bottom: 40, left: 40 });
        el.style.setProperty("--map-fit-top", "116px");
        el.style.setProperty("--map-fit-bottom", "188px");
        document.body.append(el);
        expect(fitPadding(el)).toEqual({ top: 116, right: 40, bottom: 188, left: 40 });
        el.remove();
    });

    it("en movil el encuadre deja sitio a la barra y a la hoja de resultados", async () => {
        withWebGL();
        // jsdom no hereda variables CSS: la regla va sobre el propio contenedor del mapa
        const sheet = document.createElement("style");
        sheet.textContent = ".map-canvas { --map-fit-top: 116px; --map-fit-bottom: 188px; }";
        document.head.append(sheet);
        render(<MapView markers={MARKERS} />);
        await screen.findByTestId("maplibre");
        sheet.remove();
        const view = lastMapProps().initialViewState as { fitBoundsOptions: { padding: unknown } };
        expect(view.fitBoundsOptions.padding).toEqual({ top: 116, right: 40, bottom: 188, left: 40 });
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
