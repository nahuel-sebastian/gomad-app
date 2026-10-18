import { afterEach, describe, expect, it, vi } from "vitest";
import type { AssistantRouteRequest } from "../api/types";
import { assistantRoute, interpret } from "../data/assistant";

afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
});

function ok(body: unknown) {
    return vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status: 200 }));
}

describe("asistente contra la API", () => {
    it("interpret hace POST a /api/assistant/interpret solo con el texto", async () => {
        vi.stubEnv("MODE", "production");
        const body = { params: null, clarification: "¿Qué distancia?", rejection: null };
        const fetchMock = ok(body);
        vi.stubGlobal("fetch", fetchMock);
        expect(await interpret("5 km")).toEqual(body);
        const [url, init] = fetchMock.mock.calls[0];
        expect(url).toBe("/api/assistant/interpret");
        expect(init.method).toBe("POST");
        expect(JSON.parse(init.body)).toEqual({ text: "5 km" });
    });

    it("assistantRoute hace POST a /api/assistant/route con la peticion", async () => {
        vi.stubEnv("MODE", "production");
        const req: AssistantRouteRequest = {
            origin: { lat: 40.3057, lon: -3.7329 },
            params: { activity: "walk", distance_km: 5, duration_min: null, loop: true, pass_by: ["park"], avoid: [] },
        };
        const fetchMock = ok({ route: null, conditions: [], explanation: "", written_by_ai: false });
        vi.stubGlobal("fetch", fetchMock);
        await assistantRoute(req);
        const [url, init] = fetchMock.mock.calls[0];
        expect(url).toBe("/api/assistant/route");
        expect(JSON.parse(init.body)).toEqual(req);
    });
});
