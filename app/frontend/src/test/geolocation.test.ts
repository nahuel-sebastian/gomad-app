import { describe, expect, it } from "vitest";
import { LOCATION_MESSAGES, locateWithBrowser, municipalityAt } from "../data/geolocation";

function fakeGeo(result: { lat: number; lon: number } | { code: number }): Geolocation {
    return {
        getCurrentPosition: (ok: PositionCallback, fail?: PositionErrorCallback | null) => {
            if ("code" in result) fail?.({ code: result.code, message: "", PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 });
            else ok({ coords: { latitude: result.lat, longitude: result.lon } } as GeolocationPosition);
        },
    } as unknown as Geolocation;
}

describe("geolocalización", () => {
    it("devuelve la posición con el municipio más cercano", async () => {
        const c = await locateWithBrowser(fakeGeo({ lat: 40.3057, lon: -3.7329 }), true);
        expect(c).toMatchObject({ label: "Tu ubicación", municipality: "Getafe", ine_code: "28065", precision: "address" });
        expect(c.coordinate).toEqual({ lat: 40.3057, lon: -3.7329 });
    });

    it("sin HTTPS lo explica", async () => {
        await expect(locateWithBrowser(fakeGeo({ lat: 40.3, lon: -3.7 }), false)).rejects.toThrow(LOCATION_MESSAGES.insecure);
    });

    it("permiso denegado", async () => {
        await expect(locateWithBrowser(fakeGeo({ code: 1 }), true)).rejects.toThrow(LOCATION_MESSAGES.denied);
    });

    it("sin posición o sin API", async () => {
        await expect(locateWithBrowser(fakeGeo({ code: 3 }), true)).rejects.toThrow(LOCATION_MESSAGES.unavailable);
        await expect(locateWithBrowser(undefined, true)).rejects.toThrow(LOCATION_MESSAGES.unavailable);
    });

    it("fuera de la Comunidad", async () => {
        await expect(locateWithBrowser(fakeGeo({ lat: 41.39, lon: 2.17 }), true)).rejects.toThrow(LOCATION_MESSAGES.outside);
    });

    it("decide el municipio por su contorno, no por el centro más cercano", async () => {
        expect((await municipalityAt(40.4169, -3.7035))?.ine_code).toBe("28079");     // Sol
        expect((await municipalityAt(40.3057, -3.7329))?.ine_code).toBe("28065");     // centro de Getafe
        expect((await municipalityAt(40.3290, -3.7650))?.ine_code).toBe("28074");     // Leganés
        expect(await municipalityAt(41.39, 2.17)).toBeNull();
    });
});
