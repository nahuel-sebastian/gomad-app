import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as assistantApi from "../data/assistant";
import { ApiError } from "../data/errors";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "./render";

afterEach(() => {
    vi.restoreAllMocks();
});

describe("Asistente de rutas", () => {
    it("tiene los tres bloques y el formulario sin IA", async () => {
        const { container } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        expect(screen.getByRole("heading", { level: 1, name: "Asistente de rutas" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Tu petición" })).toBeNull();
        expect(screen.getByRole("heading", { level: 2, name: "Lo que he entendido" })).toBeInTheDocument();
        expect(screen.getByRole("heading", { level: 2, name: "La ruta propuesta" })).toBeInTheDocument();
        expect(screen.getByLabelText("¿Qué ruta quieres?")).toBeInTheDocument();
        const passBy = screen.getByRole("group", { name: "Pasar por" });
        expect(within(passBy).getAllByRole("checkbox")).toHaveLength(6);
        expect(passBy.querySelector(".icon-shopping_cart")).toHaveAttribute("aria-hidden", "true");
        expect(within(screen.getByRole("group", { name: "Evitar" })).getAllByRole("checkbox")).toHaveLength(2);
        await expectNoAxeViolations(container);
    });

    it("no muestra el aviso de respuestas de ejemplo", () => {
        renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        expect(screen.queryByText(/Respuestas de ejemplo/)).toBeNull();
        expect(screen.queryByRole("note")).toBeNull();
    });

    it("si interpretar falla, muestra el error", async () => {
        vi.spyOn(assistantApi, "interpret").mockRejectedValueOnce(new Error("red"));
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.type(screen.getByLabelText("¿Qué ruta quieres?"), "5 km con fuentes");
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        expect(
            await screen.findByText("Ahora no puedo interpretar el texto. Rellena los campos de abajo y pulsa «Calcular ruta»."),
        ).toBeInTheDocument();
    });

    it("con texto demasiado corto pide un poco mas con un ejemplo", async () => {
        const spy = vi.spyOn(assistantApi, "interpret");
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.type(screen.getByLabelText("¿Qué ruta quieres?"), "ok");
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        expect(
            await screen.findByText("Escribe un poco más. Por ejemplo: «5 km andando por un parque».", { selector: ".notice" }),
        ).toBeInTheDocument();
        expect(spy).not.toHaveBeenCalled();
    });

    const CLARIFICATION =
        "He apuntado: caminar, pasar por un área canina. Solo falta la distancia o el tiempo: por ejemplo, «5 km» o «45 minutos».";
    const partial = () =>
        vi.spyOn(assistantApi, "interpret").mockResolvedValueOnce({
            params: { activity: "walk", distance_km: null, duration_min: null, loop: true, pass_by: ["dog_area"], avoid: [] },
            clarification: CLARIFICATION,
            rejection: null,
        });

    it("con aclaracion sin cantidad vacia la distancia por defecto si no la has tocado", async () => {
        partial();
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        expect(screen.getByLabelText("Distancia (km)")).toHaveValue(5);
        await user.type(screen.getByLabelText("¿Qué ruta quieres?"), "pasear con el perro");
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        expect(await screen.findByText(CLARIFICATION, { selector: ".notice" })).toBeInTheDocument();
        expect(screen.getByLabelText("Distancia (km)")).toHaveValue(null);
        expect(screen.getByLabelText("Duración (min)")).toHaveValue(null);
    });

    it("con aclaracion y params rellena lo entendido, conserva lo escrito a mano y anuncia la aclaracion", async () => {
        const clarification = CLARIFICATION;
        partial();
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        const distance = screen.getByLabelText("Distancia (km)");
        await user.clear(distance);
        await user.type(distance, "3");
        const passBy = screen.getByRole("group", { name: "Pasar por" });
        await user.click(within(passBy).getByRole("checkbox", { name: "Parque" }));
        await user.click(within(screen.getByRole("group", { name: "Evitar" })).getByRole("checkbox", { name: "Cuestas" }));
        await user.type(screen.getByLabelText("¿Qué ruta quieres?"), "pasear con el perro");
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        expect(await screen.findByText(clarification, { selector: ".notice" })).toBeInTheDocument();
        expect(within(passBy).getByRole("checkbox", { name: "Área canina" })).toBeChecked();
        expect(within(passBy).getByRole("checkbox", { name: "Parque" })).toBeChecked();
        expect(within(screen.getByRole("group", { name: "Evitar" })).getByRole("checkbox", { name: "Cuestas" })).toBeChecked();
        expect(screen.getByLabelText("Distancia (km)")).toHaveValue(3);
        expect(screen.getByRole("status")).toHaveTextContent(clarification);
        await waitFor(() => expect(screen.getByLabelText("¿Qué ruta quieres?")).toHaveFocus());
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
        expect(await screen.findByText(/no da consejo médico/, { selector: ".notice" })).toBeInTheDocument();
    });

    it("pide aclaracion si es ambiguo", async () => {
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.type(screen.getByLabelText("¿Qué ruta quieres?"), "quiero dar un paseo");
        await user.click(screen.getByRole("button", { name: "Interpretar" }));
        expect(await screen.findByText(/Solo falta la distancia o el tiempo/, { selector: ".notice" })).toBeInTheDocument();
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
        expect(await screen.findByText(/Antes, dinos dónde estás/, { selector: ".notice" })).toBeInTheDocument();
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

    it("muestra el motivo del servidor si no hay donde hacer la ruta (422)", async () => {
        const detail = "No hay ningún punto de paso ni ningún parque cerca de tu ubicación para preparar la ruta.";
        vi.spyOn(assistantApi, "assistantRoute").mockRejectedValueOnce(new ApiError(422, detail));
        const { user } = renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        expect(await screen.findByText(detail)).toBeInTheDocument();
        expect(screen.queryByText("No se pudo calcular la ruta.")).toBeNull();
    });

    it("ofrece ida y vuelta (por defecto) o solo ida", () => {
        renderAt("/asistente", { origin: SAMPLE_ORIGIN });
        const group = screen.getByRole("group", { name: "Tipo de ruta" });
        expect(within(group).getByRole("radio", { name: "Ida y vuelta" })).toBeChecked();
        expect(within(group).getByRole("radio", { name: "Solo ida" })).not.toBeChecked();
        expect(within(group).queryByRole("radio", { name: "Circular" })).toBeNull();
    });
});
