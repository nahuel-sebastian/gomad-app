import type { RecommendRequest, RecommendResponse } from "../api/types";
import { simulate } from "./mock/delay";
import { recommendMock } from "./mock/recommend";

// POST /api/recommend (la ubicacion va solo en el cuerpo)
// paso 3: sustituir por la llamada real a /api/recommend
export function recommend(req: RecommendRequest): Promise<RecommendResponse> {
    return simulate(() => recommendMock(req));
}
