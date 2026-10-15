import type { RouteRequest, RouteResponse } from "../api/types";
import { simulate } from "./mock/delay";
import { routeMock } from "./mock/route";

// POST /api/route
// paso 3: sustituir por la llamada real a /api/route
export function getRoute(req: RouteRequest): Promise<RouteResponse> {
    return simulate(() => routeMock(req));
}
