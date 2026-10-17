import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as activitiesApi from "../data/activities";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "./render";

const WITH_SEARCH = {
    origin: SAMPLE_ORIGIN,
    search: { activity: "walk", label: "Caminar" },
};

describe("Perfil", () => {
    it("tiene perfil, «Salgo con…», lugar, tiempo, distancia, ventana y 5 pesos", async () => {
        const { container } = renderAt("/perfil");
        expect(screen.getByRole("heading", { level: 1, name: "Tus preferencias" })).toBeInTheDocument();
        const place = screen.getByRole("group", { name: "Lugar" });
        expect(within(place).getByRole("radio", { name: "Indiferente" })).toBeChecked();
        const companions = screen.getByRole("group", { name: "Perfil (opcional)" });
        expect(within(companions).getAllByRole("checkbox")).toHaveLength(2);
        expect(within(companions).getAllByRole("button")).toHaveLength(3);
        expect(companions.querySelector(".icon-pets")).toBeInTheDocument();
        expect(companions.querySelector(".icon-family")).toBeInTheDocument();
        expect(companions.querySelector(".icon-elderly")).toBeInTheDocument();
        expect(companions.querySelector(".icon-air")).toBeInTheDocument();
        expect(companions.querySelectorAll(".icon[aria-hidden='true']")).toHaveLength(5);
        expect(screen.getByRole("slider", { name: "Tiempo disponible" })).toHaveAttribute(
            "aria-valuetext",
            "45 minutos",
        );
        const durationSlider = screen.getByRole("slider", { name: "Tiempo disponible" });
        const durationControl = durationSlider.closest<HTMLElement>(".pref-slider")!;
        expect(within(durationControl).getByText("45 min")).toBeInTheDocument();
        expect(within(durationControl).getByText("10 min")).toBeInTheDocument();
        expect(within(durationControl).getByText("180 min")).toBeInTheDocument();
        expect(screen.getByRole("slider", { name: "Distancia máxima a pie" })).toHaveAttribute(
            "aria-valuetext",
            "3 km",
        );
        expect(screen.getByRole("slider", { name: "Ventana horaria" })).toHaveAttribute(
            "aria-valuetext",
            "Próximas 3 horas",
        );
        const windowSlider = screen.getByRole("slider", { name: "Ventana horaria" });
        const windowControl = windowSlider.closest<HTMLElement>(".pref-slider")!;
        expect(within(windowControl).getByText("3h")).toBeInTheDocument();
        expect(within(windowControl).getByText("1h")).toBeInTheDocument();
        expect(within(windowControl).getByText("12h")).toBeInTheDocument();
        const weights = await screen.findAllByRole("slider", { name: /^Importancia de/ });
        expect(weights).toHaveLength(5);
        expect(screen.getByRole("slider", { name: "Importancia de adecuación a la actividad" })).toBeInTheDocument();
        expect(screen.getByRole("slider", { name: "Importancia de cercanía y rapidez" })).toHaveAttribute(
            "aria-valuetext",
            "30 %, importancia media",
        );
        await expectNoAxeViolations(container);
    });

    it("mover un peso con el teclado lo cambia y Restablecer vuelve a los de por defecto", async () => {
        const { user } = renderAt("/perfil");
        const air = await screen.findByRole("slider", { name: "Importancia de aire limpio" });
        air.focus();
        await user.keyboard("{End}");
        await waitFor(() => expect(air).toHaveAttribute("aria-valuetext", "100 %, importancia máxima"));
        await user.click(screen.getByRole("button", { name: "Restablecer valores por defecto" }));
        await waitFor(() =>
            expect(screen.getByRole("slider", { name: "Importancia de aire limpio" })).toHaveAttribute(
                "aria-valuetext",
                "15 %, importancia baja",
            ),
        );
    });

    it("ajusta los tres filtros por sus pasos con botones accesibles", async () => {
        const { user } = renderAt("/perfil");
        expect(screen.getByRole("button", { name: "Aumentar tiempo disponible" }).querySelector(".icon-add_24dp_1F1F1F_FILL1_wght400_GRAD0_opsz24")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Disminuir tiempo disponible" }).querySelector(".icon-remove_24dp_1F1F1F_FILL1_wght400_GRAD0_opsz24")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Aumentar tiempo disponible" }));
        expect(screen.getByRole("slider", { name: "Tiempo disponible" })).toHaveAttribute("aria-valuetext", "50 minutos");
        expect(screen.getByRole("slider", { name: "Tiempo disponible" }).closest(".pref-slider")).toHaveTextContent("50 min");
        await user.click(screen.getByRole("button", { name: "Disminuir distancia máxima a pie" }));
        expect(screen.getByRole("slider", { name: "Distancia máxima a pie" })).toHaveAttribute("aria-valuetext", "2,5 km");
        await user.click(screen.getByRole("button", { name: "Aumentar ventana horaria" }));
        expect(screen.getByRole("slider", { name: "Ventana horaria" })).toHaveAttribute("aria-valuetext", "Próximas 4 horas");
        expect(screen.getByRole("slider", { name: "Ventana horaria" }).closest(".pref-slider")).toHaveTextContent("4h");
    });

    it("permite elegir varios acompañantes y activar o quitar un perfil", async () => {
        const { user } = renderAt("/perfil");
        const companions = screen.getByRole("group", { name: "Perfil (opcional)" });
        await user.click(within(companions).getByRole("checkbox", { name: "Con perro" }));
        expect(within(companions).getByRole("checkbox", { name: "Con perro" })).toBeChecked();
        await user.click(within(companions).getByRole("checkbox", { name: "Con niños" }));
        expect(within(companions).getByRole("checkbox", { name: "Con niños" })).toBeChecked();
        await user.click(within(companions).getByRole("button", { name: "Con personas mayores" }));
        expect(within(companions).getByRole("button", { name: "Con personas mayores" })).toHaveAttribute("aria-pressed", "true");
        await user.click(within(companions).getByRole("button", { name: "Con personas mayores" }));
        expect(within(companions).getByRole("button", { name: "Con personas mayores" })).toHaveAttribute("aria-pressed", "false");
        expect(within(companions).getByRole("checkbox", { name: "Con perro" })).toBeChecked();
    });

    it("confirma el guardado en sesión y retira la confirmación al cambiar un filtro", async () => {
        const { user } = renderAt("/perfil");
        await user.click(screen.getByRole("button", { name: "Guardar preferencias" }));
        expect(screen.getByRole("status", { name: "" })).toHaveTextContent("Preferencias guardadas durante esta sesión.");
        await user.click(screen.getByRole("checkbox", { name: "Con perro" }));
        expect(screen.queryByText("Preferencias guardadas durante esta sesión.")).not.toBeInTheDocument();
    });

    it("el resumen de Inicio refleja los cambios", async () => {
        const { user } = renderAt("/perfil", { origin: SAMPLE_ORIGIN });
        await user.click(screen.getByRole("radio", { name: "Interior" }));
        const nav = screen.getByRole("navigation", { name: "Principal" });
        await user.click(within(nav).getByRole("link", { name: "Mi entorno" }));
        expect(await screen.findByText("45 min · hasta 3 km · interior")).toBeInTheDocument();
    });
});

