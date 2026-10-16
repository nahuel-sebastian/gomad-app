import type { ReactNode } from "react";

interface ErrorMessageProps {
    message: string;
    onRetry?: () => void;
    children?: ReactNode;
}

// Error de carga con «Reintentar» (pantallas §0, estados)
export default function ErrorMessage({ message, onRetry, children }: ErrorMessageProps) {
    return (
        <div className="notice notice--bad gomad-component gomad-error-message" role="alert">
            <p>{message}</p>
            <div className="notice__actions">
                {onRetry && (
                    <button type="button" className="button gomad-action gomad-action-retry" onClick={onRetry}>
                        Reintentar
                    </button>
                )}
                {children}
            </div>
        </div>
    );
}
