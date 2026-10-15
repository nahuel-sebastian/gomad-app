import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as recommendApi from "../data/recommend";
import { ApiError } from "../data/errors";
import { selectScenario } from "../data/scenarios";
import { expectNoAxeViolations, renderAt, SAMPLE_ORIGIN } from "../test/render";

const WITH_SEARCH = {
    origin: SAMPLE_ORIGIN,
    search: { activity: "walk", label: "Caminar" },
};

afterEach(() => {
    vi.restoreAllMocks();
    selectScenario("neutral");
});

async function resultsList() {
    return screen.findByRole("list", { name: "Resultados" });
}

describe("Resultados", () => {
    it("sin busqueda en memoria vuelve a Inicio con aviso (P-07)", async () => {
        renderAt("/resultados");
        expect(
            await screen.findByText(
                /Elige una actividad para ver recomendaciones/,
            ),
        ).toBeInTheDocument();
        expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
            "¿Qué te apetece hacer hoy?",
        );
    });

    it("anuncia la carga en una region aria-live presente desde el principio", async () => {
        renderAt("/resultados", WITH_SEARCH);
        const live = screen.getByRole("status");
        expect(live).toHaveTextContent("Buscando los mejores sitios…");
        await waitFor(() =>
            expect(live).toHaveTextContent("3 resultados actualizados"),
        );
    });

    it("lista 3 resultados ordenados con nota accesible y enlace al detalle", async () => {
        const { container } = renderAt("/resultados", WITH_SEARCH);
        const list = await resultsList();
        expect(list.tagName).toBe("OL");
        const items = within(list).getAllByRole("listitem");
        expect(items).toHaveLength(3);
        const link = within(items[0]).getByRole("link");
        expect(link.getAttribute("href")).toMatch(/^\/resultados\/ejemplo/);
        expect(
            within(items[0]).getByText(/Nota \d,\d sobre 10, (muy buena|buena|aceptable)/i),
        ).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });

    it("muestra avisos y el aviso medico de la respuesta", async () => {
        renderAt("/resultados", WITH_SEARCH);
        await resultsList();
        expect(
            screen.getByText(/Zona verde: sin datos para algún destino/),
        ).toBeInTheDocument();
        expect(
            screen.getByText(
                "Recomendación orientativa con datos abiertos. No es consejo médico.",
            ),
        ).toBeInTheDocument();
    });

    it("muestra «sin datos» cuando un factor viene a null", async () => {
        renderAt("/resultados", WITH_SEARCH);
        await resultsList();
        expect(screen.getAllByText(/Verde: sin datos/).length).toBeGreaterThan(
            0,
        );
    });

    it("Ver más opciones añade resultados", async () => {
        const { user } = renderAt("/resultados", WITH_SEARCH);
        await resultsList();
        await user.click(
            screen.getByRole("button", { name: "Ver más opciones" }),
        );
        await waitFor(async () =>
            expect(
                within(await resultsList()).getAllByRole("listitem"),
            ).toHaveLength(6),
        );
        expect(
            screen.queryByRole("button", { name: "Ver más opciones" }),
        ).not.toBeInTheDocument();
    });

    it("estado vacio con Ajustar preferencias", async () => {
        renderAt("/resultados", {
            ...WITH_SEARCH,
            preferences: { maxDistanceM: 200 },
        });
        expect(
            await screen.findByText(
                /Ningún destino encaja con tus preferencias/,
            ),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Ajustar preferencias" }),
        ).toBeInTheDocument();
    });

    it("error con Reintentar", async () => {
        vi.spyOn(recommendApi, "recommend").mockRejectedValueOnce(
            new Error("red"),
        );
        const { user } = renderAt("/resultados", WITH_SEARCH);
        expect(
            await screen.findByText(
                "No se pudieron cargar las recomendaciones.",
            ),
        ).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(await resultsList()).toBeInTheDocument();
    });

    it("una peticion invalida (422) ofrece Ajustar preferencias", async () => {
        vi.spyOn(recommendApi, "recommend").mockRejectedValueOnce(
            new ApiError(422, "invalida"),
        );
        renderAt("/resultados", WITH_SEARCH);
        expect(
            await screen.findByText(/no son válidas/),
        ).toBeInTheDocument();
        expect(
            screen.getByRole("button", { name: "Ajustar preferencias" }),
        ).toBeInTheDocument();
    });

    it("marca la alternativa cubierta y la mejor hora (Carmen)", async () => {
        selectScenario("carmen");
        renderAt("/resultados", {
            ...WITH_SEARCH,
            preferences: { profile: "senior" },
        });
        const list = await resultsList();
        expect(within(list).getByText("Alternativa cubierta")).toBeInTheDocument();
        expect(within(list).getAllByText("Mejor a las 20:30").length).toBeGreaterThan(0);
    });

    it("el orden cambia con los pesos (dos personas, mismo sitio)", async () => {
        const { unmount } = renderAt("/resultados", {
            ...WITH_SEARCH,
            preferences: {
                weights: { proximity: 1, suitability: 0, green: 0, air: 0, weather: 0 },
            },
        });
        const near = within(await resultsList()).getAllByRole("link")[0]
            .textContent;
        unmount();
        renderAt("/resultados", {
            ...WITH_SEARCH,
            preferences: {
                weights: { proximity: 0, suitability: 0, green: 0.5, air: 0.5, weather: 0 },
            },
        });
        const clean = within(await resultsList()).getAllByRole("link")[0]
            .textContent;
        expect(near).not.toBe(clean);
    });

    it("Sorpréndeme titula «Planes para ti hoy»", async () => {
        renderAt("/resultados", {
            origin: SAMPLE_ORIGIN,
            search: { activity: null },
        });
        expect(
            screen.getByRole("heading", { level: 1, name: "Planes para ti hoy" }),
        ).toBeInTheDocument();
        expect(within(await resultsList()).getAllByRole("listitem")).toHaveLength(3);
    });

    it("tiene un mapa de marcador de posicion oculto a lectores", async () => {
        const { container } = renderAt("/resultados", WITH_SEARCH);
        await resultsList();
        const map = container.querySelector(".map-view");
        expect(map).toHaveAttribute("aria-hidden", "true");
    });
});
