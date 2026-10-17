import type { MapPoint } from "../api/types";
import { KIND_STYLES, OUT_OF_SERVICE_COLOR } from "./mapIcons";
import { pointInfo } from "./mapUtils";

interface NearbyListProps {
    // ya ordenados y recortados (closestPoints)
    points: MapPoint[];
    onPick: (point: MapPoint) => void;
}

// «Lugares a la vista»: los puntos de la capa de MapLibre (dibujados en el lienzo, que no es
// enfocable) como lista de botones, para teclado y lectores de pantalla. Usa los puntos ya pedidos.
export default function NearbyList({ points, onPick }: NearbyListProps) {
    if (points.length === 0) return null;
    return (
        <details className="map-legend map-nearby">
            <summary>{`Lugares a la vista (${points.length})`}</summary>
            <ul role="list" aria-label="Lugares a la vista">
                {points.map((p) => {
                    const style = KIND_STYLES[p.kind];
                    return (
                        <li key={p.id}>
                            <button type="button" onClick={() => onPick(p)}>
                                <span
                                    className="map-legend__icon"
                                    style={{ background: p.working === false ? OUT_OF_SERVICE_COLOR : style.color }}>
                                    <svg viewBox="0 0 960 960" aria-hidden="true" focusable="false">
                                        <path d={style.path} />
                                    </svg>
                                </span>
                                {pointInfo(p)}
                            </button>
                        </li>
                    );
                })}
            </ul>
        </details>
    );
}
