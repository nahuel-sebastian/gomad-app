import { act, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MapPoint, MapPointsResponse } from "../api/types";
import { KIND_ORDER, KIND_STYLES, OUT_OF_SERVICE_COLOR } from "../components/mapIcons";
import MapLegend from "../components/MapLegend";
import { pinImage, pinImageSpec } from "../components/mapPinImage";
import * as pinImages from "../components/mapPinImage";
import {
    EXPLORE_FIT_MAX_ZOOM,
    FIT_MAX_ZOOM,
    nearbyFeatures,
    nearbyRequest,
    NEARBY_DEBOUNCE_MS,
    NEARBY_MIN_ZOOM,
    POI_MIN_ZOOM,
} from "../components/mapUtils";
import MapView, { type MapMarker } from "../components/MapView";
import * as mapPointsModule from "../data/mapPoints";
import { easeToMock, fitBoundsMock, lastMapProps, withWebGL } from "./mapMock";
import { expectNoAxeViolations } from "./render";

vi.mock("react-map-gl/maplibre", async () => (await import("./mapMock")).mapLibreModule());
vi.mock("maplibre-gl", async () => (await import("./mapMock")).maplibreModule());

const MARKERS: MapMarker[] = [
    { id: "r1", number: 1, name: "Resultado", kind: "park", coordinate: { lon: -3.7329, lat: 40.3057 } },
];
const OLD_POINT: MapPoint = {
    id: "viejo",
    kind: "park",
    name: "Viejo",
    coordinate: { lat: 40.3, lon: -3.73 },
    working: null,
    source: "x",
};

const BOUNDS = { west: -3.745, south: 40.298, east: -3.72, north: 40.313 };

function point(id: string, kind: MapPoint["kind"], working: boolean | null = null): MapPoint {
    return { id, kind, name: kind === "park" ? "Parque" : null, coordinate: { lat: 40.3, lon: -3.73 }, working, source: "x" };
}

describe("que pedir segun el zoom", () => {
    it("por debajo del zoom minimo no pide nada", () => {
        expect(nearbyRequest(NEARBY_MIN_ZOOM - 0.1, BOUNDS)).toBeNull();
    });

    it("entre los dos zooms pide solo destinos", () => {
        const req = nearbyRequest(NEARBY_MIN_ZOOM, BOUNDS)!;
        expect(req.bbox).toEqual([-3.745, 40.298, -3.72, 40.313]);
        expect(req.kinds).toEqual(["facility", "pool", "park", "recreation_area", "trail", "bathing_area"]);
    });

    it("de cerca pide tambien fuentes, bancos, papeleras, desfibriladores, areas caninas y juegos", () => {
        const req = nearbyRequest(POI_MIN_ZOOM, BOUNDS)!;
        expect(req.kinds).toEqual(
            expect.arrayContaining(["park", "fountain", "bench", "bin", "aed", "dog_area", "playground"]),
        );
    });

    it("quita los destinos ya numerados y marca las fuentes fuera de servicio", () => {
        const fc = nearbyFeatures([point("a", "park"), point("b", "fountain", false), point("c", "bench")], ["a"]);
        expect(fc.type).toBe("FeatureCollection");
        expect(fc.features.map((f) => f.properties.id)).toEqual(["b", "c"]);
        expect(fc.features[0].properties).toMatchObject({ kind: "fountain", icon: "pin-off-fountain", working: false });
        expect(fc.features[1].properties).toMatchObject({ kind: "bench", icon: "pin-bench" });
        expect(fc.features[1].geometry).toEqual({ type: "Point", coordinates: [-3.73, 40.3] });
    });
});

