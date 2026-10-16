import { afterEach, describe, expect, it, vi } from "vitest";
import type { RecommendRequest } from "../api/types";
import { ApiError } from "../data/errors";
import { getJson, postJson } from "../data/http";

const json = (status: number, body: unknown) =>
    new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

// la promesa debe fallar: devuelve el ApiError (y si no falla, la prueba falla)
function failure(promise: Promise<unknown>): Promise<ApiError> {
    return promise.then(
        () => {
            throw new Error("la petición no falló");
        },
        (e: unknown) => e as ApiError,
    );
}

afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
});

describe("cliente HTTP", () => {
    it("hace GET a /api y devuelve el JSON", async () => {
        const fetchMock = vi.fn().mockResolvedValue(json(200, { status: "ok" }));
        vi.stubGlobal("fetch", fetchMock);
        await expect(getJson("/health")).resolves.toEqual({ status: "ok" });
        expect(fetchMock.mock.calls[0][0]).toBe("/api/health");
    });

    it("hace POST con el cuerpo en JSON", async () => {
        const fetchMock = vi.fn().mockResolvedValue(json(200, { ok: true }));
        vi.stubGlobal("fetch", fetchMock);
        await postJson("/route", { a: 1 });
        const init = fetchMock.mock.calls[0][1] as RequestInit;
        expect(init.method).toBe("POST");
        expect(init.body).toBe('{"a":1}');
        expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    });

    it("convierte un 422 de validación en ApiError legible", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(422, { detail: [{ msg: "x" }] })));
        const error = await failure(getJson("/location?text=ab"));
        expect(error).toBeInstanceOf(ApiError);
        expect(error.status).toBe(422);
        expect(error.message).toMatch(/no es válido/);
    });

    it("usa el detail de texto de la API", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(503, { detail: "Los datos todavía no están cargados." })));
        const error = await failure(getJson("/recommend"));
        expect(error).toMatchObject({ status: 503, message: "Los datos todavía no están cargados." });
    });

    it("un 500 sin JSON da un mensaje de servidor", async () => {
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("boom", { status: 500 })));
        const error = await failure(getJson("/x"));
        expect(error).toMatchObject({ status: 500 });
        expect(error.message).toMatch(/servidor/);
    });

    it("sin conexión da ApiError con estado 0", async () => {
        vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
        const error = await failure(getJson("/x"));
        expect(error).toMatchObject({ status: 0 });
        expect(error.message).toMatch(/conectar/);
    });

    it("corta la petición si tarda demasiado", async () => {
        vi.stubGlobal(
            "fetch",
            vi.fn((_url: string, init: RequestInit) =>
                new Promise((_resolve, reject) => {
                    init.signal!.addEventListener("abort", () =>
                        reject(new DOMException("aborted", "AbortError")),
                    );
                }),
            ),
        );
        const error = await failure(getJson("/x", 10));
        expect(error).toMatchObject({ status: 0 });
        expect(error.message).toMatch(/tarda demasiado/);
    });

    it("fuera de las pruebas, recommend llama a POST /api/recommend", async () => {
        vi.stubEnv("MODE", "production");
        const fetchMock = vi.fn().mockResolvedValue(json(200, { results: [], has_more: false, warnings: [], medical_disclaimer: "" }));
        vi.stubGlobal("fetch", fetchMock);
        const { recommend } = await import("../data/recommend");
        const req = { origin: { lat: 40.3, lon: -3.7 } } as RecommendRequest;
        await recommend(req);
        expect(fetchMock.mock.calls[0][0]).toBe("/api/recommend");
        expect(JSON.parse((fetchMock.mock.calls[0][1] as RequestInit).body as string)).toEqual(req);
    });
    it("fuera de las pruebas, getMunicipality llama a /api/municipality con las preferencias", async () => {
        vi.stubEnv("MODE", "production");
        const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json(200, { ine_code: "28065" })));
        vi.stubGlobal("fetch", fetchMock);
        const { getMunicipality } = await import("../data/municipality");
        await getMunicipality("28065", { activities: ["walk", "padel"], profile: "senior", companions: ["dog"] });
        expect(fetchMock.mock.calls[0][0]).toBe(
            "/api/municipality/28065?activities=walk&activities=padel&profile=senior&companions=dog",
        );
        await getMunicipality("28065");
        await getMunicipality("28065", { profile: "general", companions: [] });
        expect(fetchMock.mock.calls[1][0]).toBe("/api/municipality/28065");
        expect(fetchMock.mock.calls[2][0]).toBe("/api/municipality/28065");
    });

    it("getMunicipality con 404 o 503 lanza ApiError con su código", async () => {
        vi.stubEnv("MODE", "production");
        const { getMunicipality } = await import("../data/municipality");
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(404, { detail: "Municipio no encontrado" })));
        expect(await failure(getMunicipality("28999"))).toMatchObject({ status: 404 });
        vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(503, { detail: "Los datos todavía no están cargados." })));
        expect(await failure(getMunicipality("28065"))).toMatchObject({
            status: 503,
            message: "Los datos todavía no están cargados.",
        });
    });

    it("fuera de las pruebas, getSources llama a GET /api/sources", async () => {
        vi.stubEnv("MODE", "production");
        const fetchMock = vi.fn().mockResolvedValue(json(200, { sources: [] }));
        vi.stubGlobal("fetch", fetchMock);
        const { getSources } = await import("../data/sources");
        await expect(getSources()).resolves.toEqual({ sources: [] });
        expect(fetchMock.mock.calls[0][0]).toBe("/api/sources");
        expect((fetchMock.mock.calls[0][1] as RequestInit).method).toBe("GET");
    });
});
