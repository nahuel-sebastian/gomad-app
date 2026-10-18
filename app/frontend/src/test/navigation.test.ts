import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { LonLat } from "../lib/geometry";
import type { LiveDeps } from "../data/livePosition";
import {
    NAV_MIN_INTERVAL_MS,
    NAV_MIN_MOVE_M,
    progressAlong,
    useNavigation,
} from "../data/navigation";

// geolocalizacion simulada: guarda los callbacks de watchPosition para emitir posiciones
function fakeGeo() {
    const watchers = new Map<number, { ok: PositionCallback; fail?: PositionErrorCallback | null }>();
    let next = 1;
    const geo = {
        watchPosition: vi.fn((ok: PositionCallback, fail?: PositionErrorCallback | null, _options?: PositionOptions) => {
            watchers.set(next, { ok, fail });
            return next++;
        }),
        clearWatch: vi.fn((id: number) => watchers.delete(id)),
        getCurrentPosition: vi.fn(),
    };
    const emit = (lat: number, lon: number) =>
        act(() => {
            for (const w of watchers.values())
                w.ok({ coords: { latitude: lat, longitude: lon } } as GeolocationPosition);
        });
    const fail = (code: number) =>
        act(() => {
            for (const w of watchers.values())
                w.fail?.({ code, message: "", PERMISSION_DENIED: 1, POSITION_UNAVAILABLE: 2, TIMEOUT: 3 });
        });
    return { geo: geo as unknown as Geolocation, raw: geo, watchers, emit, fail };
}

// linea de ~1 km hacia el este en Getafe (1 grado de longitud ~ 85 km a esta latitud)
const LAT = 40.3057;
const LON0 = -3.7329;
const KM_LON = 1000 / (111_320 * Math.cos((LAT * Math.PI) / 180));
const LINE: LonLat[] = [
    [LON0, LAT],
    [LON0 + KM_LON / 2, LAT],
    [LON0 + KM_LON, LAT],
];

function near(value: number, expected: number) {
    expect(Math.abs(value - expected)).toBeLessThanOrEqual(expected * 0.01);
}

describe("progressAlong", () => {
    it("en la mitad de una linea de 1 km quedan ~500 m", () => {
        const p = progressAlong(LINE, { lat: LAT, lon: LON0 + KM_LON / 2 });
        near(p.remaining_m, 500);
        expect(p.off_route_m).toBeLessThan(1);
    });

    it("a 100 m de la linea da off_route_m ~100", () => {
        const p = progressAlong(LINE, { lat: LAT + 100 / 111_195, lon: LON0 + KM_LON / 4 });
        near(p.off_route_m, 100);
        near(p.remaining_m, 750);
    });

    it("funciona con una ruta de 2 puntos", () => {
        const two: LonLat[] = [LINE[0], LINE[2]];
        const p = progressAlong(two, { lat: LAT, lon: LON0 + KM_LON / 4 });
        near(p.remaining_m, 750);
        const end = progressAlong(two, { lat: LAT, lon: LON0 + KM_LON });
        expect(end.remaining_m).toBeLessThan(1);
    });
});

const A = { lat: LAT, lon: LON0 };

describe("useNavigation", () => {
    it("inactivo no llama a watchPosition", () => {
        const g = fakeGeo();
        renderHook(() => useNavigation(false, { geo: g.geo, secure: true }));
        expect(g.raw.watchPosition).not.toHaveBeenCalled();
        expect(g.raw.getCurrentPosition).not.toHaveBeenCalled();
    });

    it("al activarse sigue con alta precision", () => {
        const g = fakeGeo();
        const deps: LiveDeps = { geo: g.geo, secure: true };
        const { result, rerender } = renderHook(({ on }) => useNavigation(on, deps), {
            initialProps: { on: false },
        });
        rerender({ on: true });
        expect(g.raw.watchPosition).toHaveBeenCalledOnce();
        expect(g.raw.watchPosition.mock.calls[0][2]).toMatchObject({ enableHighAccuracy: true });
        g.emit(A.lat, A.lon);
        expect(result.current).toEqual({ position: A, error: null });
    });

    it("aplica el intervalo y el movimiento minimos", () => {
        let now = 0;
        const g = fakeGeo();
        const { result } = renderHook(() => useNavigation(true, { geo: g.geo, secure: true, now: () => now }));
        g.emit(A.lat, A.lon);
        now = NAV_MIN_INTERVAL_MS / 2;
        g.emit(A.lat + 0.0002, A.lon); // ~22 m, antes de tiempo
        expect(result.current.position).toEqual(A);
        now = NAV_MIN_INTERVAL_MS * 2;
        g.emit(A.lat + (NAV_MIN_MOVE_M / 2) / 111_195, A.lon); // menos del movimiento minimo
        expect(result.current.position).toEqual(A);
        g.emit(A.lat + 0.0002, A.lon);
        expect(result.current.position).toEqual({ lat: A.lat + 0.0002, lon: A.lon });
    });

    it("con el permiso denegado da denied y para", () => {
        const g = fakeGeo();
        const { result } = renderHook(() => useNavigation(true, { geo: g.geo, secure: true }));
        g.emit(A.lat, A.lon);
        g.fail(1);
        expect(g.raw.clearWatch).toHaveBeenCalledWith(1);
        expect(result.current).toEqual({ position: null, error: "denied" });
        expect(g.raw.watchPosition).toHaveBeenCalledOnce();
    });

    it("sin contexto seguro da insecure", () => {
        const g = fakeGeo();
        const { result } = renderHook(() => useNavigation(true, { geo: g.geo, secure: false }));
        expect(g.raw.watchPosition).not.toHaveBeenCalled();
        expect(result.current.error).toBe("insecure");
    });

    it("sin API de geolocalizacion da unavailable", () => {
        const { result } = renderHook(() => useNavigation(true, { geo: undefined, secure: true }));
        expect(result.current.error).toBe("unavailable");
    });

    it("al desactivar o desmontar limpia el seguimiento", () => {
        const g = fakeGeo();
        const deps: LiveDeps = { geo: g.geo, secure: true };
        const { result, rerender, unmount } = renderHook(({ on }) => useNavigation(on, deps), {
            initialProps: { on: true },
        });
        g.emit(A.lat, A.lon);
        rerender({ on: false });
        expect(g.raw.clearWatch).toHaveBeenCalledWith(1);
        expect(result.current).toEqual({ position: null, error: null });
        rerender({ on: true });
        expect(g.raw.watchPosition).toHaveBeenCalledTimes(2);
        unmount();
        expect(g.raw.clearWatch).toHaveBeenCalledWith(2);
        expect(g.watchers.size).toBe(0);
    });
});

describe("progressAlong en rutas de ida y vuelta", () => {
    // ida hasta B y vuelta al inicio: los dos tramos se solapan
    const BACK: LonLat[] = [LINE[0], LINE[2], LINE[0]];

    it("al salir no da la ruta por terminada", () => {
        const p = progressAlong(BACK, { lat: LAT, lon: LON0 + KM_LON / 20 }, 0);
        near(p.remaining_m, 1950);
    });

    it("a la vuelta sigue avanzando desde donde iba", () => {
        const p = progressAlong(BACK, { lat: LAT, lon: LON0 + KM_LON / 4 }, 1700);
        near(p.remaining_m, 250);
        near(p.along_m, 1750);
    });

    it("lejos de lo esperado busca en toda la ruta", () => {
        const p = progressAlong(LINE, { lat: LAT, lon: LON0 + KM_LON * 0.9 }, 0);
        near(p.remaining_m, 100);
    });
});