// --- Task 146: capa de puntos cercanos (sin grupos) ---
describe("MapView explorable", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    function fakeMap(zoom: number, bounds = BOUNDS) {
        return {
            getZoom: () => zoom,
            getBounds: () => ({
                getWest: () => bounds.west,
                getSouth: () => bounds.south,
                getEast: () => bounds.east,
                getNorth: () => bounds.north,
            }),
            easeTo: vi.fn(),
        };
    }

    async function moveTo(zoom: number, bounds = BOUNDS) {
        const target = fakeMap(zoom, bounds);
        await act(async () => {
            (lastMapProps().onMoveEnd as (e: unknown) => void)({ target });
        });
        return target;
    }

    function nearbySource(container: HTMLElement) {
        return container.querySelector('[data-source="nearby"]');
    }

    it("al mover el mapa a zoom cercano pide y pinta los puntos de la zona", async () => {
        withWebGL();
        const spy = vi.spyOn(mapPointsModule, "getMapPoints");
        const { container } = render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        await moveTo(POI_MIN_ZOOM);
        await waitFor(() => expect(nearbySource(container)).toHaveAttribute("data-count", "10"));
        expect(spy).toHaveBeenCalledTimes(1);
        expect(spy.mock.calls[0][0]).toEqual([BOUNDS.west, BOUNDS.south, BOUNDS.east, BOUNDS.north]);
        // sin grupos numerados: solo los iconos de cada punto
        expect(nearbySource(container)).toHaveAttribute("data-cluster", "false");
        expect(container.querySelector('[data-layer="nearby-points"]')).not.toBeNull();
        expect(container.querySelector('[data-layer="nearby-clusters"]')).toBeNull();
        expect(container.querySelector('[data-layer="nearby-count"]')).toBeNull();
    });

    it("al pulsar un destino registra las imágenes y muestra bancos y papeleras", async () => {
        withWebGL();
        const user = userEvent.setup();
        const loaded = new Set<string>();
        const addImage = vi.fn((id: string) => loaded.add(id));
        vi.spyOn(pinImages, "pinImage").mockReturnValue({} as ImageData);
        vi.spyOn(mapPointsModule, "getMapPoints").mockResolvedValue({
            points: [point("b", "bench"), point("p", "bin")],
            truncated: false,
            clipped: false,
        });
        const { container } = render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        await act(async () => {
            (lastMapProps().onLoad as (e: unknown) => void)({
                target: {
                    getStyle: () => ({ layers: [] }),
                    setLayoutProperty: vi.fn(),
                    hasImage: (id: string) => loaded.has(id),
                    addImage,
                    ...fakeMap(EXPLORE_FIT_MAX_ZOOM),
                },
            });
        });
        expect(addImage).toHaveBeenCalledTimes(KIND_ORDER.length * 2);
        expect(loaded).toContain("pin-bench");
        expect(loaded).toContain("pin-bin");
        await user.click(screen.getByRole("img", { name: /Resultado/ }));
        expect(easeToMock).toHaveBeenCalledWith(expect.objectContaining({ zoom: POI_MIN_ZOOM }));
        await moveTo(POI_MIN_ZOOM);
        await waitFor(() => expect(nearbySource(container)).toHaveAttribute("data-count", "2"));
    });

    it("carga los puntos cercanos sin depender de la fuente de iconos", async () => {
        withWebGL();
        const originalFonts = Object.getOwnPropertyDescriptor(document, "fonts");
        Object.defineProperty(document, "fonts", {
            configurable: true,
            value: { load: () => new Promise<FontFace[]>(() => {}) },
        });
        try {
            const { container } = render(<MapView markers={MARKERS} explore />);
            await screen.findByTestId("maplibre");
            await moveTo(POI_MIN_ZOOM);
            await waitFor(() => expect(nearbySource(container)).toHaveAttribute("data-count", "10"));
            expect(container.querySelector('[data-layer="nearby-points"]')).not.toBeNull();
        } finally {
            if (originalFonts) Object.defineProperty(document, "fonts", originalFonts);
            else Reflect.deleteProperty(document, "fonts");
        }
    });

    it("el encuadre inicial se queda por debajo del zoom de los puntos informativos: salen al acercar", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        const view = lastMapProps().initialViewState as { fitBoundsOptions: { maxZoom: number } };
        expect(view.fitBoundsOptions.maxZoom).toBe(EXPLORE_FIT_MAX_ZOOM);
        expect(EXPLORE_FIT_MAX_ZOOM).toBeLessThan(NEARBY_MIN_ZOOM);
        expect(nearbyRequest(EXPLORE_FIT_MAX_ZOOM, BOUNDS)).toBeNull();
        expect(nearbyRequest(EXPLORE_FIT_MAX_ZOOM + 1, BOUNDS)).not.toBeNull();
    });

    it("el mapa no explorable mantiene su encuadre", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} />);
        await screen.findByTestId("maplibre");
        const view = lastMapProps().initialViewState as { fitBoundsOptions: { maxZoom: number } };
        expect(view.fitBoundsOptions.maxZoom).toBe(FIT_MAX_ZOOM);
    });

    it("no repite como punto el destino que ya tiene pin numerado", async () => {
        withWebGL();
        const markers: MapMarker[] = [
            { id: "ejemplo:mapa-parque-1", number: 1, name: "Parque", kind: "park", coordinate: { lon: -3.7355, lat: 40.3071 } },
        ];
        const { container } = render(<MapView markers={markers} explore />);
        await screen.findByTestId("maplibre");
        await moveTo(NEARBY_MIN_ZOOM);
        // 4 destinos de ejemplo en la caja menos el ya numerado
        await waitFor(() => expect(nearbySource(container)).toHaveAttribute("data-count", "3"));
    });

    it("a poco zoom no pide puntos y quita los que habia", async () => {
        withWebGL();
        const spy = vi.spyOn(mapPointsModule, "getMapPoints");
        const { container } = render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        await moveTo(POI_MIN_ZOOM);
        await waitFor(() => expect(nearbySource(container)).not.toBeNull());
        await moveTo(NEARBY_MIN_ZOOM - 1);
        await waitFor(() => expect(nearbySource(container)).toBeNull());
        expect(spy).toHaveBeenCalledTimes(1);
    });

    it("descarta una respuesta vieja", async () => {
        withWebGL();
        let resolveFirst: (v: MapPointsResponse) => void = () => {};
        const spy = vi
            .spyOn(mapPointsModule, "getMapPoints")
            .mockImplementationOnce(() => new Promise((resolve) => (resolveFirst = resolve)))
            .mockResolvedValueOnce({ points: [], truncated: false, clipped: false });
        const { container } = render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        await moveTo(POI_MIN_ZOOM);
        await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
        await moveTo(POI_MIN_ZOOM + 1);
        await waitFor(() => expect(nearbySource(container)).toHaveAttribute("data-count", "0"));
        await act(async () => {
            resolveFirst({ points: [OLD_POINT], truncated: false, clipped: false });
        });
        expect(nearbySource(container)).toHaveAttribute("data-count", "0");
    });

    it("sin explore no pide nada", async () => {
        withWebGL();
        const spy = vi.spyOn(mapPointsModule, "getMapPoints");
        const { container } = render(<MapView markers={MARKERS} />);
        await screen.findByTestId("maplibre");
        await moveTo(POI_MIN_ZOOM);
        await new Promise((r) => setTimeout(r, NEARBY_DEBOUNCE_MS + 50));
        expect(spy).not.toHaveBeenCalled();
        expect(nearbySource(container)).toBeNull();
    });

    it("pulsar un punto muestra su nombre y tipo; una fuente fuera de servicio lo dice", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        const click = (properties: object) =>
            act(async () => {
                (lastMapProps().onClick as (e: unknown) => void)({
                    features: [{ properties, geometry: { type: "Point", coordinates: [-3.73, 40.3] } }],
                    target: fakeMap(16),
                });
            });
        await click({ id: "p", kind: "park", name: "Parque del Sol", working: null });
        expect(screen.getByRole("status")).toHaveTextContent("Parque o zona verde: Parque del Sol");
        await click({ id: "f", kind: "fountain", name: null, working: false });
        expect(screen.getByRole("status")).toHaveTextContent("Fuente (fuera de servicio)");
    });

});

