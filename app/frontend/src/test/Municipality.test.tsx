import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as municipalityApi from "../data/municipality";
import { MUNICIPALITIES } from "../data/mock/municipalities";
import { normalize } from "../lib/text";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "./render";

afterEach(() => {
    vi.restoreAllMocks();
});

describe("Lista de municipios", () => {
    const allLinks = () =>
        within(screen.getByRole("region", { name: "Todos los municipios" })).getAllByRole("link");

    it("muestra los 179 agrupados por letra, sin paginar", async () => {
        const { container } = renderAt("/municipios");
        expect(screen.getByRole("heading", { level: 1, name: "Municipios" })).toBeInTheDocument();
        await screen.findByRole("heading", { level: 2, name: "A" });
        expect(allLinks()).toHaveLength(MUNICIPALITIES.length);
        expect(screen.getByRole("heading", { level: 2, name: "Z" })).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Mostrar más municipios" })).not.toBeInTheDocument();
        expect(screen.getByRole("status")).toHaveTextContent(`${MUNICIPALITIES.length} municipios`);
        await expectNoAxeViolations(container);
    });

    it("filtra por nombre sin tildes", async () => {
        const { user } = renderAt("/municipios");
        await screen.findByRole("heading", { level: 2, name: "A" });
        await user.type(screen.getByLabelText("Busca un municipio"), "alcala de");
        await waitFor(() => expect(allLinks().map((a) => a.textContent)).toContain("Alcalá de Henares"));
        expect(allLinks().every((a) => normalize(a.textContent!).includes("alcala de"))).toBe(true);
    });

    it("dice si no hay coincidencias", async () => {
        const { user } = renderAt("/municipios");
        await screen.findByRole("heading", { level: 2, name: "A" });
        await user.type(screen.getByLabelText("Busca un municipio"), "zzzz");
        expect(await screen.findByText("Ningún municipio coincide con «zzzz».")).toBeInTheDocument();
    });

    it("con un solo resultado, Enter abre el municipio", async () => {
        const { user } = renderAt("/municipios");
        await screen.findByRole("heading", { level: 2, name: "A" });
        await user.type(screen.getByLabelText("Busca un municipio"), "getafe{Enter}");
        expect(await screen.findByRole("heading", { level: 1, name: "Getafe" })).toBeInTheDocument();
    });

    it("con ubicación, «Cerca de ti» muestra tu municipio y los 3 más cercanos con su distancia", async () => {
        renderAt("/municipios", { origin: SAMPLE_ORIGIN });
        const near = await screen.findByRole("region", { name: "Cerca de ti" });
        const links = within(near).getAllByRole("link");
        expect(links).toHaveLength(4);
        // el municipio de la ubicacion va primero aunque el centro de otro quede mas cerca
        expect(links[0]).toHaveTextContent("GetafeEstás aquí");
        for (const link of links.slice(1)) {
            expect(link).toHaveTextContent(/\d+(,\d)? km|\d+ m/);
        }
    });

    it("sin ubicación no aparece «Cerca de ti»", async () => {
        renderAt("/municipios");
        await screen.findByRole("heading", { level: 2, name: "A" });
        expect(screen.queryByRole("region", { name: "Cerca de ti" })).not.toBeInTheDocument();
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
        expect(screen.queryByText(/Cifras de ejemplo/)).not.toBeInTheDocument();
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
        expect(await screen.findByDisplayValue("Getafe")).toBeInTheDocument();
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

describe("Municipio: region viva", () => {
    it("existe desde el primer render y cambia al cargar", async () => {
        renderAt("/municipios/28065");
        const live = screen.getAllByRole("status").find((el) => /Cargando municipio…/.test(el.textContent ?? ""));
        expect(live).toBeDefined();
        expect(live).toHaveAttribute("aria-live", "polite");
        await waitFor(() => expect(live).toHaveTextContent(/Getafe/));
    });
});
