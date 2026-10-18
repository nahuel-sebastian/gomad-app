import type {
    AssistantRouteRequest,
    AssistantRouteResponse,
    InterpretResponse,
} from "../api/types";
import { postJson } from "./http";
import { assistantRouteMock, interpretMock } from "./mock/assistant";
import { simulate } from "./mock/delay";
import { sampleDataMode } from "./mode";

// POST /api/assistant/interpret: solo el texto, NUNCA la ubicacion
export function interpret(text: string): Promise<InterpretResponse> {
    if (sampleDataMode()) return simulate(() => interpretMock(text));
    return postJson<InterpretResponse>("/assistant/interpret", { text });
}

// POST /api/assistant/route: aqui si va la ubicacion (en el cuerpo)
export function assistantRoute(
    req: AssistantRouteRequest,
): Promise<AssistantRouteResponse> {
    if (sampleDataMode()) return simulate(() => assistantRouteMock(req));
    return postJson<AssistantRouteResponse>("/assistant/route", req);
}
