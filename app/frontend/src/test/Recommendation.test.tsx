import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { Recommendation } from "../api/types";
import { recommend } from "../data/recommend";
import { selectScenario } from "../data/scenarios";
import { buildRecommendRequest } from "../lib/request";
import { heroVariantForDestination } from "../components/Hero";
import { DEFAULT_PREFERENCES } from "../state/context";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "./render";

async function sampleResults(
    activity: string | null = "walk",
    patch: Partial<typeof DEFAULT_PREFERENCES> = {},
): Promise<Recommendation[]> {
    const data = await recommend(
        buildRecommendRequest(SAMPLE_ORIGIN.coordinate, activity, {
            ...DEFAULT_PREFERENCES,
            ...patch,
        }),
    );
    return data.results;
}

function pathFor(item: Recommendation) {
    return `/resultados/${encodeURIComponent(item.destination.id)}`;
}

afterEach(() => selectScenario("neutral"));

describe("Detalle", () => {
    it("elige la ilustración del hero según el tipo de destino", async () => {
        const results = await sampleResults();
        const park = results.find((result) => result.destination.type === "park")!;
        const types = ["park", "trail", "recreation_area", "facility", "bathing_area"] as const;
        const examples: Recommendation[] = types.map((type) => ({
            ...park,
            destination: { ...park.destination, id: `test:${type}`, name: `Destino ${type}`, type },
        }));
        for (const item of examples) {
            const search = item.destination.type === "bathing_area" ? { activity: "swim", label: "Nadar" } : undefined;
            const view = renderAt(pathFor(item), { origin: SAMPLE_ORIGIN, search, results: examples });
            expect(view.container.querySelector(`.detail-media.hero--${item.destination.type} svg`)).toBeInTheDocument();
            view.unmount();
        }
    });

    it("usa palabras del título para variar el hero aunque el tipo sea genérico", async () => {
        const results = await sampleResults();
        const base = results[0];
        const cases = [
            { name: "Senda del Pinar", type: "park", variant: "trail" },
            { name: "Jardín de la Plaza", type: "park", variant: "trail" },
            { name: "Jardines del Retiro", type: "park", variant: "trail" },
            { name: "Jardín del Lago", type: "park", variant: "trail" },
            { name: "Área Recreativa del Lago", type: "park", variant: "recreation_area" },
            { name: "Piscina Municipal", type: "facility", variant: "facility" },
            { name: "Estadio Municipal", type: "park", variant: "facility" },
        ] as const;

        for (const { name, type, variant } of cases) {
            const item: Recommendation = {
                ...base,
                destination: { ...base.destination, id: `test:${variant}`, name, type },
            };
            const view = renderAt(pathFor(item), { origin: SAMPLE_ORIGIN, results: [item] });
            expect(view.container.querySelector(`.detail-media.hero--${variant} svg`)).toBeInTheDocument();
            view.unmount();
        }
    });

    it("usa el hero de baño para cualquier destino al elegir Nadar", async () => {
        const results = await sampleResults();
        const base = results[0];
        for (const type of ["park", "facility", "trail"] as const) {
            const item: Recommendation = {
                ...base,
                destination: { ...base.destination, id: `test:swim:${type}`, name: "Destino genérico", type },
            };
            const view = renderAt(pathFor(item), {
                origin: SAMPLE_ORIGIN,
                search: { activity: "swim", label: "Nadar" },
                results: [item],
            });
            expect(view.container.querySelector(".detail-media.hero--bathing_area svg")).toBeInTheDocument();
            view.unmount();
        }
    });

    it("no usa el hero de Nadar al elegir Pádel, incluso en una piscina", async () => {
        const results = await sampleResults();
        const base = results[0];
        for (const type of ["facility", "bathing_area"] as const) {
            const item: Recommendation = {
                ...base,
                destination: { ...base.destination, id: `test:padel:${type}`, name: "Piscina Municipal", type },
            };
            const view = renderAt(pathFor(item), {
                origin: SAMPLE_ORIGIN,
                search: { activity: "padel", label: "Pádel" },
                results: [item],
            });
            expect(view.container.querySelector(".detail-media.hero--facility svg")).toBeInTheDocument();
            view.unmount();
        }
    });

    it("usa área recreativa al correr y deja de alternar parques", () => {
        expect(heroVariantForDestination({ name: "Jardín de la Plaza", type: "park" }, "run")).toBe("recreation_area");
        expect(heroVariantForDestination({ name: "Parque del Arroyo", type: "park" }, "run")).toBe("recreation_area");
        expect(heroVariantForDestination({ name: "Parque del Arroyo", type: "park" }, "walk")).toBe("park");
    });

    it("sin resultados en memoria vuelve a Inicio con aviso (P-07)", async () => {
        renderAt("/resultados/ejemplo%3Aparque-arroyo");
        expect(
            await screen.findByText(/Los resultados no se guardan al recargar la página/),
        ).toBeInTheDocument();
    });

    it("muestra nombre, nota accesible, factores y enlaces", async () => {
        const results = await sampleResults();
        const item = results[0];
        const { container } = renderAt(pathFor(item), {
            origin: SAMPLE_ORIGIN,
            search: { activity: "walk", label: "Caminar" },
            results,
        });
        expect(
            screen.getByRole("heading", { level: 1, name: item.destination.name }),
        ).toBeInTheDocument();
        expect(screen.getByText(/^Nota \d,\d sobre 10/)).toBeInTheDocument();
        const factors = screen.getByRole("list", { name: "Nota por factor" });
        expect(within(factors).getAllByRole("listitem")).toHaveLength(5);
        expect(
            screen.getByRole("link", { name: "Ver ruta en el mapa" }),
        ).toHaveAttribute("href", `/ruta/${encodeURIComponent(item.destination.id)}`);
        expect(
            screen.getByRole("link", { name: "Ver otras opciones" }),
        ).toHaveAttribute("href", "/resultados");
        expect(screen.getByText(/No es consejo médico/, { selector: ".detail-disclaimer" })).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("resume la explicación en puntos y deja las fuentes en su sección", async () => {
        const [base] = await sampleResults();
        const item: Recommendation = {
            ...base,
            explanation: "Ahora no: mejor a las 17:00 (lluvia: 58 % de probabilidad (umbral de criterio propio)). Parque de los Pinos, a 900 m (12 min a pie); nota 7,8 sobre 10. Destaca por cercanía y adecuación a la actividad. Fuentes: Previsión horaria (Open-Meteo) (18/10 a las 13:55).",
        };
        renderAt(pathFor(item), { origin: SAMPLE_ORIGIN, results: [item] });

        const summary = screen.getByRole("list", { name: "Resumen de la recomendación" });
        expect(within(summary).getAllByRole("listitem")).toHaveLength(3);
        expect(summary).toHaveTextContent("Mejor salir a las 17:00");
        expect(summary).toHaveTextContent("58 % de probabilidad de lluvia");
        expect(summary).toHaveTextContent("GoMAD aplica su propio umbral");
        expect(summary).toHaveTextContent("Puntos fuertes: cercanía y adecuación a la actividad");
        expect(summary).not.toHaveTextContent("Fuentes:");
        expect(summary).not.toHaveTextContent("Parque de los Pinos");
    });

    it("muestra subtítulos sin prefijo y «Sin datos» cuando falta la nota", async () => {
        const results = await sampleResults();
        const item = results.find((r) => r.factors.some((f) => f.value === null))!;
        renderAt(pathFor(item), { origin: SAMPLE_ORIGIN, results });
        const factors = screen.getByRole("list", { name: "Nota por factor" });
        expect(within(factors).getByText("Sin datos", { selector: ".factor-list__nodata" })).toBeInTheDocument();
        const proximity = item.factors.find((factor) => factor.factor === "proximity")!;
        const proximityCard = within(factors).getByText("Cercanía y rapidez").closest("li")!;
        expect(proximityCard).toHaveTextContent(proximity.text.replace(/^.*?:\s*/, "").replace(/^./, (first) => first.toUpperCase()));
        expect(proximityCard).not.toHaveTextContent("Cercanía:");
    });

    it("pinta la linea horaria como tabla con la mejor hora en texto", async () => {
        const results = await sampleResults();
        renderAt(pathFor(results[0]), { origin: SAMPLE_ORIGIN, results });
        const table = screen.getByRole("table", { name: /Nota por hora/ });
        const rows = within(table).getAllByRole("row");
        expect(rows.length).toBeGreaterThan(2);
        expect(within(table).getByText("Mejor hora")).toBeInTheDocument();
        expect(within(table).getAllByRole("rowheader").length).toBe(rows.length - 1);
    });

    it("usa «Sin datos» en la tabla y omite el aviso si ahora se puede salir", async () => {
        const [base] = await sampleResults();
        const item: Recommendation = {
            ...base,
            hours: [
                { ...base.hours[0], score: null, temperature_c: null, precip_prob: null, aqi_category: null, outdoor_ok: true },
                ...base.hours.slice(1),
            ],
        };
        renderAt(pathFor(item), { origin: SAMPLE_ORIGIN, results: [item] });
        const table = screen.getByRole("table", { name: /Nota por hora/ });
        expect(within(table).getAllByText("Sin datos").length).toBeGreaterThanOrEqual(4);
        expect(screen.queryByText(/La mejor hora para esta actividad/, { selector: ".detail-callout" })).not.toBeInTheDocument();
    });

    it("Carmen: el aviso explica el motivo y la mejor hora queda solo en la tabla", async () => {
        selectScenario("carmen");
        const results = await sampleResults("walk", { profile: "senior" });
        const outdoor = results.find((r) => !r.indoor_alternative)!;
        renderAt(pathFor(outdoor), { origin: SAMPLE_ORIGIN, results });
        const callout = screen.getByText(/Ahora no:/, { selector: ".detail-callout" });
        expect(callout).not.toHaveTextContent("Mejor a las");
        expect(screen.getByRole("table", { name: /Nota por hora/ })).toHaveTextContent("Mejor hora");
        expect(screen.queryByRole("list", { name: "Motivos por hora" })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Alternativa cubierta/ })).toBeInTheDocument();
    });

    it("Lucía: muestra la recomendacion oficial del BOE que llega en reasons (P-05)", async () => {
        selectScenario("lucia");
        const results = await sampleResults("run", { profile: "sensitive" });
        renderAt(pathFor(results[0]), { origin: SAMPLE_ORIGIN, results });
        expect(screen.getAllByText(/Recomendación oficial \(BOE\)/).length).toBeGreaterThan(0);
    });

    it("lista las fuentes con fecha y «criterio propio»", async () => {
        const results = await sampleResults();
        renderAt(pathFor(results[0]), { origin: SAMPLE_ORIGIN, results });
        const sources = screen.getByRole("list", { name: "Fuentes de los datos" });
        expect(sources).toHaveTextContent(/Previsión horaria \(Open-Meteo\): \d{2}\/\d{2} \d{2}:\d{2}/);
        expect(within(sources).getByText("Previsión horaria (Open-Meteo):").tagName).toBe("STRONG");
        expect(sources).toHaveTextContent("Criterio propio");
    });
});
