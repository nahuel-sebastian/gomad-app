import { useCallback, useEffect, useRef, useState } from "react";
import type { MapPointsResponse } from "../api/types";
import { getMapPoints } from "../data/mapPoints";
import { nearbyRequest, NEARBY_DEBOUNCE_MS } from "./mapUtils";

// lo que usa el hook del mapa de MapLibre (asi las pruebas pasan un objeto simple)
export interface ViewSource {
    getZoom(): number;
    getBounds(): { getWest(): number; getSouth(): number; getEast(): number; getNorth(): number };
}

// Puntos de la zona visible (C2): se piden al dejar de mover el mapa, tras NEARBY_DEBOUNCE_MS;
// solo cuenta la respuesta de la ultima vista. Con enabled false no hace nada.
export function useNearbyPoints(enabled: boolean) {
    const [nearby, setNearby] = useState<MapPointsResponse | null>(null);
    const [zoom, setZoom] = useState<number | null>(null);
    const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
    const sequence = useRef(0);

    const refresh = useCallback(
        (view: ViewSource) => {
            if (!enabled) return;
            const currentZoom = view.getZoom();
            const b = view.getBounds();
            setZoom(currentZoom);
            clearTimeout(timer.current);
            const id = ++sequence.current;
            const request = nearbyRequest(currentZoom, {
                west: b.getWest(),
                south: b.getSouth(),
                east: b.getEast(),
                north: b.getNorth(),
            });
            if (!request) {
                setNearby(null);
                return;
            }
            timer.current = setTimeout(() => {
                getMapPoints(request.bbox, request.kinds).then(
                    (response) => {
                        if (id === sequence.current) setNearby(response);
                    },
                    () => {
                        // sin red o sin datos: el mapa sigue con los resultados numerados
                        if (id === sequence.current) setNearby(null);
                    },
                );
            }, NEARBY_DEBOUNCE_MS);
        },
        [enabled],
    );

    useEffect(
        () => () => {
            clearTimeout(timer.current);
            // una respuesta que llegue tras desmontar no se aplica
            sequence.current++;
        },
        [],
    );

    return { nearby, zoom, refresh };
}
