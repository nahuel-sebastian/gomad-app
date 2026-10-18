import { act } from "@testing-library/react";
import { vi } from "vitest";
import type { RouteVariant } from "../api/types";
import { toLineString, type LonLat } from "../lib/geometry";

// Geolocalizacion simulada del navegador para las pruebas de navegacion (Tasks 184-185):
// sustituye navigator.geolocation y window.isSecureContext y guarda los callbacks de
// watchPosition para emitir posiciones. restore() deja el navegador como estaba.
export function installFakeGeo({ secure = true }: { secure?: boolean } = {}) {
    const watchers = new Map<number, { ok: PositionCallback; fail?: PositionErrorCallback | null }>();
    let next = 1;
    const raw = {
        watchPosition: vi.fn((ok: PositionCallback, fail?: PositionErrorCallback | null) => {
            watchers.set(next, { ok, fail });
            return next++;
        }),
        clearWatch: vi.fn((id: number) => watchers.delete(id)),
        getCurrentPosition: vi.fn(),
    };
    const geoBefore = Object.getOwnPropertyDescriptor(navigator, "geolocation");
    const secureBefore = Object.getOwnPropertyDescriptor(window, "isSecureContext");
    Object.defineProperty(navigator, "geolocation", { value: raw, configurable: true });
    Object.defineProperty(window, "isSecureContext", { value: secure, configurable: true });
    // reloj que avanza en cada posicion: el intervalo minimo de navegacion no retiene ninguna
    let now = 1_000_000;
    vi.spyOn(Date, "now").mockImplementation(() => now);

    const emit = (lat: number, lon: number) =>
        act(() => {
            now += 10_000;
            for (const w of watchers.values())
                w.ok({ coords: { latitude: lat, longitude: lon } } as GeolocationPosition);
        });
    const fail = (code: number) =>
        act(() => {
            for (const w of watchers.values())
                w.fail?.({ code, message: "", PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 });
        });
    const restore = () => {
        if (geoBefore) Object.defineProperty(navigator, "geolocation", geoBefore);
        else delete (navigator as unknown as Record<string, unknown>).geolocation;
        if (secureBefore) Object.defineProperty(window, "isSecureContext", secureBefore);
        else delete (window as unknown as Record<string, unknown>).isSecureContext;
    };
    return { raw, watchers, emit, fail, restore };
}

// linea de ~1 km hacia el este en Getafe
export const NAV_LAT = 40.3057;
export const NAV_LON0 = -3.7329;
export const NAV_KM_LON = 1000 / (111_320 * Math.cos((NAV_LAT * Math.PI) / 180));
export const NAV_LINE: LonLat[] = [
    [NAV_LON0, NAV_LAT],
    [NAV_LON0 + NAV_KM_LON, NAV_LAT],
];

export function navVariant(overrides: Partial<RouteVariant> = {}): RouteVariant {
    return {
        kind: "healthy",
        geometry: toLineString(NAV_LINE),
        distance_m: 1000,
        duration_min: 12,
        green_pct: null,
        traffic_m: 0,
        pois: [],
        approximate: false,
        description: "",
        ...overrides,
    };
}
