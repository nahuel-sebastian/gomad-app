import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as activitiesApi from "../data/activities";
import * as recommendApi from "../data/recommend";
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
        expect(within(place).getByRole("radio", { name: "Cualquiera" })).toBeChecked();
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
        const weights = await screen.findAllByRole("group", { name: /^Importancia de/ });
        expect(weights).toHaveLength(5);
        for (const group of weights) {
            expect(within(group).getAllByRole("radio")).toHaveLength(5);
        }
        expect(within(screen.getByRole("group", { name: "Importancia de cercanía y rapidez" })).getByRole("radio", { name: "Poca" })).toBeChecked();
        await expectNoAxeViolations(container);
    });

    it("pide confirmación antes de restablecer los pesos y permite cancelar", async () => {
        const { user } = renderAt("/perfil");
        const air = await screen.findByRole("group", { name: "Importancia de aire limpio" });
        const much = within(air).getByRole("radio", { name: "Mucha" });
        await user.click(much);
        expect(much).toBeChecked();
        const clear = screen.getByRole("button", { name: "Borrar todas mis preferencias" });
        expect(clear.closest(".gomad-preferences-form")).toBeNull();
        expect(clear.closest(".panel")).toBeNull();
        await user.click(clear);
        let confirmation = screen.getByRole("dialog", { name: "¿Restablecer los pesos?" });
        expect(much).toBeChecked();
        await user.click(within(confirmation).getByRole("button", { name: "Cancelar" }));
        expect(screen.queryByRole("dialog", { name: "¿Restablecer los pesos?" })).not.toBeInTheDocument();
        expect(clear).toHaveFocus();
        expect(much).toBeChecked();
        await user.click(clear);
        confirmation = screen.getByRole("dialog", { name: "¿Restablecer los pesos?" });
        await user.click(within(confirmation).getByRole("button", { name: "Borrar" }));
        await waitFor(() =>
            expect(within(air).getByRole("radio", { name: "Poca" })).toBeChecked(),
        );
        expect(screen.getByRole("status")).toHaveTextContent("Pesos restablecidos a los valores por defecto.");
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
        await user.click(within(companions).getByRole("button", { name: "Con carrito" }));
        expect(within(companions).getByRole("button", { name: "Con personas mayores" })).toHaveAttribute("aria-pressed", "true");
        expect(within(companions).getByRole("button", { name: "Con carrito" })).toHaveAttribute("aria-pressed", "true");
        await user.click(within(companions).getByRole("button", { name: "Con personas mayores" }));
        expect(within(companions).getByRole("button", { name: "Con personas mayores" })).toHaveAttribute("aria-pressed", "false");
        expect(within(companions).getByRole("button", { name: "Con carrito" })).toHaveAttribute("aria-pressed", "true");
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

describe("Ajustar en el panel de resultados", () => {
    afterEach(() => vi.restoreAllMocks());

    it("sustituye los resultados por las preferencias y Listo vuelve a la lista", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        const adjust = screen.getByRole("button", { name: "Ajustar preferencias" });
        await user.click(adjust);
        expect(screen.getByRole("heading", { name: "Tus preferencias" })).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Importancia de cercanía y rapidez" })).toBeInTheDocument();
        expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Guardar preferencias" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Listo" }));
        expect(await screen.findByRole("list", { name: "Resultados" })).toBeInTheDocument();
    });

    it("deja cambiar tiempo, distancia, ventana, lugar y perfil sin salir de Resultados", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        await screen.findByRole("list", { name: "Resultados" });
        await user.click(screen.getByRole("button", { name: "Ajustar preferencias" }));
        expect(screen.getByRole("slider", { name: "Tiempo disponible" })).toBeInTheDocument();
        expect(screen.getByRole("slider", { name: "Distancia máxima a pie" })).toBeInTheDocument();
        expect(screen.getByRole("slider", { name: "Ventana horaria" })).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Lugar" })).toBeInTheDocument();
        expect(screen.getByRole("group", { name: "Perfil (opcional)" })).toBeInTheDocument();
        // en Resultados los cambios se aplican solos: sin «Guardar» ni «Borrar»
        expect(screen.queryByRole("button", { name: "Guardar preferencias" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: "Borrar todas mis preferencias" })).not.toBeInTheDocument();
    });

    it("cambiar la distancia y el lugar en Resultados recalcula con los nuevos valores", async () => {
        const spy = vi.spyOn(recommendApi, "recommend");
        const { user } = renderAt("/resultados", WITH_SEARCH);
        await screen.findByRole("list", { name: "Resultados" });
        await user.click(screen.getByRole("button", { name: "Ajustar preferencias" }));
        await user.click(screen.getByRole("button", { name: "Aumentar distancia máxima a pie" }));
        await user.click(within(screen.getByRole("group", { name: "Lugar" })).getByRole("radio", { name: "Exterior" }));
        await waitFor(() =>
            expect(spy).toHaveBeenLastCalledWith(
                expect.objectContaining({ max_distance_m: 3500, setting: "outdoor" }),
            ),
        );
        await user.click(screen.getByRole("button", { name: "Listo" }));
        expect(await screen.findByRole("list", { name: "Resultados" })).toBeInTheDocument();
    });

    it("subir la cercania al maximo recalcula y cambia el orden sin recargar", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        const list = await screen.findByRole("list", { name: "Resultados" });
        await waitFor(() => expect(within(list).getAllByRole("listitem")).toHaveLength(3));
        const before = within(list).getAllByRole("link")[0].textContent;
        await user.click(screen.getByRole("button", { name: "Ajustar preferencias" }));
        for (const name of ["Importancia de sombra y zona verde", "Importancia de aire limpio", "Importancia de adecuación a la actividad", "Importancia de meteorología"]) {
            await user.click(within(screen.getByRole("group", { name })).getByRole("radio", { name: "Nada" }));
        }
        await user.click(within(screen.getByRole("group", { name: "Importancia de cercanía y rapidez" })).getByRole("radio", { name: "Mucha" }));
        await user.click(screen.getByRole("button", { name: "Listo" }));
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
        expect(await screen.findAllByRole("group", { name: /^Importancia de/ })).toHaveLength(5);
    });

    it("mientras carga dice «Cargando pesos…» y no hay deslizadores de peso", async () => {
        vi.spyOn(activitiesApi, "getActivities").mockReturnValue(new Promise(() => {}));
        renderAt("/perfil");
        expect(screen.getByText("Cargando pesos…")).toBeInTheDocument();
        expect(screen.queryAllByRole("slider", { name: /^Importancia de/ })).toHaveLength(0);
    });
});
