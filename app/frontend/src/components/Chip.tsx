import type { ReactNode } from "react";
import type { AqiCategory } from "../api/types";
import { aqiLabel, type Tone } from "../lib/labels";
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

// Pastilla del ICA con un tono legible por categoría y el texto del BOE
export function AqiChip({ category }: { category: AqiCategory | null }) {
    return (
        <span className={`chip chip--aqi-${category ?? "nodata"} gomad-component gomad-aqi-chip`}>
            <Icon name="air" />
            {category ? `Aire ${aqiLabel(category).toLowerCase()}` : "Aire: sin datos"}
        </span>
    );
}
