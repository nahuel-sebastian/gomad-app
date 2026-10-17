import { useCallback, useEffect, useRef, useState } from "react";
import type { Coordinate, MapPointKind, MapPointsResponse } from "../api/types";
import { POI_KINDS } from "./mapIcons";
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
    // centro de la caja de la ultima respuesta aplicada (ordena «Lugares a la vista»)
    const [center, setCenter] = useState<Coordinate | null>(null);
    // tipos de punto util que comprobo la respuesta aplicada (vacio si estaba truncada): solo de
    // ellos se puede decir «sin datos en esta zona»
    const [checkedPoiKinds, setCheckedPoiKinds] = useState<MapPointKind[]>([]);
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
                setCheckedPoiKinds([]);
                return;
            }
            timer.current = setTimeout(() => {
                getMapPoints(request.bbox, request.kinds).then(
                    (response) => {
                        if (id === sequence.current) {
                            const [w, s, e, n] = request.bbox;
                            setCenter({ lat: (s + n) / 2, lon: (w + e) / 2 });
                            setNearby(response);
                            setCheckedPoiKinds(
                                response.truncated ? [] : request.kinds.filter((k) => POI_KINDS.includes(k)),
                            );
                        }
                    },
                    () => {
                        // sin red o sin datos: el mapa sigue con los resultados numerados
                        if (id === sequence.current) {
                            setNearby(null);
                            setCheckedPoiKinds([]);
                        }
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

    return { nearby, zoom, center, checkedPoiKinds, refresh };
}
