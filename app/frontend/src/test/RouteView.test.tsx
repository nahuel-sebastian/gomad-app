import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Recommendation } from "../api/types";
import { recommend } from "../data/recommend";
import * as routeApi from "../data/route";
import { selectScenario } from "../data/scenarios";
import { buildRecommendRequest } from "../lib/request";
import { DEFAULT_PREFERENCES } from "../state/context";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "./render";

async function setup() {
    const data = await recommend(
        buildRecommendRequest(SAMPLE_ORIGIN.coordinate, "walk", DEFAULT_PREFERENCES),
    );
    const item: Recommendation = data.results[0];
    const path = `/ruta/${encodeURIComponent(item.destination.id)}`;
    return { item, path, init: { origin: SAMPLE_ORIGIN, results: data.results } };
}

afterEach(() => {
    vi.restoreAllMocks();
    selectScenario("neutral");
});

describe("Ruta saludable", () => {
    it("sin datos en memoria vuelve a Inicio (P-07)", async () => {
        renderAt("/ruta/ejemplo%3Aparque-arroyo");
        expect(
            await screen.findByText(/Los resultados no se guardan al recargar la página/),
        ).toBeInTheDocument();
    });

    it("compara recomendada y directa con metricas, PDI y descripcion", async () => {
        const { item, path, init } = await setup();
        const { container } = renderAt(path, init);
        expect(
            screen.getByRole("heading", { level: 1, name: `Ruta a ${item.destination.name}` }),
        ).toBeInTheDocument();
        const group = screen.getByRole("group", { name: "Variante de ruta" });
        expect(within(group).getByRole("radio", { name: /Ruta recomendada/ })).toBeChecked();
        const metrics = await screen.findByRole("list", { name: "Resumen de la ruta" });
        expect(metrics).toHaveTextContent("Zonas verdes");
        expect(metrics).toHaveTextContent("64 %");
        expect(metrics).toHaveTextContent("Desnivel");
        expect(metrics).toHaveTextContent("sin datos de desnivel");
        for (const icon of [".icon-route", ".icon-calendar_clock", ".icon-eco", ".icon-mountain"]) {
            expect(metrics.querySelector(icon)).toHaveAttribute("aria-hidden", "true");
        }
        const pois = screen.getByRole("list", { name: "En la ruta" });
        expect(pois).toHaveTextContent("2 fuentes");
        expect(pois).toHaveTextContent("5 bancos");
        expect(pois).toHaveTextContent("1 desfibrilador");
        expect(screen.getByText(/% por zona verde/, { selector: ".route-description" })).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("al cambiar a la directa cambia el resumen y se anuncia", async () => {
        const { path, init } = await setup();
        const { user } = renderAt(path, init);
        await screen.findByRole("list", { name: "Resumen de la ruta" });
        await user.click(screen.getByRole("radio", { name: /Ruta directa/ }));
        await waitFor(() =>
            expect(screen.getByRole("status")).toHaveTextContent("Mostrando la ruta directa"),
        );
        expect(screen.getByRole("list", { name: "Resumen de la ruta" })).toHaveTextContent("18 %");
    });

    it("avisa si la ruta es aproximada", async () => {
        selectScenario("family");
        const { path, init } = await setup();
        renderAt(path, init);
        expect(
            await screen.findByText(
                "Ruta aproximada en línea recta: no hay red peatonal en esta zona.",
            ),
        ).toBeInTheDocument();
        expect(screen.getByRole("list", { name: "Resumen de la ruta" })).toHaveTextContent(
            "sin datos",
        );
    });

    it("error con Reintentar", async () => {
        vi.spyOn(routeApi, "getRoute").mockRejectedValueOnce(new Error("red"));
        const { path, init } = await setup();
        const { user } = renderAt(path, init);
        expect(await screen.findByText("No se pudo calcular la ruta.")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(await screen.findByRole("list", { name: "Resumen de la ruta" })).toBeInTheDocument();
    });

    it("lista las fuentes de la ruta", async () => {
        const { path, init } = await setup();
        renderAt(path, init);
        const sources = await screen.findByRole("list", { name: "Fuentes de la ruta" });
        expect(sources).toHaveTextContent("OpenStreetMap");
        expect(sources).toHaveTextContent("Criterio propio");
    });
});
