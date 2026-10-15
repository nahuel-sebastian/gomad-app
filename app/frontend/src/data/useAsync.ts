import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";

export type AsyncStatus = "loading" | "error" | "success";

export interface AsyncState<T> {
    status: AsyncStatus;
    // se conservan los datos anteriores mientras se recalcula
    data: T | undefined;
    error: unknown;
    reload: () => void;
}

// Estado cargando/error/datos de una funcion de src/data.
// paso 3: se puede cambiar por TanStack Query sin tocar las pantallas.
export function useAsync<T>(
    load: () => Promise<T>,
    deps: DependencyList,
): AsyncState<T> {
    const [status, setStatus] = useState<AsyncStatus>("loading");
    const [data, setData] = useState<T | undefined>(undefined);
    const [error, setError] = useState<unknown>(null);
    const [attempt, setAttempt] = useState(0);
    const loadRef = useRef(load);
    loadRef.current = load;

    useEffect(() => {
        let current = true;
        setStatus("loading");
        setError(null);
        loadRef.current().then(
            (value) => {
                if (!current) return;
                setData(value);
                setStatus("success");
            },
            (reason: unknown) => {
                if (!current) return;
                setError(reason);
                setStatus("error");
            },
        );
        // la respuesta de una peticion vieja se descarta
        return () => {
            current = false;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [...deps, attempt]);

    const reload = useCallback(() => setAttempt((n) => n + 1), []);

    return { status, data, error, reload };
}
