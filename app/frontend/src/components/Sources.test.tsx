import { screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { selectScenario } from "../data/scenarios";
import * as sourcesApi from "../data/sources";
import { expectNoAxeViolations, renderAt } from "../test/render";

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
        expect(headers).toEqual(["Fuente", "Publicador", "Licencia", "Actualizado"]);
        expect(table).toHaveTextContent("CC BY 4.0");
        expect(table).toHaveTextContent("ODbL");
        expect(table).toHaveTextContent("Aviso legal de AEMET");
        expect(table).toHaveTextContent("hace 12 min");
        expect(table).toHaveTextContent("Última recarga fallida: se muestra el dato anterior.");
        expect(table).toHaveTextContent("Sin descargar todavía");
        await expectNoAxeViolations(container);
    });

    it("tiene el aviso medico, la privacidad y la licencia de nuestros datos", () => {
        renderAt("/fuentes");
        expect(screen.getByRole("heading", { level: 2, name: "No es consejo médico" })).toBeInTheDocument();
        expect(screen.getByText(/BOE-A-2020-10426/)).toBeInTheDocument();
        const privacy = screen.getByRole("region", { name: "Privacidad" });
        expect(privacy).toHaveTextContent("Sin registro");
        expect(privacy).toHaveTextContent(/ubicación.*no se guarda/);
        expect(privacy).toHaveTextContent(/no se envía tu ubicación/);
        expect(screen.getByRole("region", { name: "Nuestros datos" })).toHaveTextContent("CC BY 4.0");
    });

    it("error de carga con Reintentar", async () => {
        vi.spyOn(sourcesApi, "getSources").mockRejectedValueOnce(new Error("red"));
        const { user } = renderAt("/fuentes");
        expect(await screen.findByText("No se pudieron cargar las fuentes.")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(await screen.findByRole("table", { name: "Fuentes de datos" })).toBeInTheDocument();
    });

    it("permite elegir un escenario de la demo y verlo (Carmen)", async () => {
        const { user } = renderAt("/fuentes");
        const group = screen.getByRole("group", { name: "Datos de ejemplo" });
        expect(within(group).getAllByRole("radio")).toHaveLength(6);
        await user.click(within(group).getByRole("radio", { name: /Carmen/ }));
        await user.click(screen.getByRole("button", { name: "Ver este ejemplo" }));
        expect(await screen.findByRole("heading", { level: 1, name: "Caminar cerca de ti" })).toBeInTheDocument();
        expect(await screen.findByText("Alternativa cubierta")).toBeInTheDocument();
    });
});
