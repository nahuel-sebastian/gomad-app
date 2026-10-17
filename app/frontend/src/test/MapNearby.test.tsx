import { act, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { MapPoint, MapPointsResponse } from "../api/types";
import { KIND_STYLES, OUT_OF_SERVICE_COLOR } from "../components/mapIcons";
import MapLegend from "../components/MapLegend";
import { pinImage, pinImageSpec } from "../components/mapPinImage";
import {
    nearbyFeatures,
    nearbyRequest,
    NEARBY_DEBOUNCE_MS,
    NEARBY_MIN_ZOOM,
    POI_MIN_ZOOM,
} from "../components/mapUtils";
import MapView, { type MapMarker } from "../components/MapView";
import * as mapPointsModule from "../data/mapPoints";
import { fitBoundsMock, lastMapProps, withWebGL } from "./mapMock";
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

    it("de cerca pide tambien fuentes, bancos, desfibriladores, areas caninas y juegos", () => {
        const req = nearbyRequest(POI_MIN_ZOOM, BOUNDS)!;
        expect(req.kinds).toEqual(expect.arrayContaining(["park", "fountain", "bench", "aed", "dog_area", "playground"]));
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

// --- Task 146: capa de puntos cercanos con clusters ---
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
        await waitFor(() => expect(nearbySource(container)).toHaveAttribute("data-count", "9"));
        expect(spy).toHaveBeenCalledTimes(1);
        expect(spy.mock.calls[0][0]).toEqual([BOUNDS.west, BOUNDS.south, BOUNDS.east, BOUNDS.north]);
        expect(nearbySource(container)).toHaveAttribute("data-cluster", "true");
        expect(container.querySelector('[data-layer="nearby-points"]')).not.toBeNull();
        expect(container.querySelector('[data-layer="nearby-clusters"]')).not.toBeNull();
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

    it("pulsar un grupo acerca el mapa", async () => {
        withWebGL();
        render(<MapView markers={MARKERS} explore />);
        await screen.findByTestId("maplibre");
        const target = fakeMap(13);
        await act(async () => {
            (lastMapProps().onClick as (e: unknown) => void)({
                features: [{ properties: { cluster: true, point_count: 12 }, geometry: { type: "Point", coordinates: [-3.73, 40.3] } }],
                target,
            });
        });
        expect(target.easeTo).toHaveBeenCalledWith({ center: [-3.73, 40.3], zoom: 15 });
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
});

// --- Task 147: leyenda accesible ---
describe("leyenda del mapa", () => {
    afterEach(() => {
        vi.restoreAllMocks();
    });

    it("lista los tipos visibles con icono, texto y recuento", () => {
        const { container } = render(
            <MapLegend
                markerKinds={["park"]}
                points={[point("a", "park"), point("b", "fountain", false), point("c", "fountain"), point("d", "bench")]}
                zoom={POI_MIN_ZOOM}
                truncated={false}
            />,
        );
        expect(screen.getByText("Leyenda")).toBeInTheDocument();
        const list = screen.getByRole("list", { name: "Tipos de lugar en el mapa" });
        const items = within(list).getAllByRole("listitem").map((li) => li.textContent);
        expect(items).toEqual([
            "Parque o zona verde: 2",
            "Fuente: 2",
            "Banco: 1",
            "Fuente fuera de servicio: 1",
            "Grupo de lugares (tócalo para acercar)",
        ]);
        expect(container.querySelectorAll(".map-legend__icon svg[aria-hidden='true']").length).toBe(4);
    });

    it("pide acercar el mapa a poco zoom y avisa si hay mas lugares", () => {
        const { rerender } = render(<MapLegend markerKinds={["park"]} points={[]} zoom={NEARBY_MIN_ZOOM - 1} truncated={false} />);
        expect(screen.getByText("Acerca el mapa para ver más lugares de la zona.")).toBeInTheDocument();
        rerender(<MapLegend markerKinds={["park"]} points={[]} zoom={NEARBY_MIN_ZOOM} truncated={false} />);
        expect(screen.getByText("Acerca más para ver fuentes, bancos, desfibriladores y áreas caninas.")).toBeInTheDocument();
        rerender(<MapLegend markerKinds={[]} points={[point("a", "park")]} zoom={POI_MIN_ZOOM} truncated />);
        expect(screen.getByText("Hay más lugares de los que se ven: acerca el mapa.")).toBeInTheDocument();
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

// --- Task 149: «Estás aquí» en tiempo real ---
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
});