describe("Ajustar como dialogo", () => {
    it("se abre desde Resultados, Esc cierra y el foco vuelve a Ajustar", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        const adjust = screen.getByRole("button", { name: "Ajustar preferencias" });
        await user.click(adjust);
        const dialog = await screen.findByRole("dialog", { name: "Tus preferencias" });
        expect(dialog).toBeInTheDocument();
        await user.keyboard("{Escape}");
        await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
        expect(adjust).toHaveFocus();
    });

    it("subir la cercania al maximo recalcula y cambia el orden sin recargar", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        const list = await screen.findByRole("list", { name: "Resultados" });
        await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(3));
        const before = within(list).getAllByRole("link")[0].textContent;
        await user.click(screen.getByRole("button", { name: "Ajustar preferencias" }));
        const dialog = await screen.findByRole("dialog", { name: "Tus preferencias" });
        for (const name of ["Importancia de sombra y zona verde", "Importancia de aire limpio", "Importancia de adecuación a la actividad", "Importancia de meteorología"]) {
            const slider = within(dialog).getByRole("slider", { name });
            slider.focus();
            await user.keyboard("{Home}");
        }
        const near = within(dialog).getByRole("slider", { name: "Importancia de cercanía y rapidez" });
        near.focus();
        await user.keyboard("{End}");
        await user.click(within(dialog).getByRole("button", { name: "Listo" }));
        await waitFor(() =>
            expect(screen.getByRole("status")).toHaveTextContent("3 resultados actualizados"),
        );
        const after = within(screen.getByRole("list", { name: "Resultados" })).getAllByRole("link")[0].textContent;
        expect(after).not.toBe(before);
    });

    it("«Tus preferencias» en Inicio lleva al perfil", async () => {
        const { user } = renderAt("/", { origin: SAMPLE_ORIGIN });
        await user.click(screen.getByRole("link", { name: /^Tus preferencias/ }));
        expect(await screen.findByRole("heading", { level: 1, name: "Tus preferencias" })).toBeInTheDocument();
    });

    it("con todos los pesos a 0 se ve el aviso de la API", async () => {
        renderAt("/resultados", {
            ...WITH_SEARCH,
            preferences: { weights: { proximity: 0, suitability: 0, green: 0, air: 0, weather: 0 } },
        });
        expect(await screen.findByText(/se usan los pesos por defecto/)).toBeInTheDocument();
    });
});

describe("Perfil: pesos por defecto", () => {
    afterEach(() => vi.restoreAllMocks());

    it("sin /activities no pinta los pesos ni inventa unos: error con Reintentar y, al reintentar, aparecen", async () => {
        const real = activitiesApi.getActivities;
        const spy = vi.spyOn(activitiesApi, "getActivities").mockRejectedValueOnce(new Error("red"));
        const { user } = renderAt("/perfil");
        const retry = await screen.findByRole("button", { name: "Reintentar" });
        expect(screen.queryAllByRole("slider", { name: /^Importancia de/ })).toHaveLength(0);
        spy.mockImplementation(real);
        await user.click(retry);
        expect(await screen.findAllByRole("slider", { name: /^Importancia de/ })).toHaveLength(5);
    });

    it("mientras carga dice «Cargando pesos…» y no hay deslizadores de peso", async () => {
        vi.spyOn(activitiesApi, "getActivities").mockReturnValue(new Promise(() => {}));
        renderAt("/perfil");
        expect(screen.getByText("Cargando pesos…")).toBeInTheDocument();
        expect(screen.queryAllByRole("slider", { name: /^Importancia de/ })).toHaveLength(0);
    });
});
