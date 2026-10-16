import type { SourcesResponse } from "../api/types";
import { getJson } from "./http";
import { simulate } from "./mock/delay";
import { sourcesMock } from "./mock/sources";
import { sampleDataMode } from "./mode";

// GET /api/sources: editor, licencia, URL y fechas de cada fuente (RF-19)
export function getSources(): Promise<SourcesResponse> {
    if (sampleDataMode()) return simulate(() => sourcesMock());
    return getJson<SourcesResponse>("/sources");
}
