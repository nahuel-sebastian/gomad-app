import type { ReactNode } from "react";
import type { AqiCategory } from "../api/types";
import { AQI_LEVELS, AQI_PLAIN, aqiLabel, type Tone } from "../lib/labels";
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

// Pastilla del ICA en lenguaje llano: como esta el aire, que supone y una escala de 6 niveles
// con los colores del BOE; la categoria oficial queda en el texto para lectores y en el title
export function AqiChip({ category }: { category: AqiCategory | null }) {
    if (!category) {
        return (
            <span className="chip chip--aqi-nodata gomad-component gomad-aqi-chip">
                <Icon name="air" />
                Aire: sin datos
            </span>
        );
    }
    const plain = AQI_PLAIN[category];
    return (
        <span
            className={`chip chip--aqi-${category} gomad-component gomad-aqi-chip`}
            title={`Índice oficial de calidad del aire: ${aqiLabel(category)} (nivel ${plain.level} de ${AQI_LEVELS})`}
        >
            <Icon name="air" />
            <span className="aqi-chip__text">
                {plain.text}
                <span className="aqi-chip__hint"> · {plain.hint}</span>
            </span>
            <span className="aqi-meter" aria-hidden="true">
                {Array.from({ length: AQI_LEVELS }, (_, i) => (
                    <span key={i} className={`aqi-meter__step aqi-meter__step--${i + 1}${i + 1 === plain.level ? " is-current" : ""}`} />
                ))}
            </span>
            <span className="sr-only">
                {" "}
                (índice oficial: {aqiLabel(category).toLowerCase()}, nivel {plain.level} de {AQI_LEVELS})
            </span>
        </span>
    );
}
