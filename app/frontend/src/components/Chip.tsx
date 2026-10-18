import type { ReactNode } from "react";
import type { AqiCategory } from "../api/types";
import { AQI_LEVEL, AQI_LEVELS, aqiLabel, type Tone } from "../lib/labels";
import Icon from "./Icon";

interface ChipProps {
    tone: Tone | "info";
    icon: string;
    children: ReactNode;
}

// Pastilla de indicador (pantallas §0.1): icono (aplazado) + color + texto
export default function Chip({ tone, icon, children }: ChipProps) {
    return (
        <span className={`chip chip--${tone} gomad-component gomad-chip`}>
            <Icon name={icon} />
            {children}
        </span>
    );
}

// Pastilla del ICA: fondo con el color de la categoria oficial (codigo de colores del equipo),
// texto con la categoria; el nivel queda para lectores y en el title
export function AqiChip({ category }: { category: AqiCategory | null }) {
    if (!category) {
        return (
            <span className="chip chip--aqi-nodata gomad-component gomad-aqi-chip">
                <Icon name="air" />
                Aire: sin datos
            </span>
        );
    }
    const level = AQI_LEVEL[category];
    return (
        <span
            className={`chip chip--aqi-${category} gomad-component gomad-aqi-chip`}
            title={`Índice oficial de calidad del aire: ${aqiLabel(category)} (nivel ${level} de ${AQI_LEVELS})`}
        >
            <Icon name="air" />
            Aire: {aqiLabel(category)}
            <span className="sr-only"> (índice oficial, nivel {level} de {AQI_LEVELS})</span>
        </span>
    );
}
