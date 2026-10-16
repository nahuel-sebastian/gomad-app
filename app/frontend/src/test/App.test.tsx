import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { expectNoAxeViolations, renderAt } from "./render";

describe("diseno comun", () => {
    it("pinta Inicio con un h1, skip link y main#contenido sin violaciones de axe", async () => {
        const { container } = renderAt("/");
        expect(
            screen.getByRole("heading", { level: 1 }),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("link", { name: "Saltar al contenido" }),
        ).toHaveAttribute("href", "#contenido");
        expect(screen.getByRole("main")).toHaveAttribute("id", "contenido");
        await screen.findAllByRole("button", { name: /Caminar/ });
        await expectNoAxeViolations(container);
    });

    it("tiene pie con aviso medico y enlace a Fuentes en cualquier pantalla", () => {
        renderAt("/municipios");
        const footer = screen.getByRole("contentinfo");
        expect(footer).toHaveTextContent("No es consejo médico");
        expect(
            within(footer).getByRole("link", { name: /Fuentes y aviso/ }),
        ).toHaveAttribute("href", "/fuentes");
    });

    it("marca en la navegacion principal la seccion actual", () => {
        renderAt("/municipios/28065");
        const nav = screen.getByRole("navigation", { name: "Principal" });
        // subpantalla de la seccion: aria-current="true", no "page"
        expect(
            within(nav).getByRole("link", { name: "Municipios" }),
        ).toHaveAttribute("aria-current", "true");
        expect(
            within(nav).getByRole("link", { name: "Mi entorno" }),
        ).not.toHaveAttribute("aria-current");
    });

    it("aria-current=page solo en la ruta exacta del enlace", () => {
        renderAt("/municipios");
        const nav = screen.getByRole("navigation", { name: "Principal" });
        expect(
            within(nav).getByRole("link", { name: "Municipios" }),
        ).toHaveAttribute("aria-current", "page");
    });

    it("pone el titulo del documento a partir del h1", async () => {
        renderAt("/perfil");
        await waitFor(() =>
            expect(document.title).toBe("Tus preferencias · GoMad"),
        );
    });

    it("lleva el foco al h1 al navegar a otra pantalla", async () => {
        const { user } = renderAt("/");
        const nav = screen.getByRole("navigation", { name: "Principal" });
        await user.click(within(nav).getByRole("link", { name: "Preferencias" }));
        const h1 = await screen.findByRole("heading", {
            level: 1,
            name: "Tus preferencias",
        });
        await waitFor(() => expect(h1).toHaveFocus());
    });

    it("muestra una pagina 404 con su h1", async () => {
        const { container } = renderAt("/no-existe");
        expect(
            screen.getByRole("heading", {
                level: 1,
                name: "Página no encontrada",
            }),
        ).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });
});
