import { afterEach, describe, expect, it, vi } from "vitest";
import { getMapPoints } from "../data/mapPoints";

// Getafe alrededor del origen de ejemplo
const BOX: [number, number, number, number] = [-3.745, 40.298, -3.72, 40.313];

afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
});

describe("getMapPoints", () => {
    it("filtra los puntos de ejemplo por caja y tipo", async () => {
        const parks = await getMapPoints(BOX, ["park"]);
        expect(parks.points.length).toBeGreaterThan(0);
        expect(parks.points.every((p) => p.kind === "park")).toBe(true);
        expect(parks.truncated).toBe(false);
        const fountains = await getMapPoints(BOX, ["fountain"]);
        expect(fountains.points.some((p) => p.working === false)).toBe(true);
        const far = await getMapPoints([-3.6, 40.5, -3.5, 40.6], ["park", "fountain"]);
        expect(far.points).toEqual([]);
    });

    it("pide /api/map/points con la caja y los tipos", async () => {
        vi.stubEnv("MODE", "production");
        const body = { points: [], truncated: false, clipped: false };
        const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
        vi.stubGlobal("fetch", fetchMock);
        expect(await getMapPoints(BOX, ["park", "fountain"])).toEqual(body);
        expect(fetchMock.mock.calls[0][0]).toBe(
            "/api/map/points?bbox=-3.74500%2C40.29800%2C-3.72000%2C40.31300&kinds=park&kinds=fountain",
        );
    });

    it("recupera los otros puntos si una API antigua rechaza papeleras", async () => {
        vi.resetModules();
        vi.stubEnv("MODE", "production");
        const { getMapPoints: fetchPoints, mapPointKindAvailable } = await import("../data/mapPoints");
        const body = { points: [], truncated: false, clipped: false };
        const fetchMock = vi.fn()
            .mockResolvedValueOnce(new Response(JSON.stringify({ detail: [{ type: "literal_error", input: "bin" }] }), { status: 422 }))
            .mockImplementation(() => Promise.resolve(new Response(JSON.stringify(body), { status: 200 })));
        vi.stubGlobal("fetch", fetchMock);

        expect(await fetchPoints(BOX, ["park", "bench", "bin"])).toEqual(body);
        expect(new URL(fetchMock.mock.calls[0][0], "http://localhost").searchParams.getAll("kinds")).toEqual(["park", "bench", "bin"]);
        expect(new URL(fetchMock.mock.calls[1][0], "http://localhost").searchParams.getAll("kinds")).toEqual(["park", "bench"]);
        expect(mapPointKindAvailable("bin")).toBe(false);

        await fetchPoints(BOX, ["park", "bench", "bin"]);
        expect(fetchMock).toHaveBeenCalledTimes(3);
        expect(new URL(fetchMock.mock.calls[2][0], "http://localhost").searchParams.getAll("kinds")).toEqual(["park", "bench"]);
    });
});
