import type { ReactNode } from "react";

interface ErrorMessageProps {
    message: string;
    onRetry?: () => void;
    children?: ReactNode;
}

// Error de carga con «Reintentar» (pantallas §0, estados)
export default function ErrorMessage({ message, onRetry, children }: ErrorMessageProps) {
    return (
        <div className="notice notice--bad" role="alert">
            <p>{message}</p>
            <div className="notice__actions">
                {onRetry && (
                    <button type="button" className="button" onClick={onRetry}>
                        Reintentar
                    </button>
                )}
                {children}
            </div>
        </div>
    );
}
