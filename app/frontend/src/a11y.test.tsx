import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { recommend } from "./data/recommend";
import { buildRecommendRequest } from "./lib/request";
import { DEFAULT_PREFERENCES } from "./state/context";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "./test/render";

async function stateWithResults() {
    const data = await recommend(
        buildRecommendRequest(SAMPLE_ORIGIN.coordinate, "walk", DEFAULT_PREFERENCES),
    );
    return {
        origin: SAMPLE_ORIGIN,
        search: { activity: "walk", label: "Caminar" },
        results: data.results,
        id: encodeURIComponent(data.results[0].destination.id),
    };
}

describe("barrido de accesibilidad por pantalla", () => {
    it.each([
        ["/", "¿Qué te apetece hacer hoy?"],
        ["/resultados", "Caminar cerca de ti"],
        ["/resultados/:id", null],
        ["/ruta/:id", null],
        ["/municipios", "Municipios"],
        ["/municipios/28079", "Madrid"],
        ["/perfil", "Tus preferencias"],
        ["/asistente", "Asistente de rutas"],
        ["/fuentes", "Fuentes, licencias y aviso"],
    ])("%s tiene un solo h1, pasa axe y tiene el aviso medico", async (path, title) => {
        const state = await stateWithResults();
        const { container } = renderAt(path.replace(":id", state.id), state);
        if (title) {
            await screen.findByRole("heading", { level: 1, name: title });
        }
        // espera a que acabe la carga simulada
        await waitFor(() => expect(container).not.toHaveTextContent(/Cargando|Calculando|Buscando/));
        expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
        expect(screen.getByRole("contentinfo")).toHaveTextContent("No es consejo médico");
        await waitFor(() => expect(document.title).toMatch(/ · GoMad$/));
        await expectNoAxeViolations(container);
    });
});

describe("navegacion global", () => {
    it("la barra tiene los tres destinos con texto visible y va despues del logo", () => {
        renderAt("/");
        const nav = screen.getByRole("navigation", { name: "Principal" });
        const links = within(nav).getAllByRole("link");
        expect(links.map((l) => l.textContent)).toEqual(["Mi entorno", "Municipios", "Perfil"]);
        expect(screen.queryByRole("button", { name: /menú/i })).not.toBeInTheDocument();
    });

    it("Inicio queda marcado tambien en Resultados, Ruta y Asistente", () => {
        renderAt("/asistente");
        const nav = screen.getByRole("navigation", { name: "Principal" });
        expect(within(nav).getByRole("link", { name: "Mi entorno" })).toHaveAttribute("aria-current", "true");
    });

    it("en Inicio, Mi entorno lleva aria-current=page", () => {
        renderAt("/");
        const nav = screen.getByRole("navigation", { name: "Principal" });
        expect(within(nav).getByRole("link", { name: "Mi entorno" })).toHaveAttribute("aria-current", "page");
    });

    it("main recibe el foco del skip link", () => {
        renderAt("/");
        expect(screen.getByRole("main")).toHaveAttribute("tabindex", "-1");
    });

    it("Volver desde Resultados lleva a Inicio", async () => {
        const state = await stateWithResults();
        const { user } = renderAt("/resultados", state);
        const list = await screen.findByRole("list", { name: "Resultados" });
        const handle = screen.getByRole("button", { name: "Mostrar resultados" });
        expect(handle).toHaveAttribute("aria-expanded", "false");
        await user.click(screen.getByRole("button", { name: "Volver" }));
        await screen.findByRole("heading", { level: 1, name: "¿Qué te apetece hacer hoy?" });
        expect(list).not.toBeInTheDocument();
    });

    it("tabular hasta un resultado despliega la hoja", async () => {
        const state = await stateWithResults();
        renderAt("/resultados", state);
        const list = await screen.findByRole("list", { name: "Resultados" });
        within(list).getAllByRole("link")[0].focus();
        await waitFor(() =>
            expect(screen.getByRole("button", { name: "Ocultar resultados" })).toHaveAttribute(
                "aria-expanded",
                "true",
            ),
        );
    });
});
