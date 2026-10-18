import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { recommend } from "../data/recommend";
import { buildRecommendRequest } from "../lib/request";
import { DEFAULT_PREFERENCES } from "../state/context";
import { renderAt, SAMPLE_ORIGIN } from "./render";

// Pruebas de los hallazgos de la auditoria de accesibilidad (15/10)

const WITH_SEARCH = { origin: SAMPLE_ORIGIN, search: { activity: "walk", label: "Caminar" } };

async function withResults() {
    const data = await recommend(buildRecommendRequest(SAMPLE_ORIGIN.coordinate, "walk", DEFAULT_PREFERENCES));
    return { ...WITH_SEARCH, results: data.results, id: encodeURIComponent(data.results[0].destination.id) };
}

describe("hoja inferior (C2)", () => {
    it("pulsar el asa la despliega (el foco en el asa no la alterna)", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        await screen.findByRole("list", { name: "Resultados" });
        await user.click(screen.getByRole("button", { name: "Mostrar resultados" }));
        expect(screen.getByRole("button", { name: "Ocultar resultados" })).toHaveAttribute("aria-expanded", "true");
    });

    it("el foco al h1 al navegar no despliega la hoja", async () => {
        const { user } = renderAt("/", { origin: SAMPLE_ORIGIN });
        await user.click(await screen.findByRole("button", { name: "Caminar" }));
        await screen.findByRole("list", { name: "Resultados" });
        expect(screen.getByRole("button", { name: "Mostrar resultados" })).toHaveAttribute("aria-expanded", "false");
    });
});

describe("anuncios y foco (I1, I8)", () => {
    it("anuncia la ubicacion elegida", async () => {
        const { user } = renderAt("/");
        await user.click(screen.getByRole("button", { name: "Usar mi ubicación" }));
        const region = screen.getByRole("region", { name: "¿Desde dónde sales?" });
        expect(within(region).getByRole("status")).toHaveTextContent(/Ubicación elegida: Tu ubicación de ejemplo/);
    });

    it("el asistente anuncia el rechazo y la peticion de ubicacion en la region viva", async () => {
        const { user } = renderAt("/asistente");
        await user.type(screen.getByLabelText("¿Qué ruta quieres?"), "¿Puedo correr con asma?");
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        await waitFor(() => expect(screen.getAllByRole("status")[0]).toHaveTextContent(/no da consejo médico/));
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        await waitFor(() => expect(screen.getAllByRole("status")[0]).toHaveTextContent(/Antes, dinos dónde estás/));
    });

    it("la ruta anuncia cuando termina de calcular", async () => {
        const state = await withResults();
        renderAt(`/ruta/${state.id}`, state);
        await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent(/Ruta calculada: [\d,]+ k?m, \d+ min/));
    });

    it("el panel de preferencias anuncia los resultados recalculados", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        await screen.findByRole("list", { name: "Resultados" });
        await user.click(screen.getByRole("button", { name: /Ajustar/ }));
        await screen.findByRole("heading", { name: "Tus preferencias" });
        await user.click(screen.getByRole("button", { name: "Con personas mayores" }));
        await waitFor(() => expect(screen.getByText(/^\d+ resultados actualizados$/)).toHaveAttribute("role", "status"));
    });

    it("Ver más lleva el foco al primer resultado nuevo", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        await screen.findByRole("list", { name: "Resultados" });
        await user.click(screen.getByRole("button", { name: "Ver más opciones" }));
        await waitFor(() => {
            const links = within(screen.getByRole("list", { name: "Resultados" })).getAllByRole("link");
            expect(links).toHaveLength(6);
            expect(links[3]).toHaveFocus();
        });
    });
});

describe("tablas (I2, I3)", () => {
    it("la tabla horaria desplazable se puede enfocar con teclado", async () => {
        const state = await withResults();
        renderAt(`/resultados/${state.id}`, state);
        const region = screen.getByRole("region", { name: "Tabla de horas" });
        expect(region).toHaveAttribute("tabindex", "0");
    });

    it("la tabla de fuentes mantiene sus roles aunque el CSS la apile", async () => {
        renderAt("/fuentes");
        const table = await screen.findByRole("table", { name: "Aire y tiempo" });
        expect(table).toHaveAttribute("role", "table");
        expect(within(table).getAllByRole("row")[1]).toHaveAttribute("role", "row");
        expect(within(table).getAllByRole("cell")[0]).toHaveAttribute("role", "cell");
    });
});