describe("imagenes de los pines para MapLibre", () => {
    it("reconoce los nombres de imagen de los pines", () => {
        expect(pinImageSpec("pin-park")).toEqual({ kind: "park", color: KIND_STYLES.park.color });
        expect(pinImageSpec("pin-off-fountain")).toEqual({ kind: "fountain", color: OUT_OF_SERVICE_COLOR });
        expect(pinImageSpec("pin-casino")).toBeNull();
        expect(pinImageSpec("otra-cosa")).toBeNull();
    });

    it("sin lienzo 2D no dibuja nada", () => {
        expect(pinImage("pin-park")).toBeNull();
    });

    it("dibuja los cuatro iconos nuevos cuando la fuente está lista", () => {
        const ctx = {
            scale: vi.fn(), translate: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), closePath: vi.fn(),
            fill: vi.fn(), arc: vi.fn(), stroke: vi.fn(), fillText: vi.fn(),
            getImageData: vi.fn(() => ({ width: 44, height: 54, data: new Uint8ClampedArray(9504) })),
        };
        vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(ctx as unknown as CanvasRenderingContext2D);
        vi.stubGlobal("Path2D", class {});
        try {
            for (const [kind, glyph] of [["aed", "\ue91e"], ["bench", "\ue91a"], ["playground", "\ue92c"], ["trail", "\ue924"]] as const) {
                expect(pinImage(`pin-${kind}`, true)).not.toBeNull();
                expect(ctx.fillText).toHaveBeenLastCalledWith(glyph, 11, 11);
            }
            ctx.fillText.mockClear();
            expect(pinImage("pin-bench")).not.toBeNull();
            expect(ctx.fillText).not.toHaveBeenCalled();
        } finally {
            vi.restoreAllMocks();
            vi.unstubAllGlobals();
        }
    });
});

