import { createContext, useContext } from "react";
import type {
    Companion,
    LocationCandidate,
    Profile,
    Recommendation,
    Setting,
    Weights,
} from "../api/types";

// Estado de la app en memoria (sin localStorage ni sessionStorage).
// La ubicacion nunca sale de aqui: ni URL, ni titulo, ni almacenamiento.

export interface Preferences {
    profile: Profile;
    companions: Companion[];
    // null = pesos por defecto del servidor
    weights: Weights | null;
    durationMin: number;
    maxDistanceM: number;
    setting: Setting;
    // ventana horaria: desde ahora hasta ahora + windowHours (P-06)
    windowHours: number;
}

export const DEFAULT_PREFERENCES: Preferences = {
    profile: "general",
    companions: [],
    weights: null,
    durationMin: 45,
    maxDistanceM: 3000,
    setting: "any",
    windowHours: 3,
};

// Busqueda en curso: undefined = ninguna; activity null = «Sorpréndeme»
export interface Search {
    activity: string | null;
    // etiqueta de la actividad (de /activities) para el titulo
    label?: string;
}

export interface AppStateValue {
    origin: LocationCandidate | null;
    setOrigin: (origin: LocationCandidate | null) => void;
    search: Search | undefined;
    setSearch: (search: Search | undefined) => void;
    preferences: Preferences;
    updatePreferences: (patch: Partial<Preferences>) => void;
    resetPreferences: () => void;
    // ultimos resultados mostrados (los usan Detalle y Ruta)
    results: Recommendation[];
    setResults: (results: Recommendation[]) => void;
    medicalDisclaimer: string | null;
    setMedicalDisclaimer: (text: string | null) => void;
}

export type AppStateInit = Partial<
    Pick<AppStateValue, "origin" | "search" | "results">
> & { preferences?: Partial<Preferences> };

export const AppStateContext = createContext<AppStateValue | null>(null);

export function useAppState(): AppStateValue {
    const value = useContext(AppStateContext);
    if (!value) {
        throw new Error("useAppState fuera de AppStateProvider");
    }
    return value;
}
