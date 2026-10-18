import { afterEach, describe, expect, it } from "vitest";
import type { RecommendRequest } from "../api/types";
import { getActivities } from "../data/activities";
import { assistantRoute, interpret } from "../data/assistant";
import { ApiError } from "../data/errors";
import { isSampleLocation, sampleLocation, searchLocation } from "../data/location";
import { setMockScenario } from "../data/mock/scenario";
import { getMunicipality, listMunicipalities } from "../data/municipality";
import { recommend } from "../data/recommend";
import { getRoute } from "../data/route";
import { getSources } from "../data/sources";

const ORIGIN = { lat: 40.3057, lon: -3.7329 };

function request(patch: Partial<RecommendRequest> = {}): RecommendRequest {
    return {
        origin: ORIGIN,
        activity: "walk",
        window_start: "2026-10-15T18:00:00",
        window_end: "2026-10-15T21:00:00",
        duration_min: 45,
        max_distance_m: 3000,
        setting: "any",
        profile: "general",
        companions: [],
        weights: null,
        limit: 3,
        offset: 0,
        ...patch,
    };
}

afterEach(() => setMockScenario("neutral"));

describe("actividades", () => {
    it("devuelve las 8 actividades del catalogo por id", async () => {
        const data = await getActivities();
        expect(data.activities.map((a) => a.id)).toEqual([
            "walk",
            "run",
            "swim",
            "padel",
            "tennis",
            "football",
            "basketball",
            "gym",
        ]);
        expect(data.profiles).toEqual([
            "general",
            "senior",
            "stroller",
            "sensitive",
        ]);
        expect(data.default_weights.proximity).toBe(0.3);
    });
});

describe("recomendar", () => {
    it("devuelve 3 resultados ordenados por nota con aviso medico", async () => {
        const data = await recommend(request());
        expect(data.results).toHaveLength(3);
        const scores = data.results.map((r) => r.score);
        expect([...scores].sort((a, b) => b - a)).toEqual(scores);
        expect(data.medical_disclaimer).toMatch(/No es consejo médico/);
        expect(data.results[0].destination.name).toMatch(/\(ejemplo\)/);
    });

    it("cambia el orden al mover los pesos (dos personas, mismo sitio)", async () => {
        const near = await recommend(
            request({
                weights: {
                    proximity: 1,
                    suitability: 0,
                    green: 0,
                    air: 0,
                    weather: 0,
                },
            }),
        );
        const clean = await recommend(
            request({
                weights: {
                    proximity: 0,
                    suitability: 0,
                    green: 0.5,
                    air: 0.5,
                    weather: 0,
                },
            }),
        );
        expect(near.results[0].destination.id).not.toBe(
            clean.results[0].destination.id,
        );
    });

    it("con Sorpréndeme da 3 opciones de tipos distintos", async () => {
        const data = await recommend(request({ activity: null }));
        const types = new Set(data.results.map((r) => r.destination.type));
        expect(types.size).toBe(3);
    });

    it("pagina con offset y has_more", async () => {
        const first = await recommend(request());
        expect(first.has_more).toBe(true);
        const more = await recommend(request({ offset: 3 }));
        expect(more.results.length).toBeGreaterThan(0);
        const ids = new Set(first.results.map((r) => r.destination.id));
        expect(more.results.some((r) => ids.has(r.destination.id))).toBe(
            false,
        );
    });

    it("queda vacio si la distancia maxima es muy corta", async () => {
        const data = await recommend(request({ max_distance_m: 200 }));
        expect(data.results).toEqual([]);
        expect(data.has_more).toBe(false);
    });

    it("con todos los pesos a 0 usa los de por defecto y lo avisa", async () => {
        const data = await recommend(
            request({
                weights: {
                    proximity: 0,
                    suitability: 0,
                    green: 0,
                    air: 0,
                    weather: 0,
                },
            }),
        );
        expect(data.warnings.join(" ")).toMatch(/pesos por defecto/);
        expect(data.results).toHaveLength(3);
    });

    it("solo devuelve cubiertas si se pide interior", async () => {
        const data = await recommend(
            request({ activity: "swim", setting: "indoor" }),
        );
        expect(data.results.length).toBeGreaterThan(0);
        expect(data.results.every((r) => r.destination.covered)).toBe(true);
    });

    it("rechaza una ventana horaria invertida como la API (422)", async () => {
        await expect(
            recommend(
                request({
                    window_start: "2026-10-15T21:00:00",
                    window_end: "2026-10-15T18:00:00",
                }),
            ),
        ).rejects.toMatchObject({ status: 422 });
    });

    it("escenario Carmen: calor ahora, mejor a las 20:30 y alternativa cubierta", async () => {
        setMockScenario("carmen");
        const data = await recommend(request({ profile: "senior" }));
        const outdoor = data.results.find((r) => !r.indoor_alternative)!;
        expect(outdoor.hours[0].outdoor_ok).toBe(false);
        expect(outdoor.best_hour).toBe("2026-07-15T20:30:00");
        expect(data.results.some((r) => r.indoor_alternative)).toBe(true);
    });

    it("escenario Lucia: ozono regular o peor ahora y mejor temprano", async () => {
        setMockScenario("lucia");
        const data = await recommend(
            request({ activity: "run", profile: "sensitive" }),
        );
        const first = data.results[0];
        expect(["moderate", "poor"]).toContain(first.hours[0].aqi_category);
        expect(first.best_hour).toMatch(/T07:00:00$/);
    });

    it("incluye algun factor sin datos (null) y su aviso", async () => {
        const data = await recommend(request());
        const factors = data.results.flatMap((r) => r.factors);
        expect(factors.some((f) => f.value === null)).toBe(true);
        expect(data.warnings.length).toBeGreaterThan(0);
    });
});