// --- Task 147: leyenda accesible ---
describe("leyenda del mapa", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("las papeleras salen en la leyenda con su icono y su nombre", async () => {
        const user = userEvent.setup();
        render(<MapLegend markerKinds={[]} points={[point("p", "bin"), point("q", "bin")]} zoom={POI_MIN_ZOOM} truncated={false} />);
        await user.click(screen.getByRole("button", { name: "Leyenda del mapa" }));
        const list = screen.getByRole("list", { name: "Tipos de lugar en el mapa" });
        expect(within(list).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["Papelera: 2"]);
    });

    it("lista los tipos visibles con icono, texto y recuento", async () => {
        const user = userEvent.setup();
        const { container } = render(
            <MapLegend
                markerKinds={["park"]}
                points={[point("a", "park"), point("b", "fountain", false), point("c", "fountain"), point("d", "bench")]}
                zoom={POI_MIN_ZOOM}
                truncated={false}
            />,
        );
        const button = screen.getByRole("button", { name: "Leyenda del mapa" });
        expect(button).toHaveAttribute("aria-haspopup", "dialog");
        await user.click(button);
        const list = screen.getByRole("list", { name: "Tipos de lugar en el mapa" });
        const items = within(list).getAllByRole("listitem").map((li) => li.textContent);
        expect(items).toEqual([
            "Parque o zona verde: 2",
            "Fuente: 2",
            "Banco: 1",
            "Fuente fuera de servicio: 1",
        ]);
        expect(container.querySelectorAll(".map-legend__icon .icon[aria-hidden='true']").length).toBe(4);
    });

    it("el boton abre la leyenda en una ventana y «Cerrar» la cierra", async () => {
        const user = userEvent.setup();
        render(<MapLegend markerKinds={["park"]} points={[]} zoom={null} truncated={false} />);
        expect(screen.queryByRole("dialog")).toBeNull();
        await user.click(screen.getByRole("button", { name: "Leyenda del mapa" }));
        const dialog = screen.getByRole("dialog", { name: "Leyenda del mapa" });
        expect(within(dialog).getByText("Parque o zona verde: 1")).toBeInTheDocument();
        await user.click(within(dialog).getByRole("button", { name: "Cerrar" }));
        expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("con legendSlot el boton va fuera del mapa (junto a «Ajustar» en Resultados)", async () => {
        withWebGL();
        const slot = document.createElement("div");
        document.body.appendChild(slot);
        const { container } = render(<MapView markers={MARKERS} explore legendSlot={slot} />);
        await screen.findByTestId("maplibre");
        expect(within(slot).getByRole("button", { name: "Leyenda del mapa" })).toBeInTheDocument();
        expect(container.querySelector(".map-panels .map-legend-button")).toBeNull();
        slot.remove();
    });

    it("con legendSlot null (sin sitio todavia) no pinta la leyenda", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} explore legendSlot={null} />);
        await screen.findByTestId("maplibre");
        expect(screen.queryByRole("button", { name: "Leyenda del mapa" })).toBeNull();
    });

    it("fuera de servicio con la etiqueta y el icono de su tipo", () => {
        const { container } = render(
            <MapLegend markerKinds={[]} points={[point("b", "bench", false)]} zoom={null} truncated={false} />,
        );
        const item = screen.getByText("Banco fuera de servicio: 1");
        expect(item.querySelector(".icon-bench")).toBeInTheDocument();
        expect(container.textContent).not.toContain("Fuente fuera de servicio");
    });

    it("pide acercar el mapa a poco zoom y avisa si hay mas lugares", () => {
        const { rerender } = render(<MapLegend markerKinds={["park"]} points={[]} zoom={NEARBY_MIN_ZOOM - 1} truncated={false} />);
        expect(screen.getByText("Acerca el mapa para ver más lugares de la zona.")).toBeInTheDocument();
        rerender(<MapLegend markerKinds={["park"]} points={[]} zoom={NEARBY_MIN_ZOOM} truncated={false} />);
        expect(
            screen.getByText(
                "Acerca más para ver fuentes, bancos, papeleras, juegos, desfibriladores y áreas caninas (solo donde hay datos).",
            ),
        ).toBeInTheDocument();
        rerender(<MapLegend markerKinds={[]} points={[point("a", "park")]} zoom={POI_MIN_ZOOM} truncated />);
        expect(screen.getByText("Hay más lugares de los que se ven: acerca el mapa.")).toBeInTheDocument();
    });

    it("de cerca avisa de la cobertura y de los tipos sin datos en la zona", () => {
        render(
            <MapLegend
                markerKinds={[]}
                points={[point("a", "park"), point("b", "fountain"), point("c", "bench")]}
                zoom={POI_MIN_ZOOM}
                truncated={false}
                checkedPoiKinds={["fountain", "bench", "aed", "dog_area", "playground"]}
            />,
        );
        expect(
            screen.getByText("Fuentes, bancos, papeleras, juegos, desfibriladores y áreas caninas: solo donde hay datos."),
        ).toBeInTheDocument();
        expect(
            screen.getByText("Sin datos en esta zona: Desfibrilador, Área canina, Juegos infantiles."),
        ).toBeInTheDocument();
    });

    it("no dice sin datos si la respuesta no comprobo esos tipos o esta truncada", () => {
        const pts = [point("a", "park")];
        const { rerender } = render(
            <MapLegend markerKinds={[]} points={pts} zoom={POI_MIN_ZOOM} truncated={false} checkedPoiKinds={[]} />,
        );
        expect(screen.queryByText(/Sin datos en esta zona/)).toBeNull();
        rerender(
            <MapLegend markerKinds={[]} points={pts} zoom={POI_MIN_ZOOM} truncated checkedPoiKinds={["fountain", "bench"]} />,
        );
        expect(screen.queryByText(/Sin datos en esta zona/)).toBeNull();
        rerender(
            <MapLegend markerKinds={[]} points={pts} zoom={POI_MIN_ZOOM} truncated={false} checkedPoiKinds={["fountain", "bench"]} />,
        );
        expect(screen.getByText("Sin datos en esta zona: Fuente, Banco.")).toBeInTheDocument();
    });

    it("al acercar de 14 a 15 no dice sin datos mientras llega la respuesta ni si falla", async () => {
        withWebGL();
        const spy = vi.spyOn(mapPointsModule, "getMapPoints");
        render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        const move = (zoom: number) =>
            act(async () => {
                (lastMapProps().onMoveEnd as (e: unknown) => void)({
                    target: {
                        getZoom: () => zoom,
                        getBounds: () => ({
                            getWest: () => BOUNDS.west,
                            getSouth: () => BOUNDS.south,
                            getEast: () => BOUNDS.east,
                            getNorth: () => BOUNDS.north,
                        }),
                    },
                });
            });
        await move(POI_MIN_ZOOM - 1);
        await waitFor(() => expect(spy).toHaveBeenCalledTimes(1));
        await screen.findByText("Parque o zona verde: 3");
        // la siguiente peticion no llega: durante la espera no hay que afirmar nada
        spy.mockImplementationOnce(() => new Promise(() => {}));
        await move(POI_MIN_ZOOM);
        await waitFor(() => expect(spy).toHaveBeenCalledTimes(2));
        expect(screen.queryByText(/Sin datos en esta zona/)).toBeNull();
        // y si falla (sin red), tampoco
        spy.mockRejectedValueOnce(new Error("sin red"));
        await move(POI_MIN_ZOOM + 1);
        await waitFor(() => expect(spy).toHaveBeenCalledTimes(3));
        await new Promise((r) => setTimeout(r, 0));
        expect(screen.queryByText(/Sin datos en esta zona/)).toBeNull();
    });

    it("incluye Estas aqui cuando hay posicion en tiempo real", () => {
        render(<MapLegend markerKinds={[]} points={[]} zoom={null} truncated={false} live />);
        expect(screen.getByText("Estás aquí (en tiempo real)")).toBeInTheDocument();
    });

    it("axe sin violaciones con puntos y leyenda en el mapa", async () => {
        withWebGL();
        const { container } = render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        await act(async () => {
            (lastMapProps().onMoveEnd as (e: unknown) => void)({
                target: {
                    getZoom: () => POI_MIN_ZOOM,
                    getBounds: () => ({
                        getWest: () => BOUNDS.west,
                        getSouth: () => BOUNDS.south,
                        getEast: () => BOUNDS.east,
                        getNorth: () => BOUNDS.north,
                    }),
                },
            });
        });
        await waitFor(() => expect(screen.getByText("Banco: 1")).toBeInTheDocument());
        await expectNoAxeViolations(container);
    });
});

