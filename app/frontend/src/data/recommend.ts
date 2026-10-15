import type { RecommendRequest, RecommendResponse } from "../api/types";
import { postJson } from "./http";
import { simulate } from "./mock/delay";
import { recommendMock } from "./mock/recommend";
import { sampleDataMode } from "./mode";

// POST /api/recommend (la ubicacion va solo en el cuerpo)
export function recommend(req: RecommendRequest): Promise<RecommendResponse> {
    if (sampleDataMode()) return simulate(() => recommendMock(req));
    return postJson<RecommendResponse>("/recommend", req);
}
