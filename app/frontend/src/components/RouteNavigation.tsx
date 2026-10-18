import { useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import type { Coordinate, RouteVariant } from "../api/types";
import { ARRIVED_M, OFF_ROUTE_M, progressAlong, useNavigation, type NavigationError } from "../data/navigation";
import { lineCoordinates } from "../lib/geometry";
import { formatDistance, formatMinutes } from "../lib/format";
import Icon from "./Icon";

// Navegacion sobre una ruta («Seguir mi ubicacion»), comun a las tres pantallas de ruta.
// La posicion se queda en el navegador: no se envia, no se guarda y la ruta no se recalcula.

const ERROR_TEXT: Record<NavigationError, string> = {
    denied: "No podemos seguir tu ubicación: el navegador no tiene permiso. Actívalo en los ajustes del navegador.",
    insecure: "No podemos seguir tu ubicación: hace falta una conexión segura (HTTPS).",
    unavailable: "No podemos seguir tu ubicación: este navegador no permite conocer la ubicación.",
};

interface NavState {
    // ruta a la que se refiere el estado: si cambia, se deja de seguir
    key: string;
    active: boolean;
    // la camara sigue la posicion (false cuando la persona mueve el mapa)
    follow: boolean;
    // la persona ha dejado de seguir (para anunciarlo)
    stopped: boolean;
    arrived: boolean;
    // ya se ha pulsado alguna vez: desde entonces la region de estado tiene role="status"
    touched: boolean;
    // ultimo avance calculado y la posicion de la que sale (el avance anterior acota la busqueda)
    progress: { at: Coordinate; remaining_m: number; off_route_m: number; along_m: number } | null;
}

// clave por valor: la misma ruta vuelta a pedir no corta la navegacion
function variantKey(variant: RouteVariant | null): string {
    if (!variant) return "";
    const coords = lineCoordinates(variant.geometry);
    return JSON.stringify([variant.kind, variant.distance_m, variant.duration_min, coords.length, coords[0], coords.at(-1)]);
}

export interface RouteNavigationOptions {
    // se llama al empezar a seguir (p. ej. para recoger la hoja y ver el mapa)
    onStart?: () => void;
}

export function useRouteNavigation(
    variant: RouteVariant | null,
    options: RouteNavigationOptions = {},
): { live: Coordinate | null; follow: boolean; onUserMove: () => void; controls: ReactNode } {
    const key = variantKey(variant);
    const [stored, setState] = useState<NavState>({
        key,
        active: false,
        follow: true,
        stopped: false,
        arrived: false,
        touched: false,
        progress: null,
    });
    let state = stored;
    if (stored.key !== key) {
        // otra ruta o variante: se deja de seguir y se reinicia la llegada
        state = { ...stored, key, active: false, follow: true, stopped: stored.active, arrived: false, progress: null };
        setState(state);
    }

    const nav = useNavigation(state.active);
    const following = state.active && nav.error === null;
    const coords = lineCoordinates(variant?.geometry);
    let progress: NavState["progress"] = null;
    if (following && nav.position && coords.length > 0) {
        if (state.progress?.at === nav.position) {
            progress = state.progress;
        } else {
            // solo con cada posicion nueva: el avance sigue desde el anterior (rutas de ida y vuelta)
            progress = { at: nav.position, ...progressAlong(coords, nav.position, state.progress?.along_m ?? 0) };
            // llegada: cerca del final y sobre la ruta (no a 300 m pasado el destino)
            const arrivedNow = progress.remaining_m <= ARRIVED_M && progress.off_route_m <= OFF_ROUTE_M;
            state = { ...state, progress, arrived: state.arrived || arrivedNow };
            setState(state);
        }
    }
    const arrived = following && state.arrived;
    const offRoute = !arrived && progress !== null && progress.off_route_m > OFF_ROUTE_M;

    const start = () => {
        if (state.active) {
            // tras un error: se para y se vuelve a empezar (un solo intento por pulsacion)
            flushSync(() => setState((s) => ({ ...s, active: false })));
        }
        setState((s) => ({ ...s, active: true, follow: true, stopped: false, arrived: false, touched: true, progress: null }));
        options.onStart?.();
    };
    const stop = () => setState((s) => ({ ...s, active: false, follow: true, stopped: true, arrived: false, progress: null }));
    const onUserMove = () => {
        if (following) setState((s) => (s.follow ? { ...s, follow: false } : s));
    };
    const recenter = () => setState((s) => ({ ...s, follow: true }));

    // solo cambios de estado, nunca cada metro
    let announcement = "";
    if (following) {
        announcement = arrived ? "Has llegado" : offRoute ? "Te has alejado de la ruta" : "Siguiendo tu ubicación";
    } else if (state.stopped) {
        announcement = "Has dejado de seguir tu ubicación";
    }

    let panel: ReactNode = null;
    if (following && variant) {
        if (arrived) {
            panel = (
                <p className="notice notice--good route-nav__panel">
                    <Icon name="location_on" />
                    <span>Has llegado</span>
                </p>
            );
        } else if (!progress) {
            panel = (
                <p className="notice notice--info route-nav__panel">
                    <Icon name="navigation" />
                    <span>Buscando tu ubicación…</span>
                </p>
            );
        } else {
            const minutes = variant.distance_m > 0 ? (progress.remaining_m / variant.distance_m) * variant.duration_min : 0;
            panel = (
                <div className={`notice ${offRoute ? "notice--warn" : "notice--info"} route-nav__panel`}>
                    <p>
                        <Icon name="navigation" />
                        <span>{`Te quedan ${formatDistance(progress.remaining_m)} · ${formatMinutes(minutes)}`}</span>
                    </p>
                    {offRoute && (
                        <p>
                            <Icon name="location_off" />
                            <span>Te has alejado de la ruta</span>
                        </p>
                    )}
                </div>
            );
        }
    }

    const controls: ReactNode = variant ? (
        <div className="route-nav gomad-component gomad-route-navigation">
            <div className="route-nav__actions">
                <button
                    type="button"
                    className={`button${following ? "" : " button--primary"} route-nav__toggle`}
                    aria-pressed={following}
                    onClick={following ? stop : start}>
                    <Icon name="navigation" />
                    {following ? "Dejar de seguir" : "Seguir mi ubicación"}
                </button>
                {following && !state.follow && (
                    <button type="button" className="button button--quiet route-nav__recenter" onClick={recenter}>
                        <Icon name="near_me" />
                        Centrar en mí
                    </button>
                )}
            </div>
            {panel}
            {state.active && nav.error && (
                <p className="notice notice--bad route-nav__error" role="alert">
                    {ERROR_TEXT[nav.error]}
                </p>
            )}
            {/* region viva desde el montaje; role="status" solo tras pulsar, asi no compite con
                la region de estado de cada pantalla mientras no se usa la navegacion */}
            <p className="sr-only" aria-live="polite" role={state.touched ? "status" : undefined}>
                {announcement}
            </p>
        </div>
    ) : null;

    return {
        live: following ? nav.position : null,
        follow: following && state.follow,
        onUserMove,
        controls,
    };
}
