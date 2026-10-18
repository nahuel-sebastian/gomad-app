import { useId, useRef, type ReactNode } from "react";
import Icon from "./Icon";

interface MapDialogProps {
    // nombre del boton (solo icono: va en aria-label y en el tooltip)
    label: string;
    // contenido visible del boton (icono)
    icon: ReactNode;
    // clase extra del boton (gomad-action-…)
    action: string;
    title: string;
    className?: string;
    // un elemento con data-dialog-close cierra la ventana al pulsarlo (p. ej. al elegir un lugar)
    children: ReactNode;
}

// Boton de icono que abre una ventana (dialog modal: foco dentro, Esc o «Cerrar» la cierran,
// pulsar fuera tambien). Lo usa la leyenda.
export default function MapDialog({ label, icon, action, title, className = "", children }: MapDialogProps) {
    const dialogRef = useRef<HTMLDialogElement>(null);
    const titleId = useId();

    // sin showModal (navegadores antiguos, jsdom) se abre como ventana no modal
    const open = () => {
        const dialog = dialogRef.current;
        if (!dialog) return;
        if (typeof dialog.showModal === "function") dialog.showModal();
        else dialog.setAttribute("open", "");
    };
    const close = () => {
        const dialog = dialogRef.current;
        if (!dialog) return;
        if (typeof dialog.close === "function") dialog.close();
        else dialog.removeAttribute("open");
    };

    return (
        <>
            <button
                type="button"
                className={`map-dialog-button gomad-action ${action}`}
                aria-haspopup="dialog"
                aria-label={label}
                title={label}
                onClick={open}>
                {icon}
            </button>
            <dialog
                ref={dialogRef}
                className={`map-dialog gomad-component${className ? ` ${className}` : ""}`}
                aria-labelledby={titleId}
                // pulsar fuera (en el fondo) cierra: el contenido ocupa todo el dialog
                onClick={(e) => {
                    const target = e.target as HTMLElement;
                    if (target === e.currentTarget || target.closest("[data-dialog-close]")) close();
                }}>
                <div className="map-dialog__content">
                    <div className="map-dialog__header">
                        <h2 className="map-dialog__title" id={titleId}>
                            {title}
                        </h2>
                        <button
                            type="button"
                            className="map-dialog__close gomad-action gomad-action-close-map-dialog"
                            aria-label="Cerrar"
                            onClick={close}>
                            <Icon name="close" />
                        </button>
                    </div>
                    {children}
                </div>
            </dialog>
        </>
    );
}
