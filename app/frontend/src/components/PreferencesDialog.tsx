import * as Dialog from "@radix-ui/react-dialog";
import type { ReactElement } from "react";
import PreferencesForm from "./PreferencesForm";

interface PreferencesDialogProps {
    // boton que abre el dialogo (recibe el foco al cerrar)
    trigger: ReactElement;
}

// Hoja/dialogo de preferencias desde «Ajustar» (Radix Dialog: foco atrapado,
// Esc cierra y el foco vuelve al boton)
export default function PreferencesDialog({ trigger }: PreferencesDialogProps) {
    return (
        <Dialog.Root>
            <Dialog.Trigger asChild>{trigger}</Dialog.Trigger>
            <Dialog.Portal>
                <Dialog.Overlay className="sheet-overlay" />
                <Dialog.Content className="sheet">
                    <div className="sheet__header">
                        <Dialog.Title className="sheet__title">Tus preferencias</Dialog.Title>
                        <Dialog.Close asChild>
                            <button type="button" className="button button--primary">
                                Listo
                            </button>
                        </Dialog.Close>
                    </div>
                    <Dialog.Description className="muted">
                        Los cambios se aplican al momento; los resultados se recalculan solos.
                    </Dialog.Description>
                    <PreferencesForm />
                </Dialog.Content>
            </Dialog.Portal>
        </Dialog.Root>
    );
}
