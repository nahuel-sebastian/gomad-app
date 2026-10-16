import type { Companion, MunicipalityResponse, Profile } from "../api/types";
import { getJson } from "./http";
import { simulate } from "./mock/delay";
import { MUNICIPALITIES, type MunicipalityItem } from "./mock/municipalities";
import { municipalityMock } from "./mock/municipality";
import { sampleDataMode } from "./mode";

export type { MunicipalityItem };

// Preferencias para el encaje (RF-18); todas opcionales
export interface MunicipalityPrefs {
    activities?: string[];
    profile?: Profile;
    companions?: Companion[];
}

function prefsQuery(prefs: MunicipalityPrefs): string {
    const params = new URLSearchParams();
    for (const activity of prefs.activities ?? []) params.append("activities", activity);
    // general es el valor por defecto del servidor: no hace falta enviarlo
    if (prefs.profile && prefs.profile !== "general") params.append("profile", prefs.profile);
    for (const companion of prefs.companions ?? []) params.append("companions", companion);
    const query = params.toString();
    return query ? `?${query}` : "";
}

// GET /api/municipality/{ine_code}?activities=…&profile=…&companions=… (404 si no existe)
export function getMunicipality(ineCode: string, prefs: MunicipalityPrefs = {}): Promise<MunicipalityResponse> {
    if (sampleDataMode()) return simulate(() => municipalityMock(ineCode));
    return getJson<MunicipalityResponse>(`/municipality/${encodeURIComponent(ineCode)}${prefsQuery(prefs)}`);
}

// Lista para el selector (P-09): el contrato no tiene endpoint de lista, asi que es la lista
// estatica de IDEM (179 municipios con su centro) tambien fuera de las pruebas.
export function listMunicipalities(): Promise<MunicipalityItem[]> {
    return simulate(() => MUNICIPALITIES.map((m) => ({ ...m })));
}