describe("ruta", () => {
    it("devuelve directa y saludable; la saludable con mas verde", async () => {
        const data = await getRoute({
            origin: ORIGIN,
            destination: { lat: 40.31, lon: -3.72 },
            profile: "general",
            weights: null,
        });
        expect(data.direct.kind).toBe("direct");
        expect(data.healthy.kind).toBe("healthy");
        expect(data.healthy.green_pct!).toBeGreaterThan(
            data.direct.green_pct!,
        );
        expect(data.healthy.geometry).toMatchObject({ type: "LineString" });
    });
});

describe("municipios", () => {
    it("lista los 179 municipios con codigo INE", async () => {
        const list = await listMunicipalities();
        expect(list).toHaveLength(179);
        expect(list.find((m) => m.ine_code === "28065")?.name).toBe("Getafe");
    });

    it("devuelve indicadores con algun valor sin datos", async () => {
        const data = await getMunicipality("28065");
        expect(data.name).toBe("Getafe");
        expect(data.indicators.some((i) => i.value === null)).toBe(true);
        expect(data.fit.length).toBeGreaterThan(0);
    });

    it("da 404 con un codigo inexistente", async () => {
        const error = await getMunicipality("28999").catch((e) => e);
        expect(error).toBeInstanceOf(ApiError);
        expect(error.status).toBe(404);
    });
});

describe("ubicacion", () => {
    it("busca candidatos por texto", async () => {
        const data = await searchLocation("Getafe");
        expect(data.candidates.length).toBeGreaterThan(0);
        expect(data.candidates[0].ine_code).toBe("28065");
    });

    it("no encuentra nada con un texto raro", async () => {
        const data = await searchLocation("zzzzzz");
        expect(data.candidates).toEqual([]);
    });

    it("rechaza textos de menos de 3 caracteres (422)", async () => {
        await expect(searchLocation("ge")).rejects.toMatchObject({
            status: 422,
        });
    });
});

describe("asistente", () => {
    it("interpreta una peticion completa", async () => {
        const data = await interpret(
            "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado",
        );
        expect(data.params).toMatchObject({
            activity: "walk",
            distance_km: 15,
            pass_by: expect.arrayContaining([
                "park",
                "fountain",
                "bench",
                "supermarket",
            ]),
        });
        expect(data.rejection).toBeNull();
    });

    it("rechaza el consejo medico", async () => {
        const data = await interpret(
            "¿Puedo correr si tengo la tensión alta?",
        );
        expect(data.params).toBeNull();
        expect(data.rejection).toMatch(/consejo médico/);
    });

    it("pide aclaracion si falta la distancia o la duracion", async () => {
        // con aclaracion devuelve lo entendido (39cad87): actividad sin cantidad
        const data = await interpret("quiero dar un paseo");
        expect(data.clarification).toBeTruthy();
        expect(data.params?.distance_km).toBeNull();
        expect(data.params?.duration_min).toBeNull();
    });

    it("comprueba condicion por condicion", async () => {
        const data = await assistantRoute({
            origin: ORIGIN,
            params: {
                activity: "walk",
                distance_km: 5,
                duration_min: null,
                loop: true,
                pass_by: ["park", "bench"],
                avoid: ["traffic"],
            },
        });
        expect(data.conditions.some((c) => c.met)).toBe(true);
        expect(data.conditions.some((c) => !c.met)).toBe(true);
        expect(data.written_by_ai).toBe(false);
    });
});

describe("fuentes", () => {
    it("lista fuentes con licencia y fecha", async () => {
        const data = await getSources();
        const licenses = data.sources.map((s) => s.license).join(" ");
        expect(licenses).toMatch(/CC BY 4.0/);
        expect(licenses).toMatch(/ODbL/);
        expect(data.sources.some((s) => s.last_refresh === null)).toBe(true);
    });
});

describe("ubicacion de ejemplo (paso 3: GPS)", () => {
    it("sampleLocation devuelve un candidato de ejemplo y isSampleLocation lo reconoce", () => {
        const sample = sampleLocation();
        expect(sample.municipality).toBe("Getafe");
        expect(sample.label).toMatch(/ejemplo/);
        expect(isSampleLocation(sample)).toBe(true);
        expect(isSampleLocation({ ...sample, label: "Otra" })).toBe(false);
    });
});
