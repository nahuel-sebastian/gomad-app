import type { SourcesResponse } from "../api/types";
import { simulate } from "./mock/delay";
import { sourcesMock } from "./mock/sources";

// GET /api/sources
// paso 3: sustituir por la llamada real a /api/sources
export function getSources(): Promise<SourcesResponse> {
    return simulate(() => sourcesMock());
}
