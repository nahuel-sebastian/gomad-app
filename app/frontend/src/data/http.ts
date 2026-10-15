import { ApiError } from "./errors";

// Cliente de la API: misma maquina, prefijo /api (Caddy en produccion, proxy de Vite en desarrollo)
export const API_BASE = "/api";
const TIMEOUT_MS = 15_000;

async function errorMessage(response: Response): Promise<string> {
    let detail: unknown = null;
    try {
        detail = ((await response.json()) as { detail?: unknown })?.detail;
    } catch {
        // sin cuerpo JSON
    }
    if (typeof detail === "string" && detail) return detail;
    if (response.status === 422) return "Hay un dato que no es válido. Revisa lo que has escrito.";
    if (response.status === 404) return "No lo hemos encontrado.";
    if (response.status >= 500) return "El servidor no responde ahora. Inténtalo de nuevo en unos minutos.";
    return "No se pudo completar la petición.";
}

async function request<T>(path: string, init: RequestInit, timeoutMs: number): Promise<T> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(`${API_BASE}${path}`, { ...init, signal: controller.signal });
        if (!response.ok) throw new ApiError(response.status, await errorMessage(response));
        return (await response.json()) as T;
    } catch (error) {
        if (error instanceof ApiError) throw error;
        if (controller.signal.aborted) {
            throw new ApiError(0, "La respuesta tarda demasiado. Inténtalo de nuevo.");
        }
        throw new ApiError(0, "No se pudo conectar con el servidor. Comprueba tu conexión.");
    } finally {
        clearTimeout(timer);
    }
}

export function getJson<T>(path: string, timeoutMs = TIMEOUT_MS): Promise<T> {
    return request<T>(path, { method: "GET", headers: { Accept: "application/json" } }, timeoutMs);
}

export function postJson<T>(path: string, body: unknown, timeoutMs = TIMEOUT_MS): Promise<T> {
    return request<T>(
        path,
        {
            method: "POST",
            headers: { Accept: "application/json", "Content-Type": "application/json" },
            body: JSON.stringify(body),
        },
        timeoutMs,
    );
}
