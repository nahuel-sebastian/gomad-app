import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as assistantApi from "../data/assistant";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "../test/render";

afterEach(() => {
    vi.restoreAllMocks();
});

describe("Asistente de rutas", () => {
    it("tiene los tres bloques y el formulario sin IA", async () => {
        const { container } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        expect(screen.getByRole("heading", { level: 1, name: "Asistente de rutas" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { level: 2, name: "Tu petición" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { level: 2, name: "Lo que he entendido" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { level: 2, name: "La ruta propuesta" })).toBeInTheDocument();
        expect(screen.getByLabelText("¿Qué ruta quieres?")).toBeInTheDocument();
        expect(within(screen.getByRole("group", { name: "Pasar por" })).getAllByRole("checkbox")).toHaveLength(6);
        expect(within(screen.getByRole("group", { name: "Evitar" })).getAllByRole("checkbox")).toHaveLength(2);
        await expectNoAxeViolations(container);
    });

    it("interpreta el texto, rellena los controles y solo envia el texto", async () => {
        const spy = vi.spyOn(assistantApi, "interpret");
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.type(
            screen.getByLabelText("¿Qué ruta quieres?"),
            "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado",
        );
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        await waitFor(() => expect(screen.getByLabelText("Distancia (km)")).toHaveValue(15));
        const passBy = screen.getByRole("group", { name: "Pasar por" });
        expect(within(passBy).getByRole("checkbox", { name: "Parque" })).toBeChecked();
        expect(within(passBy).getByRole("checkbox", { name: "Supermercado" })).toBeChecked();
        expect(within(passBy).getByRole("checkbox", { name: "Área canina" })).not.toBeChecked();
        expect(spy).toHaveBeenCalledWith(
            "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado",
        );
        expect(spy.mock.calls[0]).toHaveLength(1);
    });

    it("rechaza el consejo medico", async () => {
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.type(screen.getByLabelText("¿Qué ruta quieres?"), "¿Puedo correr con la tensión alta?");
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        expect(await screen.findByText(/no da consejo médico/)).toBeInTheDocument();
    });

    it("pide aclaracion si es ambiguo", async () => {
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.type(screen.getByLabelText("¿Qué ruta quieres?"), "quiero dar un paseo");
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        expect(await screen.findByText(/¿Qué distancia o cuánto tiempo/)).toBeInTheDocument();
        await waitFor(() => expect(screen.getByLabelText("¿Qué ruta quieres?")).toHaveFocus());
    });

    it("calcula con el formulario sin escribir texto y muestra cumple/no cumple", async () => {
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        const distance = screen.getByLabelText("Distancia (km)");
        await user.clear(distance);
        await user.type(distance, "5");
        const passBy = screen.getByRole("group", { name: "Pasar por" });
        await user.click(within(passBy).getByRole("checkbox", { name: "Parque" }));
        await user.click(within(passBy).getByRole("checkbox", { name: "Supermercado" }));
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        const conditions = await screen.findByRole("list", { name: "Condiciones" });
        expect(within(conditions).getAllByText("Cumple").length).toBeGreaterThan(0);
        expect(within(conditions).getAllByText("No cumple").length).toBeGreaterThan(0);
        expect(screen.getByText("Explicación generada sin IA.")).toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent(/Ruta calculada: cumple \d+ de \d+ condiciones/);
    });

    it("valida que haya distancia o duracion", async () => {
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.clear(screen.getByLabelText("Distancia (km)"));
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        expect(await screen.findByText("Indica una distancia o una duración.")).toBeInTheDocument();
    });

    it("sin ubicacion pide elegirla antes de calcular", async () => {
        const { user } = renderAt("/asistente");
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        expect(await screen.findByText(/Antes, dinos dónde estás/)).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Usar mi ubicación" })).toBeInTheDocument();
    });

    it("error al calcular con Reintentar", async () => {
        vi.spyOn(assistantApi, "assistantRoute").mockRejectedValueOnce(new Error("red"));
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        expect(await screen.findByText("No se pudo calcular la ruta.")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(await screen.findByRole("list", { name: "Condiciones" })).toBeInTheDocument();
    });
});
