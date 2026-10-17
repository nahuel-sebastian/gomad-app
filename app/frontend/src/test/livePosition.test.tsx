import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
    distanceM,
    LIVE_MIN_INTERVAL_MS,
    LIVE_MIN_MOVE_M,
    useLivePosition,
    type LiveDeps,
} from "../data/livePosition";

// geolocalizacion simulada: guarda los callbacks de watchPosition para emitir posiciones
function fakeGeo() {
    const watchers = new Map<number, { ok: PositionCallback; fail?: PositionErrorCallback | null }>();
    let next = 1;
    const geo = {
        watchPosition: vi.fn((ok: PositionCallback, fail?: PositionErrorCallback | null) => {
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

function permissions(state: PermissionState) {
    return { query: vi.fn().mockResolvedValue({ state }) } as unknown as Permissions;
}

// ~111 m por milesima de grado de latitud
const A = { lat: 40.3057, lon: -3.7329 };

describe("useLivePosition", () => {
    it("con ubicacion del GPS sigue la posicion", () => {
        const g = fakeGeo();
        const { result } = renderHook(() => useLivePosition(true, { geo: g.geo, secure: true }));
        expect(g.raw.watchPosition).toHaveBeenCalledOnce();
        g.emit(A.lat, A.lon);
        expect(result.current).toEqual(A);
    });

    it("con permiso concedido sigue aunque la ubicacion sea escrita", async () => {
        const g = fakeGeo();
        const deps: LiveDeps = { geo: g.geo, secure: true, permissions: permissions("granted") };
        renderHook(() => useLivePosition(false, deps));
        await act(async () => {});
        expect(g.raw.watchPosition).toHaveBeenCalledOnce();
    });

    it("no pide permiso si no estaba concedido", async () => {
        const g = fakeGeo();
        for (const state of ["prompt", "denied"] as PermissionState[]) {
            renderHook(() => useLivePosition(false, { geo: g.geo, secure: true, permissions: permissions(state) }));
        }
        // sin API de permisos (Safari antiguo) tampoco
        renderHook(() => useLivePosition(false, { geo: g.geo, secure: true }));
        await act(async () => {});
        expect(g.raw.watchPosition).not.toHaveBeenCalled();
        expect(g.raw.getCurrentPosition).not.toHaveBeenCalled();
    });

    it("no actualiza por movimientos pequenos ni antes del intervalo", () => {
        let now = 0;
        const g = fakeGeo();
        const { result } = renderHook(() => useLivePosition(true, { geo: g.geo, secure: true, now: () => now }));
        g.emit(A.lat, A.lon);
        now = LIVE_MIN_INTERVAL_MS / 2;
        g.emit(A.lat + 0.001, A.lon);
        expect(result.current).toEqual(A);
        now = LIVE_MIN_INTERVAL_MS * 2;
        g.emit(A.lat + 0.00005, A.lon);           // ~6 m
        expect(result.current).toEqual(A);
        g.emit(A.lat + 0.001, A.lon);             // ~111 m
        expect(result.current).toEqual({ lat: A.lat + 0.001, lon: A.lon });
    });

    it("limpia el seguimiento al desmontar", () => {
        const g = fakeGeo();
        const { unmount } = renderHook(() => useLivePosition(true, { geo: g.geo, secure: true }));
        unmount();
        expect(g.raw.clearWatch).toHaveBeenCalledWith(1);
        expect(g.watchers.size).toBe(0);
    });

    it("si se deniega deja de seguir y olvida la posicion", () => {
        const g = fakeGeo();
        const { result } = renderHook(() => useLivePosition(true, { geo: g.geo, secure: true }));
        g.emit(A.lat, A.lon);
        g.fail(1);
        expect(g.raw.clearWatch).toHaveBeenCalledWith(1);
        expect(result.current).toBeNull();
    });

    it("un fallo pasajero no para el seguimiento", () => {
        const g = fakeGeo();
        const { result } = renderHook(() => useLivePosition(true, { geo: g.geo, secure: true }));
        g.emit(A.lat, A.lon);
        g.fail(3);
        expect(g.raw.clearWatch).not.toHaveBeenCalled();
        expect(result.current).toEqual(A);
    });

    it("sin HTTPS o sin API no sigue", () => {
        const g = fakeGeo();
        renderHook(() => useLivePosition(true, { geo: g.geo, secure: false }));
        expect(g.raw.watchPosition).not.toHaveBeenCalled();
        const { result } = renderHook(() => useLivePosition(true, { geo: undefined, secure: true }));
        expect(result.current).toBeNull();
    });

    it("distanceM mide en metros", () => {
        expect(distanceM(A, { lat: A.lat + 0.001, lon: A.lon })).toBeCloseTo(111, 0);
        expect(LIVE_MIN_MOVE_M).toBeGreaterThan(5);
    });
});

describe("useLivePosition con cola (verificador)", () => {
    it("acepta la ultima posicion pendiente al vencer el intervalo", () => {
        vi.useFakeTimers();
        try {
            const g = fakeGeo();
            const { result, unmount } = renderHook(() => useLivePosition(true, { geo: g.geo, secure: true }));
            g.emit(A.lat, A.lon);
            act(() => vi.advanceTimersByTime(1000));
            g.emit(A.lat + 0.001, A.lon);
            act(() => vi.advanceTimersByTime(1000));
            g.emit(A.lat + 0.002, A.lon);
            expect(result.current).toEqual(A);
            act(() => vi.advanceTimersByTime(LIVE_MIN_INTERVAL_MS));
            expect(result.current).toEqual({ lat: A.lat + 0.002, lon: A.lon });
            unmount();
            expect(vi.getTimerCount()).toBe(0);
        } finally {
            vi.useRealTimers();
        }
    });

    it("si vuelve cerca de la posicion mostrada, descarta la pendiente", () => {
        vi.useFakeTimers();
        try {
            const g = fakeGeo();
            const { result } = renderHook(() => useLivePosition(true, { geo: g.geo, secure: true }));
            g.emit(A.lat, A.lon);
            g.emit(A.lat + 0.001, A.lon);
            g.emit(A.lat + 0.00002, A.lon);
            act(() => vi.advanceTimersByTime(LIVE_MIN_INTERVAL_MS * 2));
            expect(result.current).toEqual(A);
        } finally {
            vi.useRealTimers();
        }
    });
});
