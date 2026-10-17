import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import type { Recommendation } from "../api/types";
import { recommend } from "../data/recommend";
import { selectScenario } from "../data/scenarios";
import { buildRecommendRequest } from "../lib/request";
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

    it("dice «sin datos (no cuenta en la nota)» en un factor null", async () => {
        const results = await sampleResults();
        const item = results.find((r) => r.factors.some((f) => f.value === null))!;
        renderAt(pathFor(item), { origin: SAMPLE_ORIGIN, results });
        expect(
            screen.getAllByText(/sin datos \(no cuenta en la nota\)/).length,
        ).toBeGreaterThan(0);
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

    it("Carmen: «Ahora no» con la mejor hora y la alternativa cubierta", async () => {
        selectScenario("carmen");
        const results = await sampleResults("walk", { profile: "senior" });
        const outdoor = results.find((r) => !r.indoor_alternative)!;
        renderAt(pathFor(outdoor), { origin: SAMPLE_ORIGIN, results });
        expect(
            screen.getByText(/Ahora no:/, { selector: ".detail-callout" }),
        ).toHaveTextContent("Mejor a las 20:30");
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
        expect(sources).toHaveTextContent(/Previsión horaria \(Open-Meteo\) · \d{2}\/\d{2} \d{2}:\d{2}/);
        expect(sources).toHaveTextContent("criterio propio");
    });
});
