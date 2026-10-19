import { useRef, useState, type FocusEvent, type PointerEvent } from "react";

// alto de la hoja recogida al arrastrar: solo el asa (los controles de navegacion flotan sobre el mapa)
const SHEET_PEEK_PX = 44;

// Hoja inferior arrastrable en movil de las pantallas de ruta (/trayecto y /ruta/:id): mismo gesto
// que la de Resultados (copiado, no extraido)
export function useRouteSheet() {
    const [expanded, setExpanded] = useState(false);
    const sheetRef = useRef<HTMLDivElement>(null);
    const dragStartY = useRef<number | null>(null);
    const didDrag = useRef(false);

    const reset = () => {
        dragStartY.current = null;
        if (sheetRef.current) sheetRef.current.style.transform = "";
    };

    return {
        expanded,
        setExpanded,
        sheetRef,
        onFocus: (event: FocusEvent<HTMLDivElement>) => {
            // al llegar con el foco al contenido (no al asa ni al h1), la hoja se abre
            if ((event.target as HTMLElement).closest(".results-body")) setExpanded(true);
        },
        onPointerDown: (event: PointerEvent<HTMLDivElement>) => {
            if (window.innerWidth >= 768) return;
            if (!(event.target as HTMLElement).closest(".results-sheet__handle")) return;
            dragStartY.current = event.clientY;
            didDrag.current = false;
        },
        onPointerMove: (event: PointerEvent<HTMLDivElement>) => {
            if (dragStartY.current === null || !sheetRef.current) return;
            const delta = event.clientY - dragStartY.current;
            // la captura solo empieza al arrastrar: un toque sigue siendo un clic en el asa
            if (Math.abs(delta) > 8 && !didDrag.current) {
                didDrag.current = true;
                event.currentTarget.setPointerCapture(event.pointerId);
            }
            const maxOffset = Math.max(sheetRef.current.offsetHeight - SHEET_PEEK_PX, 0);
            const offset = Math.min(maxOffset, Math.max(0, (expanded ? 0 : maxOffset) + delta));
            sheetRef.current.style.transform = `translateY(${offset}px)`;
        },
        onPointerUp: (event: PointerEvent<HTMLDivElement>) => {
            if (dragStartY.current !== null) {
                const delta = event.clientY - dragStartY.current;
                if (Math.abs(delta) > 40) setExpanded(delta < 0);
            }
            reset();
        },
        onPointerCancel: reset,
        toggle: () => {
            if (didDrag.current) {
                didDrag.current = false;
                return;
            }
            setExpanded((value) => !value);
        },
    };
}
