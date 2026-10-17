import { describe, expect, it } from "vitest";
import type { MapPoint } from "../api/types";
import { nearbyFeatures, nearbyRequest, NEARBY_MIN_ZOOM, POI_MIN_ZOOM } from "../components/mapUtils";

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
