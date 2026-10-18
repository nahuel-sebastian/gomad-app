import type { CSSProperties } from "react";
import type { MapPointKind } from "../api/types";
import Icon from "./Icon";
import { KIND_STYLES } from "./mapIcons";

interface MapPinProps {
    kind: MapPointKind;
    // numero visible, el mismo que en la lista
    number: number;
    name: string;
    selected?: boolean;
}

// Pin de un destino recomendado: color e icono de su tipo y su numero. El mapa no es enfocable
// (la lista es el equivalente completo, RF-11), pero el pin lleva texto alternativo.
export default function MapPin({ kind, number, name, selected = false }: MapPinProps) {
    const style = KIND_STYLES[kind];
    const label = `${number}. ${name} (${style.label})${selected ? ", seleccionado" : ""}`;
    return (
        <span
            className={`map-marker map-marker--pin${selected ? " map-marker--selected" : ""}`}
            style={{ "--pin-color": style.color } as CSSProperties}
            role="img"
            aria-label={label}>
            <Icon name={style.icon} />
            <span className="map-marker__number">{number}</span>
        </span>
    );
}
