import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as municipalityApi from "../data/municipality";
import { expectNoAxeViolations, renderAt } from "../test/render";

afterEach(() => {
    vi.restoreAllMocks();
});

describe("Lista de municipios", () => {
    it("lista los 179 y filtra por nombre sin tildes", async () => {
        const { user, container } = renderAt("/municipios");
        expect(screen.getByRole("heading", { level: 1, name: "Municipios" })).toBeInTheDocument();
        const list = await screen.findByRole("list", { name: "Municipios de la Comunidad de Madrid" });
        expect(within(list).getAllByRole("link")).toHaveLength(179);
        await user.type(screen.getByLabelText("Busca un municipio"), "alcala");
        await waitFor(() =>
            expect(within(list).getAllByRole("link").map((a) => a.textContent)).toContain(
                "Alcalá de Henares",
            ),
        );
        expect(screen.getByRole("status")).toHaveTextContent(/\d+ municipios?/);
        await expectNoAxeViolations(container);
    });

    it("dice si no hay coincidencias", async () => {
        const { user } = renderAt("/municipios");
        await screen.findByRole("list", { name: "Municipios de la Comunidad de Madrid" });
        await user.type(screen.getByLabelText("Busca un municipio"), "zzzz");
        expect(await screen.findByText("Ningún municipio coincide con «zzzz».")).toBeInTheDocument();
    });
});

describe("Vista de municipio", () => {
    it("muestra indicadores por categoria, sin datos en texto y encaje, sin rankings", async () => {
        const { container } = renderAt("/municipios/28065");
        expect(
            await screen.findByRole("heading", { level: 1, name: "Getafe" }),
        ).toBeInTheDocument();
        await screen.findByRole("heading", { level: 2, name: "Deporte" });
        for (const name of ["Naturaleza", "Movilidad", "Salud", "Educación", "Conectividad", "Servicios sociales"]) {
            expect(screen.getByRole("heading", { level: 2, name })).toBeInTheDocument();
        }
        expect(screen.getAllByText("Sin datos").length).toBeGreaterThan(0);
        expect(screen.getByText(/no cubre este municipio/)).toBeInTheDocument();
        expect(screen.getByRole("heading", { level: 2, name: "¿Cómo encaja contigo?" })).toBeInTheDocument();
        expect(screen.getByText(/Cifras de ejemplo/)).toBeInTheDocument();
        expect(container).not.toHaveTextContent(/ranking|puesto|mejor que|peor que/i);
        await expectNoAxeViolations(container);
    });

    it("muestra la poblacion o «sin datos»", async () => {
        renderAt("/municipios/28001");
        expect(await screen.findByText(/Población: sin datos/)).toBeInTheDocument();
    });

    it("«Buscar actividad en» usa el centro del municipio como ubicacion", async () => {
        const { user } = renderAt("/municipios/28065");
        await user.click(
            await screen.findByRole("button", { name: "Buscar actividad en Getafe" }),
        );
        expect(await screen.findByText("Usaremos el centro de Getafe.")).toBeInTheDocument();
    });

    it("avisa si no puede situar el municipio", async () => {
        vi.spyOn(municipalityApi, "listMunicipalities").mockRejectedValueOnce(new Error("red"));
        const { user } = renderAt("/municipios/28065");
        await user.click(await screen.findByRole("button", { name: "Buscar actividad en Getafe" }));
        expect(await screen.findByText("No se pudo situar el municipio. Inténtalo de nuevo.")).toBeInTheDocument();
    });

    it("con un codigo inexistente da un 404 legible", async () => {
        renderAt("/municipios/28999");
        expect(
            await screen.findByRole("heading", { level: 1, name: "Municipio no encontrado" }),
        ).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Ver todos los municipios" })).toHaveAttribute(
            "href",
            "/municipios",
        );
    });

    it("error de carga con Reintentar", async () => {
        vi.spyOn(municipalityApi, "getMunicipality").mockRejectedValueOnce(new Error("red"));
        const { user } = renderAt("/municipios/28065");
        expect(await screen.findByText("No se pudo cargar el municipio.")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(await screen.findByRole("heading", { level: 1, name: "Getafe" })).toBeInTheDocument();
    });
});