// --- Task 149: «Estas aqui» en tiempo real ---
describe("Estas aqui en el mapa", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("dibuja Estas aqui sin reencuadrar al moverse", async () => {
        withWebGL();
        const live = { lat: 40.306, lon: -3.733 };
        const { rerender } = render(<MapView markers={MARKERS} live={live} />);
        await screen.findByTestId("maplibre");
        expect(screen.getByRole("img", { name: "Estás aquí (en tiempo real)" })).toHaveClass("map-marker--live");
        fitBoundsMock.mockClear();
        rerender(<MapView markers={MARKERS} live={{ lat: 40.31, lon: -3.74 }} />);
        expect(fitBoundsMock).not.toHaveBeenCalled();
        expect(screen.getByText("Estás aquí (en tiempo real)", { selector: "li" })).toBeInTheDocument();
    });

    it("sin WebGL el esquema tambien marca Estas aqui", () => {
        const { container } = render(<MapView markers={MARKERS} live={{ lat: 40.306, lon: -3.733 }} />);
        expect(container.querySelector(".map-view__live")).not.toBeNull();
    });

    it("con posicion en tiempo real no pinta tambien el pin del origen", async () => {
        withWebGL();
        const origin = { lat: 40.3057, lon: -3.7315 };
        const { container, rerender } = render(<MapView markers={MARKERS} origin={origin} />);
        await screen.findByTestId("maplibre");
        expect(container.querySelectorAll(".map-marker--origin")).toHaveLength(1);
        fitBoundsMock.mockClear();
        rerender(<MapView markers={MARKERS} origin={origin} live={{ lat: 40.306, lon: -3.733 }} />);
        expect(container.querySelectorAll(".map-marker--origin")).toHaveLength(0);
        expect(container.querySelectorAll(".map-marker--live")).toHaveLength(1);
        // el origen sigue en el encuadre: que llegue la posicion no reencuadra
        expect(fitBoundsMock).not.toHaveBeenCalled();
    });

    it("sin WebGL tampoco se duplica: solo el punto en tiempo real", () => {
        const { container } = render(
            <MapView markers={MARKERS} origin={{ lat: 40.3057, lon: -3.7315 }} live={{ lat: 40.306, lon: -3.733 }} />,
        );
        expect(container.querySelector(".map-view__origin")).toBeNull();
        expect(container.querySelector(".map-view__live")).not.toBeNull();
    });
});

