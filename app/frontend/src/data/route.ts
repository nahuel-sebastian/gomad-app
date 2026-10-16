import type { RouteRequest, RouteResponse } from "../api/types";
import { postJson } from "./http";
import { simulate } from "./mock/delay";
import { routeMock } from "./mock/route";
import { sampleDataMode } from "./mode";

// POST /api/route (origen y destino solo en el cuerpo)
export function getRoute(req: RouteRequest): Promise<RouteResponse> {
    if (sampleDataMode()) return simulate(() => routeMock(req));
    return postJson<RouteResponse>("/route", req);
}
