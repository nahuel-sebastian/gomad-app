import { useEffect, useState } from "react";
import type { Coordinate } from "../api/types";

// Ubicacion en tiempo real mientras la pantalla del mapa esta abierta (correccion C2).
// La posicion se queda en el navegador: no se guarda ni se envia; solo se usa como origen de una
// para pintar «Estas aqui» en el mapa. Criterio propio:
// - como mucho una actualizacion cada LIVE_MIN_INTERVAL_MS y solo si se ha movido LIVE_MIN_MOVE_M
//   (el GPS del movil oscila unos metros aunque no te muevas); la ultima posicion que llega antes de
//   tiempo queda pendiente y se aplica al vencer el intervalo, para que el punto no se quede atras.
// La busqueda no se recalcula al moverse.
export const LIVE_MIN_INTERVAL_MS = 5_000;
export const LIVE_MIN_MOVE_M = 15;

const EARTH_RADIUS_M = 6_371_008.8;

export function distanceM(a: Coordinate, b: Coordinate): number {
    const rad = Math.PI / 180;
    const dLat = (b.lat - a.lat) * rad;
    const dLon = (b.lon - a.lon) * rad;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLon / 2) ** 2;
    return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

// dependencias del navegador (las pruebas pasan unas simuladas)
export interface LiveDeps {
    geo?: Geolocation;
    secure?: boolean;
    permissions?: Permissions;
    now?: () => number;
}

function browserDeps(): Required<Pick<LiveDeps, "secure" | "now">> & LiveDeps {
    const nav = typeof navigator === "undefined" ? undefined : navigator;
    return {
        geo: nav?.geolocation,
        secure: typeof window !== "undefined" && window.isSecureContext === true,
        permissions: nav?.permissions,
        now: () => Date.now(),
    };
}

// fromBrowser: la ubicacion de la busqueda vino del GPS (el permiso se acaba de dar). Si no, solo se
// sigue si el permiso ya estaba concedido: nunca se abre el aviso de permiso sin que la persona lo pida.
export function useLivePosition(fromBrowser: boolean, deps?: LiveDeps): Coordinate | null {
    const [position, setPosition] = useState<Coordinate | null>(null);
    // las dependencias se fijan al montar (solo cambian en las pruebas)
    const [given] = useState(deps);

    useEffect(() => {
        const d = { ...browserDeps(), ...given };
        const geo = given && "geo" in given ? given.geo : d.geo;
        if (!d.secure || !geo) return;
        let watchId: number | null = null;
        let cancelled = false;
        let last: { at: number; coordinate: Coordinate } | null = null;
        let pending: Coordinate | null = null;
        let timer: ReturnType<typeof setTimeout> | undefined;

        const apply = (coordinate: Coordinate) => {
            last = { at: d.now(), coordinate };
            pending = null;
            setPosition(coordinate);
        };
        const stop = () => {
            if (watchId !== null) geo.clearWatch(watchId);
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
            if (distanceM(last.coordinate, coordinate) < LIVE_MIN_MOVE_M) {
                // ha vuelto cerca de lo que se ve: lo pendiente ya no vale
                pending = null;
                return;
            }
            const wait = LIVE_MIN_INTERVAL_MS - (d.now() - last.at);
            if (wait <= 0) {
                apply(coordinate);
                return;
            }
            pending = coordinate;
            if (timer === undefined) {
                timer = setTimeout(() => {
                    timer = undefined;
                    if (pending) apply(pending);
                }, wait);
            }
        };
        const onError = (e: GeolocationPositionError) => {
            // permiso retirado: se deja de seguir; un fallo pasajero (sin senal, tiempo) no para nada
            if (e.code === 1) {
                stop();
                setPosition(null);
            }
        };
        const start = () => {
            if (cancelled) return;
            watchId = geo.watchPosition(onPosition, onError, {
                enableHighAccuracy: true,
                maximumAge: LIVE_MIN_INTERVAL_MS,
                timeout: 20_000,
            });
        };

        if (fromBrowser) {
            start();
        } else if (d.permissions?.query) {
            d.permissions
                .query({ name: "geolocation" })
                .then((status) => {
                    if (status.state === "granted") start();
                })
                .catch(() => {
                    // sin API de permisos fiable: no se sigue
                });
        }
        return () => {
            cancelled = true;
            stop();
        };
    }, [fromBrowser, given]);

    return position;
}
