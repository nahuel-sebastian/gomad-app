import { useMemo, useState, type ReactNode } from "react";
import type { LocationCandidate, Recommendation } from "../api/types";
import {
    AppStateContext,
    DEFAULT_PREFERENCES,
    type AppStateInit,
    type AppStateValue,
    type Preferences,
    type Search,
} from "./context";

export function AppStateProvider({
    children,
    init,
}: {
    children: ReactNode;
    init?: AppStateInit;
}) {
    const [origin, setOrigin] = useState<LocationCandidate | null>(
        init?.origin ?? null,
    );
    const [search, setSearch] = useState<Search | undefined>(init?.search);
    const [preferences, setPreferences] = useState<Preferences>({
        ...DEFAULT_PREFERENCES,
        ...init?.preferences,
        selectedProfiles: init?.preferences?.selectedProfiles
            ?? (init?.preferences?.profile && init.preferences.profile !== "general" ? [init.preferences.profile] : []),
    });
    const [results, setResults] = useState<Recommendation[]>(
        init?.results ?? [],
    );
    const [medicalDisclaimer, setMedicalDisclaimer] = useState<string | null>(
        null,
    );

    const value = useMemo<AppStateValue>(
        () => ({
            origin,
            setOrigin,
            search,
            setSearch,
            preferences,
            updatePreferences: (patch) =>
                setPreferences((prev) => ({ ...prev, ...patch })),
            resetPreferences: () => setPreferences(DEFAULT_PREFERENCES),
            results,
            setResults,
            medicalDisclaimer,
            setMedicalDisclaimer,
        }),
        [origin, search, preferences, results, medicalDisclaimer],
    );

    return (
        <AppStateContext.Provider value={value}>
            {children}
        </AppStateContext.Provider>
    );
}