// --- Task 152: el pin de un resultado toma el tipo que da la API (verificador) ---
describe("tipo del pin de un resultado", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("una instalacion que la API marca como piscina se pinta como piscina", async () => {
        withWebGL();
        const markers: MapMarker[] = [
            { id: "ejemplo:mapa-piscina", number: 1, name: "Piscina", kind: "facility", coordinate: { lon: -3.7262, lat: 40.3088 } },
        ];
        render(<MapView markers={markers} explore />);
        await screen.findByTestId("maplibre");
        expect(screen.getByRole("img", { name: "1. Piscina (Instalación deportiva)" })).toBeInTheDocument();
        await act(async () => {
            (lastMapProps().onMoveEnd as (e: unknown) => void)({
                target: {
                    getZoom: () => NEARBY_MIN_ZOOM,
                    getBounds: () => ({
                        getWest: () => BOUNDS.west,
                        getSouth: () => BOUNDS.south,
                        getEast: () => BOUNDS.east,
                        getNorth: () => BOUNDS.north,
                    }),
                },
            });
        });
        expect(await screen.findByRole("img", { name: "1. Piscina (Piscina)" })).toBeInTheDocument();
    });
});

// --- Etiqueta del punto pegada al icono: al pasar el raton o al pulsar (sustituye a «Lugares a la vista») ---
describe("etiqueta del punto en el mapa", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    const POINTS: MapPoint[] = [
        { ...point("b", "bench"), name: "Plaza Mayor", coordinate: { lat: 40.301, lon: -3.731 } },
        { ...point("f", "fountain", false), coordinate: { lat: 40.302, lon: -3.732 } },
    ];

    // mapa explorable con POINTS cargados en la capa
    async function showPoints() {
        withWebGL();
        vi.spyOn(mapPointsModule, "getMapPoints").mockResolvedValue({ points: POINTS, truncated: false, clipped: false });
        const view = render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        await act(async () => {
            (lastMapProps().onMoveEnd as (e: unknown) => void)({
                target: {
                    getZoom: () => POI_MIN_ZOOM,
                    getBounds: () => ({
                        getWest: () => BOUNDS.west,
                        getSouth: () => BOUNDS.south,
                        getEast: () => BOUNDS.east,
                        getNorth: () => BOUNDS.north,
                    }),
                },
            });
        });
        await waitFor(() =>
            expect(view.container.querySelector('[data-source="nearby"]')).toHaveAttribute("data-count", "2"),
        );
        return view;
    }

    function event(p: MapPoint | null) {
        return {
            features: p
                ? [
                      {
                          properties: { id: p.id, kind: p.kind, name: p.name, working: p.working },
                          geometry: { type: "Point", coordinates: [p.coordinate.lon, p.coordinate.lat] },
                      },
                  ]
                : [],
            point: { x: 10, y: 10 },
        };
    }

    const hover = (p: MapPoint | null) => act(() => (lastMapProps().onMouseMove as (e: unknown) => void)(event(p)));
    const tap = (p: MapPoint | null) => act(() => (lastMapProps().onClick as (e: unknown) => void)(event(p)));
    const popup = (container: HTMLElement) => container.querySelector<HTMLElement>("[data-popup]");

    it("ya no hay boton de «Lugares a la vista» ni recuadro visible abajo", async () => {
        const { container } = await showPoints();
        expect(screen.queryByRole("button", { name: /Lugares a la vista/ })).toBeNull();
        expect(screen.getByRole("status")).toHaveClass("sr-only");
        expect(popup(container)).toBeNull();
    });

    it("al pasar el raton sale pegada al icono (sus coordenadas) y se quita al salir", async () => {
        const { container } = await showPoints();
        expect(lastMapProps().interactiveLayerIds).toEqual(["nearby-points"]);
        hover(POINTS[0]);
        expect(popup(container)).toHaveTextContent("Banco: Plaza Mayor");
        expect(popup(container)).toHaveClass("map-point-popup");
        expect(popup(container)).toHaveAttribute("data-lon", "-3.731");
        expect(popup(container)).toHaveAttribute("data-lat", "40.301");
        expect(lastMapProps().cursor).toBe("pointer");
        hover(POINTS[1]);
        expect(popup(container)).toHaveTextContent("Fuente (fuera de servicio)");
        hover(null);
        expect(popup(container)).toBeNull();
        hover(POINTS[0]);
        act(() => (lastMapProps().onMouseLeave as () => void)());
        expect(popup(container)).toBeNull();
        expect(lastMapProps().cursor).toBeUndefined();
    });

    it("al pulsar (con el dedo) se queda, se anuncia y se quita al pulsar fuera", async () => {
        const { container } = await showPoints();
        tap(POINTS[0]);
        expect(popup(container)).toHaveTextContent("Banco: Plaza Mayor");
        expect(screen.getByRole("status")).toHaveTextContent("Banco: Plaza Mayor");
        // el raton que sale no la quita: esta fijada
        act(() => (lastMapProps().onMouseLeave as () => void)());
        hover(null);
        expect(popup(container)).toHaveTextContent("Banco: Plaza Mayor");
        tap(null);
        expect(popup(container)).toBeNull();
        expect(screen.getByRole("status")).toHaveTextContent("");
    });

    it("el mapa no explorable no escucha el raton", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} />);
        await screen.findByTestId("maplibre");
        expect(lastMapProps().onMouseMove).toBeUndefined();
    });

    it("axe sin violaciones con la etiqueta visible", async () => {
        const { container } = await showPoints();
        hover(POINTS[0]);
        await expectNoAxeViolations(container);
    });
});

