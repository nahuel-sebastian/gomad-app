import type { MunicipalityResponse } from "../api/types";
import { simulate } from "./mock/delay";
import { MUNICIPALITIES, type MunicipalityItem } from "./mock/municipalities";
import { municipalityMock } from "./mock/municipality";

export type { MunicipalityItem };

// GET /api/municipality/{ine_code} (404 si no existe)
// paso 3: sustituir por la llamada real a /api/municipality/{ine_code}
export function getMunicipality(ineCode: string): Promise<MunicipalityResponse> {
    return simulate(() => municipalityMock(ineCode));
}

// Lista para el selector (P-09): no hay endpoint en el contrato.
// paso 3: sustituir por la lista que de la API (o /api/location)
export function listMunicipalities(): Promise<MunicipalityItem[]> {
    return simulate(() => MUNICIPALITIES.map((m) => ({ ...m })));
}
