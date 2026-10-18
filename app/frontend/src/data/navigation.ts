import { useEffect, useState } from "react";
import type { Coordinate } from "../api/types";
import type { LonLat } from "../lib/geometry";
import { distanceM, type LiveDeps } from "./livePosition";

// Navegacion sobre una ruta ya calculada («Seguir mi ubicacion»). La posicion se queda en el
// navegador: no se envia a la API, no se guarda y la ruta no se recalcula al moverse.
// Umbrales, todos criterio propio:
// - como mucho una actualizacion por segundo y solo si se ha movido NAV_MIN_MOVE_M (criterio propio)
export const NAV_MIN_INTERVAL_MS = 1_000;
export const NAV_MIN_MOVE_M = 3;
// mas lejos de la linea que esto: «Te has alejado de la ruta» (criterio propio)
export const OFF_ROUTE_M = 40;
// a menos de esto del final: «Has llegado» (criterio propio)
export const ARRIVED_M = 25;
// zoom minimo del mapa mientras sigue la ubicacion (criterio propio)
export const NAV_ZOOM = 17;

export type NavigationError = "denied" | "insecure" | "unavailable";

const EARTH_RADIUS_M = 6_371_008.8;
const RAD = Math.PI / 180;

// Ventana de busqueda alrededor del avance anterior (criterio propio): en rutas de ida y vuelta o
// circulares los tramos se solapan y la proyeccion mas cercana podria saltar al final
export const NAV_BACK_M = 50;
export const NAV_AHEAD_M = 300;

// Proyecta la posicion sobre la linea de la ruta. Proyeccion equirectangular alrededor de la
// posicion (metros locales), suficiente a la escala de una ruta a pie. Con `fromAlong` (metros ya
// recorridos en la actualizacion anterior) solo busca entre NAV_BACK_M detras y NAV_AHEAD_M delante;
// si ahi queda lejos de la linea (mas de OFF_ROUTE_M), busca en toda la ruta.
export function progressAlong(
    route: LonLat[],
    position: Coordinate,
    fromAlong?: number,
): { remaining_m: number; off_route_m: number; along_m: number } {
    if (route.length === 0) return { remaining_m: 0, off_route_m: Infinity, along_m: 0 };
    const at = (c: LonLat): Coordinate => ({ lat: c[1], lon: c[0] });
    if (route.length === 1) return { remaining_m: 0, off_route_m: distanceM(position, at(route[0])), along_m: 0 };

    // metros recorridos al principio de cada vertice
    const cumulative = [0];
    for (let i = 0; i < route.length - 1; i++) {
        cumulative.push(cumulative[i] + distanceM(at(route[i]), at(route[i + 1])));
    }
    const total = cumulative[cumulative.length - 1];

    const kx = Math.cos(position.lat * RAD) * EARTH_RADIUS_M * RAD;
    const ky = EARTH_RADIUS_M * RAD;
    const local = (c: LonLat) => ({ x: (c[0] - position.lon) * kx, y: (c[1] - position.lat) * ky });

    const nearest = (include: (i: number) => boolean) => {
        let best: { index: number; t: number; d2: number } | null = null;
        for (let i = 0; i < route.length - 1; i++) {
            if (!include(i)) continue;
            const a = local(route[i]);
            const b = local(route[i + 1]);
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const len2 = dx * dx + dy * dy;
            // el origen (0, 0) es la posicion
            const t = len2 === 0 ? 0 : Math.min(1, Math.max(0, -(a.x * dx + a.y * dy) / len2));
            const px = a.x + t * dx;
            const py = a.y + t * dy;
            const d2 = px * px + py * py;
            if (!best || d2 < best.d2) best = { index: i, t, d2 };
        }
        if (!best) return null;
        const a = route[best.index];
        const b = route[best.index + 1];
        const projected: Coordinate = {
            lat: a[1] + best.t * (b[1] - a[1]),
            lon: a[0] + best.t * (b[0] - a[0]),
        };
        const along = cumulative[best.index] + distanceM(at(a), projected);
        return { remaining_m: Math.max(0, total - along), off_route_m: distanceM(position, projected), along_m: along };
    };

    if (fromAlong !== undefined) {
        const lo = fromAlong - NAV_BACK_M;
        const hi = fromAlong + NAV_AHEAD_M;
        const windowed = nearest((i) => cumulative[i + 1] >= lo && cumulative[i] <= hi);
        if (windowed && windowed.off_route_m <= OFF_ROUTE_M) return windowed;
    }
    return nearest(() => true)!;
}

