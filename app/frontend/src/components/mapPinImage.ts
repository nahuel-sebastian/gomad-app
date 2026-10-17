import type { MapPointKind } from "../api/types";
import { KIND_STYLES, OUT_OF_SERVICE_COLOR } from "./mapIcons";

// Imagenes de los pines de la capa de puntos cercanos (C2). MapLibre pide cada una con
// «styleimagemissing» la primera vez que la necesita (tambien tras cambiar de estilo).
// Nombres: pin-<tipo> y pin-off-<tipo> (fuera de servicio, en gris).

// tamano en px CSS; se dibuja al doble para pantallas de alta densidad
const PIN_WIDTH = 30;
const PIN_HEIGHT = 36;
export const PIN_PIXEL_RATIO = 2;

export function pinImageSpec(id: string): { kind: MapPointKind; color: string } | null {
    const match = /^pin-(off-)?([a-z_]+)$/.exec(id);
    if (!match || !(match[2] in KIND_STYLES)) return null;
    const kind = match[2] as MapPointKind;
    return { kind, color: match[1] ? OUT_OF_SERVICE_COLOR : KIND_STYLES[kind].color };
}

// Circulo del color del tipo con borde blanco, punta abajo e icono blanco; null sin lienzo 2D
export function pinImage(id: string): ImageData | null {
    const spec = pinImageSpec(id);
    if (!spec) return null;
    const r = PIN_PIXEL_RATIO;
    const canvas = document.createElement("canvas");
    canvas.width = PIN_WIDTH * r;
    canvas.height = PIN_HEIGHT * r;
    let ctx: CanvasRenderingContext2D | null = null;
    try {
        ctx = canvas.getContext("2d");
    } catch {
        return null;
    }
    if (!ctx || typeof ctx.getImageData !== "function" || typeof Path2D === "undefined") return null;
    ctx.scale(r, r);
    const cx = PIN_WIDTH / 2;
    const radius = PIN_WIDTH / 2 - 2;
    const cy = radius + 2;
    // punta hacia el lugar
    ctx.beginPath();
    ctx.moveTo(cx - 6, cy + radius - 3);
    ctx.lineTo(cx, PIN_HEIGHT - 1);
    ctx.lineTo(cx + 6, cy + radius - 3);
    ctx.closePath();
    ctx.fillStyle = "#ffffff";
    ctx.fill();
    ctx.beginPath();
    ctx.arc(cx, cy, radius, 0, Math.PI * 2);
    ctx.fillStyle = spec.color;
    ctx.fill();
    ctx.lineWidth = 2;
    ctx.strokeStyle = "#ffffff";
    ctx.stroke();
    const icon = 18;
    ctx.translate(cx - icon / 2, cy - icon / 2);
    ctx.scale(icon / 960, icon / 960);
    ctx.fillStyle = "#ffffff";
    ctx.fill(new Path2D(KIND_STYLES[spec.kind].path));
    return ctx.getImageData(0, 0, canvas.width, canvas.height);
}
