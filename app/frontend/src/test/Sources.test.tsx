import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { selectScenario } from "../data/scenarios";
import * as sourcesApi from "../data/sources";
import { expectNoAxeViolations, renderAt } from "./render";

afterEach(() => {
    vi.restoreAllMocks();
    selectScenario("neutral");
});

describe("Fuentes y aviso", () => {
    it("lista fuentes en una tabla con licencias y fechas", async () => {
        const { container } = renderAt("/fuentes");
        expect(
            screen.getByRole("heading", { level: 1, name: "Fuentes, licencias y aviso" }),
        ).toBeInTheDocument();
        const table = await screen.findByRole("table", { name: "Fuentes de datos" });
        const headers = within(table).getAllByRole("columnheader").map((h) => h.textContent);
        expect(headers).toEqual(["Fuente", "Publicador", "Licencia", "Última actualización"]);
        expect(table).toHaveTextContent("CC BY 4.0");
        expect(table).toHaveTextContent("ODbL");
        expect(table).toHaveTextContent("Weather data by Open-Meteo.com");
        expect(table).toHaveTextContent("hace 12 min");
        expect(table).toHaveTextContent("Última recarga fallida: se muestra el dato anterior.");
        expect(table).toHaveTextContent("Sin descargar todavía");
        const sourceLinks = within(table).getAllByRole("link");
        expect(sourceLinks).toHaveLength(9);
        for (const link of sourceLinks) {
            expect(link).toHaveAttribute("target", "_blank");
            expect(link).toHaveAttribute("rel", "noreferrer noopener");
            expect(link).toHaveClass("gomad-sources__link");
            expect(link).toHaveAccessibleName(/se abre en una pestaña nueva/);
        }
        expect(table.querySelector('[data-label="Última actualización"]')).toHaveTextContent("hace 12 min");
        expect(table.querySelector('[data-label="Última actualización"]')).not.toHaveTextContent("Actualizado");
        await expectNoAxeViolations(container);
    });

    it("las referencias fijas y el criterio propio no salen como «sin descargar»", async () => {
        renderAt("/fuentes");
        const table = await screen.findByRole("table", { name: "Fuentes de datos" });
        const row = (name: RegExp) => within(table).getByRole("link", { name }).closest("tr")!;
        expect(row(/Índice Nacional de Calidad del Aire/)).toHaveTextContent("Referencia oficial: no se descarga");
        expect(row(/Pesos por defecto/)).toHaveTextContent("Criterio propio: no se descarga");
        expect(row(/Pesos por defecto/)).not.toHaveTextContent("Sin descargar todavía");
        expect(row(/MDT05/)).toHaveTextContent("Sin descargar todavía");
    });

    it("tiene el aviso medico, la privacidad y la licencia de nuestros datos", () => {
        renderAt("/fuentes");
        expect(screen.getByRole("heading", { level: 2, name: "No es consejo médico" })).toBeInTheDocument();
        expect(screen.getByText(/BOE-A-2020-10426/)).toBeInTheDocument();
        const privacy = screen.getByRole("region", { name: "Privacidad" });
        expect(privacy).toHaveTextContent("Sin registro");
        expect(privacy).toHaveTextContent(/ubicación.*no se guarda/);
        // al interpretar solo va el texto; la ubicacion si va al calcular la ruta
        expect(privacy).toHaveTextContent(/Para interpretar tu texto solo se envía el texto/);
        expect(privacy).toHaveTextContent(/tu ubicación solo se usa para calcular la ruta/);
        expect(privacy).not.toHaveTextContent(/Al asistente de rutas solo le llega el texto/);
        expect(screen.getByRole("region", { name: "Nuestros datos" })).toHaveTextContent("CC BY 4.0");
    });

    it("dice que una dirección no encontrada se consulta en Nomecalles solo con el texto", () => {
        renderAt("/fuentes");
        const privacy = screen.getByRole("region", { name: "Privacidad" });
        expect(privacy).toHaveTextContent(/buscador público de Nomecalles \(Comunidad de Madrid\)/);
        expect(privacy).toHaveTextContent(/solo se envía el texto que escribes/);
        expect(privacy).toHaveTextContent(/nunca tu ubicación/);
        expect(privacy).toHaveTextContent(/como mucho 1 hora en memoria/);
        expect(privacy).toHaveTextContent(/no se escribe en disco ni en los registros/);
    });

    it("el calor dice lo mismo que la API: sin umbral oficial cargado, no se evalúa", () => {
        renderAt("/fuentes");
        const medical = screen.getByRole("heading", { level: 2, name: "No es consejo médico" }).closest("section")!;
        expect(medical).toHaveTextContent(/Todavía no hay un umbral oficial de calor cargado: no se evalúa el calor/);
        expect(medical).not.toHaveTextContent(/criterio propio/);
    });

    it("error de carga con Reintentar", async () => {
        vi.spyOn(sourcesApi, "getSources").mockRejectedValueOnce(new Error("red"));
        const { user } = renderAt("/fuentes");
        expect(await screen.findByText("No se pudieron cargar las fuentes.")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(await screen.findByRole("table", { name: "Fuentes de datos" })).toBeInTheDocument();
    });

    it("ya no ofrece escenarios de ejemplo: la recomendación es real", () => {
        renderAt("/fuentes");
        expect(screen.queryByRole("group", { name: "Datos de ejemplo" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Ver este ejemplo" })).not.toBeInTheDocument();
    });

    it("ya no dice que la tabla de fuentes sea de ejemplo: llega del servidor", async () => {
        renderAt("/fuentes");
        const table = await screen.findByRole("table", { name: "Fuentes de datos" });
        expect(table.closest("section")).not.toHaveTextContent(/Lista de ejemplo/);
    });
});

describe("Fuentes: region viva", () => {
    it("existe desde el primer render y cambia al cargar", async () => {
        renderAt("/fuentes");
        const live = screen.getAllByRole("status").find((el) => /Cargando fuentes…/.test(el.textContent ?? ""));
        expect(live).toBeDefined();
        expect(live).toHaveAttribute("aria-live", "polite");
        await vi.waitFor(() => expect(live).toHaveTextContent(/Fuentes cargadas/));
    });
});
