import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import AppRoutes from "../AppRoutes";
import * as activitiesApi from "../data/activities";
import * as locationApi from "../data/location";
import { AppStateProvider } from "../state/AppState";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "./render";

afterEach(() => {
    vi.restoreAllMocks();
});

describe("Inicio", () => {
    it("no enfoca el título al cargar en StrictMode, pero sí al navegar", async () => {
        const user = userEvent.setup();
        render(
            <StrictMode>
                <MemoryRouter initialEntries={["/"]}>
                    <AppStateProvider init={{ origin: SAMPLE_ORIGIN }}><AppRoutes /></AppStateProvider>
                </MemoryRouter>
            </StrictMode>,
        );
        expect(screen.getByRole("heading", { level: 1, name: "¿Qué te apetece hacer hoy?" })).not.toHaveFocus();
        await user.click(screen.getByRole("link", { name: /Tus preferencias/ }));
        await waitFor(() => expect(screen.getByRole("heading", { level: 1, name: "Tus preferencias" })).toHaveFocus());
    });

    it("tiene un h1 neutro, no fijo a buen tiempo", () => {
        renderAt("/");
        const h1 = screen.getByRole("heading", { level: 1 });
        expect(h1).toHaveTextContent("¿Qué te apetece hacer hoy?");
        expect(h1).not.toHaveTextContent(/gran día/);
    });

    it("pinta las 8 actividades del catalogo como botones en una lista", async () => {
        const { container } = renderAt("/", { origin: SAMPLE_ORIGIN });
        const list = await screen.findByRole("list", { name: "Actividades" });
        expect(within(list).getAllByRole("button")).toHaveLength(8);
        expect(
            within(list).getByRole("button", { name: "Gimnasio y cubierto" }),
        ).toBeInTheDocument();
        expect(container.querySelector(".icon-random")).toBeInTheDocument();
        expect(container.querySelector(".icon-settings")).toBeInTheDocument();
        expect(container.querySelectorAll(".activity__icon")).toHaveLength(8);
        expect(within(list).getByRole("button", { name: "Caminar" }).querySelector(".activity__icon")).toHaveAttribute("data-icon", "directions_walk");
        const nav = screen.getByRole("navigation", { name: "Principal" });
        expect(nav.querySelector(".icon-navigation")).toBeInTheDocument();
        expect(nav.querySelector(".icon-location_on")).toBeInTheDocument();
        expect(nav.querySelector(".icon-menu")).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("muestra error con Reintentar si fallan las actividades", async () => {
        const spy = vi
            .spyOn(activitiesApi, "getActivities")
            .mockRejectedValueOnce(new Error("caida"));
        const { user } = renderAt("/", { origin: SAMPLE_ORIGIN });
        expect(
            await screen.findByText("No se pudieron cargar las actividades."),
        ).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(
            await screen.findByRole("button", { name: "Caminar" }),
        ).toBeInTheDocument();
        expect(spy).toHaveBeenCalledTimes(2);
    });

    it("sin ubicacion muestra el buscador y preferencias; al activarla aparecen las demás opciones", async () => {
        const { user } = renderAt("/");
        expect(screen.getByRole("heading", { name: "¿Desde dónde sales?" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Elige una actividad" })).not.toBeInTheDocument();
        expect(screen.queryByRole("button", { name: /Sorpréndeme/ })).not.toBeInTheDocument();
        expect(screen.queryByRole("link", { name: /Asistente de rutas/ })).not.toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Tus preferencias/ })).toHaveAttribute("href", "/perfil");
        await user.click(
            screen.getByRole("button", { name: "Usar mi ubicación" }),
        );
        expect(await screen.findByRole("button", { name: "Correr" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: /Sorpréndeme/ })).toBeInTheDocument();
        expect(screen.getByRole("link", { name: /Asistente de rutas/ })).toBeInTheDocument();
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

    it("usar mi ubicacion pone la ubicacion en el campo y permite borrarla", async () => {
        const { user } = renderAt("/");
        const locationButton = screen.getByRole("button", { name: "Usar mi ubicación" });
        expect(locationButton).toHaveTextContent("Usar ubicación");
        expect(locationButton).toHaveClass("gomad-action-use-location");
        await user.click(locationButton);
        expect(await screen.findByDisplayValue("Tu ubicación de ejemplo (Getafe)")).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Borrar ubicación" }).querySelector(".icon-close")).toBeInTheDocument();
        expect(document.querySelector(".location__status")).toHaveClass("sr-only");
        await user.click(screen.getByRole("button", { name: "Borrar ubicación" }));
        expect(screen.getByLabelText("Escribe una dirección o un municipio")).toHaveValue("");
        expect(screen.getByRole("button", { name: "Buscar" })).toBeInTheDocument();
        expect(screen.queryByRole("heading", { name: "Elige una actividad" })).not.toBeInTheDocument();
    });

    it("si el GPS se deniega lo explica y deja escribir la dirección", async () => {
        vi.spyOn(locationApi, "currentLocation").mockRejectedValueOnce(
            new Error("No has dado permiso para usar tu ubicación. Escribe una dirección o un municipio."),
        );
        const { user } = renderAt("/");
        await user.click(screen.getByRole("button", { name: "Usar mi ubicación" }));
        expect(await screen.findByText(/No has dado permiso para usar tu ubicación/)).toBeInTheDocument();
        expect(screen.getByLabelText("Escribe una dirección o un municipio")).toBeEnabled();
        expect(screen.getByRole("button", { name: "Usar mi ubicación" })).toBeEnabled();
    });

    it("busca una direccion o municipio y avisa si se usa el centro", async () => {
        const { user, container } = renderAt("/");
        await user.type(
            screen.getByLabelText("Escribe una dirección o un municipio"),
            "Getafe",
        );
        const searchButton = screen.getByRole("button", { name: "Buscar" });
        expect(searchButton.querySelector(".icon-search")).toHaveAttribute("aria-hidden", "true");
        expect(searchButton.closest(".location__search")).toContainElement(
            screen.getByLabelText("Escribe una dirección o un municipio"),
        );
        await user.click(searchButton);
        const option = await screen.findByRole("button", { name: "Getafe" });
        const count = screen.getByText("1 lugar encontrado.");
        expect(count.compareDocumentPosition(screen.getByLabelText("Escribe una dirección o un municipio")) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();
        expect(count.parentElement).toHaveClass("location__form");
        expect(option.closest(".location__candidates")?.parentElement).toHaveClass("location__form");
        await user.click(option);
        expect(screen.getByLabelText("Escribe una dirección o un municipio")).toHaveValue("Getafe");
        expect(screen.queryByText("Usaremos el centro de Getafe.")).not.toBeInTheDocument();
        expect(screen.queryByRole("list", { name: "Lugares encontrados" })).not.toBeInTheDocument();
        expect(await screen.findByRole("heading", { name: "Elige una actividad" })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Borrar ubicación" }));
        expect(screen.getByLabelText("Escribe una dirección o un municipio")).toHaveValue("");
        expect(screen.queryByRole("heading", { name: "Elige una actividad" })).not.toBeInTheDocument();
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
        expect(screen.getByText("No encontramos esa dirección. Prueba con el nombre del municipio.").parentElement).toHaveClass("location__form");
    });

    it("muestra opciones mientras se escribe sin pulsar Buscar", async () => {
        const { user } = renderAt("/");
        await user.type(screen.getByLabelText("Escribe una dirección o un municipio"), "Getafe");
        const option = await screen.findByRole("button", { name: "Getafe" });
        expect(option.closest(".location__candidates")?.parentElement).toHaveClass("location__form");
    });

    it("muestra el estado del momento con temperatura y aire en texto", async () => {
        renderAt("/", { origin: SAMPLE_ORIGIN });
        const state = await screen.findByRole("list", {
            name: "Ahora en tu zona",
        });
        await waitFor(() => expect(state).toHaveTextContent("22 °C"));
        expect(state).toHaveTextContent(/Aire limpio · bien para salir/);
    });

    it("hace que toda la tarjeta de preferencias enlace al perfil y la compone como Sorpréndeme", () => {
        renderAt("/", { origin: SAMPLE_ORIGIN });
        expect(
            screen.getByText("45 min · hasta 3 km · interior o exterior"),
        ).toBeInTheDocument();
        const preferencesCard = screen.getByRole("link", { name: /Tus preferencias/ });
        expect(preferencesCard).toHaveClass("panel--action", "prefs");
        expect(preferencesCard).toHaveAttribute("href", "/perfil");
        expect(preferencesCard.querySelector("button")).not.toBeInTheDocument();
        expect(preferencesCard.querySelector(".surprise__tile .icon-settings")).toHaveAttribute("aria-hidden", "true");
        expect(preferencesCard.querySelector(".panel__title")).toHaveTextContent("Tus preferencias");
        expect(preferencesCard.querySelector(".surprise__text > .muted")).toHaveTextContent(
            "45 min · hasta 3 km · interior o exterior",
        );
        expect(preferencesCard.querySelector(".prefs__action")).not.toBeInTheDocument();
    });

    it("enlaza con el asistente de rutas", () => {
        renderAt("/", { origin: SAMPLE_ORIGIN });
        const assistantCard = screen.getByRole("link", { name: /Asistente de rutas/ });
        expect(assistantCard).toHaveAttribute("href", "/asistente");
        expect(assistantCard).toHaveClass("surprise", "assistant-link");
        expect(assistantCard.querySelector(".surprise__tile .icon-navigation")).toHaveAttribute("aria-hidden", "true");
        expect(assistantCard.parentElement).toHaveClass("home__secondary");
    });
});

function liveRegion(text: RegExp) {
    return screen.getAllByRole("status").find((el) => text.test(el.textContent ?? ""));
}

describe("Inicio: region viva", () => {
    afterEach(() => vi.restoreAllMocks());

    it("existe desde el primer render y anuncia la carga y el momento", async () => {
        renderAt("/", { origin: SAMPLE_ORIGIN });
        const live = liveRegion(/Cargando actividades…/);
        expect(live).toBeDefined();
        expect(live).toHaveAttribute("aria-live", "polite");
        await waitFor(() => expect(live).toHaveTextContent("Actividades cargadas"));
        await waitFor(() => expect(live).toHaveTextContent(/Ahora en Getafe/));
    });

    it("si falla el momento, la pastilla dice «Tiempo y aire: sin datos»", async () => {
        const recommendApi = await import("../data/recommend");
        vi.spyOn(recommendApi, "recommend").mockRejectedValue(new Error("red"));
        renderAt("/", { origin: SAMPLE_ORIGIN });
        const chips = screen.getByRole("list", { name: "Ahora en tu zona" });
        expect(await within(chips).findByText("Tiempo y aire: sin datos")).toBeInTheDocument();
    });
});
