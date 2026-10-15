import type {
    AssistantRouteRequest,
    AssistantRouteResponse,
    InterpretResponse,
} from "../api/types";
import { assistantRouteMock, interpretMock } from "./mock/assistant";
import { simulate } from "./mock/delay";

// POST /api/assistant/interpret: solo el texto, NUNCA la ubicacion
// paso 3: sustituir por la llamada real a /api/assistant/interpret
export function interpret(text: string): Promise<InterpretResponse> {
    return simulate(() => interpretMock(text));
}

// POST /api/assistant/route: aqui si va la ubicacion (en el cuerpo)
// paso 3: sustituir por la llamada real a /api/assistant/route
export function assistantRoute(
    req: AssistantRouteRequest,
): Promise<AssistantRouteResponse> {
    return simulate(() => assistantRouteMock(req));
}
