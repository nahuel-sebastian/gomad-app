import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as activitiesApi from "../data/activities";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "../test/render";

afterEach(() => {
    vi.restoreAllMocks();
});

describe("Inicio", () => {
    it("tiene un h1 neutro, no fijo a buen tiempo", () => {
        renderAt("/");
        const h1 = screen.getByRole("heading", { level: 1 });
        expect(h1).toHaveTextContent("¿Qué te apetece hacer hoy?");
        expect(h1).not.toHaveTextContent(/gran día/);
    });

    it("pinta las 8 actividades del catalogo como botones en una lista", async () => {
        const { container } = renderAt("/");
        const list = await screen.findByRole("list", { name: "Actividades" });
        expect(within(list).getAllByRole("button")).toHaveLength(8);
        expect(
            within(list).getByRole("button", { name: "Gimnasio y cubierto" }),
        ).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("muestra error con Reintentar si fallan las actividades", async () => {
        const spy = vi
            .spyOn(activitiesApi, "getActivities")
            .mockRejectedValueOnce(new Error("caida"));
        const { user } = renderAt("/");
        expect(
            await screen.findByText("No se pudieron cargar las actividades."),
        ).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(
            await screen.findByRole("button", { name: "Caminar" }),
        ).toBeInTheDocument();
        expect(spy).toHaveBeenCalledTimes(2);
    });

    it("sin ubicacion, pide la ubicacion y despues va a resultados", async () => {
        const { user } = renderAt("/");
        await user.click(await screen.findByRole("button", { name: "Correr" }));
        expect(
            screen.getByText(/Antes, dinos dónde estás/),
        ).toBeInTheDocument();
        await user.click(
            screen.getByRole("button", { name: "Usar mi ubicación" }),
        );
        expect(
            await screen.findByRole("heading", {
                level: 1,
                name: "Correr cerca de ti",
            }),
        ).toBeInTheDocument();
    });

    it("con ubicacion, una actividad lleva directo a resultados", async () => {
        const { user } = renderAt("/", { origin: SAMPLE_ORIGIN });
        await user.click(await screen.findByRole("button", { name: "Caminar" }));
        expect(
            await screen.findByRole("heading", {
                level: 1,
                name: "Caminar cerca de ti",
            }),
        ).toBeInTheDocument();
    });

    it("Sorpréndeme busca sin actividad", async () => {
        const { user } = renderAt("/", { origin: SAMPLE_ORIGIN });
        await user.click(screen.getByRole("button", { name: /Sorpréndeme/ }));
        expect(
            await screen.findByRole("heading", {
                level: 1,
                name: "Planes para ti hoy",
            }),
        ).toBeInTheDocument();
    });

    it("usar mi ubicacion avisa de que es de ejemplo", async () => {
        const { user } = renderAt("/");
        await user.click(
            screen.getByRole("button", { name: "Usar mi ubicación" }),
        );
        expect(
            await screen.findByText(
                "Es una ubicación de ejemplo: todavía no usamos tu GPS.",
            ),
        ).toBeInTheDocument();
    });

    it("busca una direccion o municipio y avisa si se usa el centro", async () => {
        const { user, container } = renderAt("/");
        await user.type(
            screen.getByLabelText("Escribe una dirección o un municipio"),
            "Getafe",
        );
        await user.click(screen.getByRole("button", { name: "Buscar" }));
        const option = await screen.findByRole("button", { name: "Getafe" });
        expect(screen.getByText("1 lugar encontrado.")).toBeInTheDocument();
        await user.click(option);
        expect(
            await screen.findByText("Usaremos el centro de Getafe."),
        ).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("dice que no encontro la direccion", async () => {
        const { user } = renderAt("/");
        await user.type(
            screen.getByLabelText("Escribe una dirección o un municipio"),
            "zzzzzz",
        );
        await user.click(screen.getByRole("button", { name: "Buscar" }));
        expect(
            await screen.findByText(
                "No encontramos esa dirección. Prueba con el nombre del municipio.",
            ),
        ).toBeInTheDocument();
    });

    it("muestra el estado del momento con temperatura y aire en texto", async () => {
        renderAt("/", { origin: SAMPLE_ORIGIN });
        const state = await screen.findByRole("list", {
            name: "Ahora en tu zona",
        });
        await waitFor(() => expect(state).toHaveTextContent("22 °C"));
        expect(state).toHaveTextContent(/Aire razonablemente buena/);
    });

    it("resume las preferencias y tiene Ajustar", () => {
        renderAt("/");
        expect(
            screen.getByText("45 min · hasta 3 km · interior o exterior"),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: /Ajustar/ }),
        ).toBeInTheDocument();
    });

    it("enlaza con el asistente de rutas", () => {
        renderAt("/");
        expect(
            screen.getByRole("link", { name: /Asistente de rutas/ }),
        ).toHaveAttribute("href", "/asistente");
    });
});