function browserDeps(): LiveDeps & { secure: boolean; now: () => number } {
    const nav = typeof navigator === "undefined" ? undefined : navigator;
    return {
        geo: nav?.geolocation,
        secure: typeof window !== "undefined" && window.isSecureContext === true,
        now: () => Date.now(),
    };
}

// Sigue la posicion con watchPosition solo mientras `active`: el aviso de permiso del navegador
// solo aparece cuando la persona pulsa «Seguir mi ubicacion». Al desactivar o desmontar, clearWatch.
export function useNavigation(
    active: boolean,
    deps?: LiveDeps,
): { position: Coordinate | null; error: NavigationError | null } {
    const [position, setPosition] = useState<Coordinate | null>(null);
    const [denied, setDenied] = useState(false);
    // las dependencias se fijan al montar (solo cambian en las pruebas)
    const [given] = useState(deps);

    const d = { ...browserDeps(), ...given };
    const geo = given && "geo" in given ? given.geo : d.geo;
    const unsupported: NavigationError | null = !d.secure ? "insecure" : !geo ? "unavailable" : null;
    const ready = active && unsupported === null;

    useEffect(() => {
        if (!ready) return;
        const deps = { ...browserDeps(), ...given };
        const g = (given && "geo" in given ? given.geo : deps.geo) as Geolocation;
        let watchId: number | null = null;
        let last: { at: number; coordinate: Coordinate } | null = null;
        let pending: Coordinate | null = null;
        let timer: ReturnType<typeof setTimeout> | undefined;

        const apply = (coordinate: Coordinate) => {
            last = { at: deps.now(), coordinate };
            pending = null;
            setPosition(coordinate);
        };
        const stop = () => {
            if (watchId !== null) g.clearWatch(watchId);
            watchId = null;
            clearTimeout(timer);
            timer = undefined;
            pending = null;
        };
        const onPosition = (p: GeolocationPosition) => {
            const coordinate = { lat: p.coords.latitude, lon: p.coords.longitude };
            if (!last) {
                apply(coordinate);
                return;
            }
            if (distanceM(last.coordinate, coordinate) < NAV_MIN_MOVE_M) {
                pending = null;
                return;
            }
            const wait = NAV_MIN_INTERVAL_MS - (deps.now() - last.at);
            if (wait <= 0) {
                apply(coordinate);
                return;
            }
            // la ultima posicion que llega antes de tiempo se aplica al vencer el intervalo
            pending = coordinate;
            if (timer === undefined) {
                timer = setTimeout(() => {
                    timer = undefined;
                    if (pending) apply(pending);
                }, wait);
            }
        };
        const onError = (e: GeolocationPositionError) => {
            // sin permiso se deja de seguir; un fallo pasajero (sin senal, tiempo) no para nada
            if (e.code === 1) {
                stop();
                setPosition(null);
                setDenied(true);
            }
        };
        watchId = g.watchPosition(onPosition, onError, {
            enableHighAccuracy: true,
            maximumAge: NAV_MIN_INTERVAL_MS,
            timeout: 20_000,
        });
        return () => {
            stop();
            // al dejar de seguir se olvida la posicion y el error
            setPosition(null);
            setDenied(false);
        };
    }, [ready, given]);

    if (!active) return { position: null, error: null };
    if (unsupported) return { position: null, error: unsupported };
    return { position, error: denied ? "denied" : null };
}