// --- La leyenda cuenta lo mismo que se ve en el mapa ---
describe("leyenda y mapa coinciden", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    const POINTS: MapPoint[] = [
        { ...point("b1", "bench"), coordinate: { lat: 40.301, lon: -3.731 } },
        { ...point("b2", "bench"), coordinate: { lat: 40.302, lon: -3.731 } },
        { ...point("f1", "fountain"), coordinate: { lat: 40.303, lon: -3.731 } },
    ];

    async function showPoints() {
        withWebGL();
        vi.spyOn(mapPointsModule, "getMapPoints").mockResolvedValue({ points: POINTS, truncated: false, clipped: false });
        const view = render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        await act(async () => {
            (lastMapProps().onMoveEnd as (e: unknown) => void)({
                target: {
                    getZoom: () => POI_MIN_ZOOM,
                    getBounds: () => ({
                        getWest: () => BOUNDS.west,
                        getSouth: () => BOUNDS.south,
                        getEast: () => BOUNDS.east,
                        getNorth: () => BOUNDS.north,
                    }),
                },
            });
        });
        await waitFor(() =>
            expect(view.container.querySelector('[data-source="nearby"]')).toHaveAttribute("data-count", "3"),
        );
        return view;
    }

    // mapa simulado que solo pinta los puntos ids y ve los destinos de markerInView
    function idle(ids: string[], markerInView: boolean) {
        const queryRenderedFeatures = vi.fn(() => ids.map((id) => ({ properties: { id } })));
        act(() =>
            (lastMapProps().onIdle as (e: unknown) => void)({
                target: {
                    getLayer: () => ({}),
                    queryRenderedFeatures,
                    getBounds: () => ({ contains: () => markerInView }),
                    getCanvas: () => ({ clientWidth: 400, clientHeight: 600 }),
                },
            }),
        );
        return queryRenderedFeatures;
    }

    async function legendItems(user: ReturnType<typeof userEvent.setup>) {
        await user.click(screen.getByRole("button", { name: "Leyenda del mapa" }));
        const list = screen.getByRole("list", { name: "Tipos de lugar en el mapa" });
        const items = within(list).getAllByRole("listitem").map((li) => li.textContent);
        await user.keyboard("{Escape}");
        return items;
    }

    it("cuenta solo los puntos y destinos que el mapa pinta en pantalla", async () => {
        const user = userEvent.setup();
        await showPoints();
        expect(await legendItems(user)).toEqual(["Parque o zona verde: 1", "Fuente: 1", "Banco: 2"]);
        // un banco tapado (solapado o bajo la hoja) y el destino fuera de la vista
        const query = idle(["b1", "f1"], false);
        expect(query).toHaveBeenCalledWith([[0, 0], [400, 600]], { layers: ["nearby-points"] });
        expect(await legendItems(user)).toEqual(["Fuente: 1", "Banco: 1"]);
    });

    it("un tipo cargado pero sin pintar no se da como «sin datos»", async () => {
        const user = userEvent.setup();
        await showPoints();
        idle([], true);
        await user.click(screen.getByRole("button", { name: "Leyenda del mapa" }));
        const dialog = screen.getByRole("dialog", { name: "Leyenda del mapa" });
        expect(dialog).toHaveTextContent("Sin datos en esta zona: Papelera, Desfibrilador, Área canina, Juegos infantiles.");
        expect(dialog).not.toHaveTextContent(/Sin datos en esta zona:.*(Fuente|Banco)/);
    });

    it("oculta los puntos de interes del mapa base y deja sus nombres de calles", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        const setLayoutProperty = vi.fn();
        const target = {
            getStyle: () => ({
                layers: [
                    { id: "poi_r20", "source-layer": "poi" },
                    { id: "poi_transit", "source-layer": "poi" },
                    { id: "highway-name-minor", "source-layer": "transportation_name" },
                    { id: "background" },
                ],
            }),
            setLayoutProperty,
            getZoom: () => 14,
            getBounds: () => ({ getWest: () => 0, getSouth: () => 0, getEast: () => 0, getNorth: () => 0 }),
        };
        act(() => (lastMapProps().onLoad as (e: unknown) => void)({ target }));
        expect(setLayoutProperty.mock.calls).toEqual([
            ["poi_r20", "visibility", "none"],
            ["poi_transit", "visibility", "none"],
        ]);
    });
});
