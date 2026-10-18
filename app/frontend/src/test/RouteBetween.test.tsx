import { screen, waitFor, within } from "@testing-library/react";
import type { UserEvent } from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import * as routeApi from "../data/route";
import { selectScenario } from "../data/scenarios";
import { expectNoAxeViolations, renderAt } from "./render";
import { installFakeGeo } from "./geoMock";

afterEach(() => {
    vi.restoreAllMocks();
    selectScenario("neutral");
});

// Busca en el campo y elige el candidato (buscador de ejemplo)
async function choose(user: UserEvent, field: string, text: string, candidate: string) {
    await user.type(screen.getByLabelText(field), text);
    await user.click(await screen.findByRole("button", { name: candidate }));
}

async function chooseBoth(user: UserEvent) {
    await choose(user, "Desde", "getafe", "Getafe");
    await choose(user, "Hasta", "leganes", "Leganés");
}

describe("Ruta entre dos direcciones", () => {
    it("muestra título y los campos Desde y Hasta", () => {
        renderAt("/trayecto");
        expect(screen.getByRole("heading", { level: 1, name: "Ruta entre dos direcciones" })).toBeInTheDocument();
        expect(screen.getByLabelText("Desde")).toBeInTheDocument();
        expect(screen.getByLabelText("Hasta")).toBeInTheDocument();
        expect(screen.getByRole("link", { name: "Volver" })).toHaveAttribute("href", "/");
    });

    it("calcula la ruta y compara recomendada y directa", async () => {
        const spy = vi.spyOn(routeApi, "getRoute");
        const { user } = renderAt("/trayecto");
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        const metrics = await screen.findByRole("list", { name: "Resumen de la ruta" });
        expect(spy).toHaveBeenCalledTimes(1);
        expect(spy).toHaveBeenCalledWith({
            origin: { lat: 40.2962, lon: -3.6711 },
            destination: { lat: 40.3294, lon: -3.7802 },
            profile: "general",
            weights: null,
        });
        expect(metrics).toHaveTextContent("Distancia");
        expect(metrics).toHaveTextContent("Tiempo estimado");
        expect(metrics).toHaveTextContent("Zonas verdes");
        expect(metrics).toHaveTextContent("64 %");
        const group = screen.getByRole("group", { name: "Variante de ruta" });
        expect(within(group).getByRole("radio", { name: /Ruta recomendada/ })).toBeChecked();
        await user.click(within(group).getByRole("radio", { name: /Ruta directa/ }));
        await waitFor(() => expect(screen.getByRole("list", { name: "Resumen de la ruta" })).toHaveTextContent("18 %"));
        expect(screen.getByRole("list", { name: "Fuentes de la ruta" })).toBeInTheDocument();
    });

    it("usa el perfil de las preferencias", async () => {
        const spy = vi.spyOn(routeApi, "getRoute");
        const { user } = renderAt("/trayecto", { preferences: { profile: "senior" } });
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        await screen.findByRole("list", { name: "Resumen de la ruta" });
        expect(spy.mock.calls[0][0].profile).toBe("senior");
    });

    it("misma direccion no calcula ruta", async () => {
        const spy = vi.spyOn(routeApi, "getRoute");
        const { user } = renderAt("/trayecto");
        await choose(user, "Desde", "getafe", "Getafe");
        await choose(user, "Hasta", "getafe", "Getafe");
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        expect(await screen.findByText("El inicio y el final son el mismo punto.")).toBeInTheDocument();
        expect(spy).not.toHaveBeenCalled();
    });

    it("con una sola direccion el boton esta deshabilitado", async () => {
        const spy = vi.spyOn(routeApi, "getRoute");
        const { user } = renderAt("/trayecto");
        expect(screen.getByRole("button", { name: "Calcular ruta" })).toBeDisabled();
        await choose(user, "Desde", "getafe", "Getafe");
        const button = screen.getByRole("button", { name: "Calcular ruta" });
        expect(button).toBeDisabled();
        await user.click(button);
        expect(spy).not.toHaveBeenCalled();
    });

    it("avisa si la ruta es aproximada", async () => {
        const original = routeApi.getRoute;
        vi.spyOn(routeApi, "getRoute").mockImplementation(async (req) => {
            const data = await original(req);
            return { ...data, healthy: { ...data.healthy, approximate: true } };
        });
        const { user } = renderAt("/trayecto");
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        expect(
            await screen.findByText("Ruta aproximada en línea recta: no hay red peatonal en esta zona."),
        ).toBeInTheDocument();
    });

    it("al repetir con el mismo punto vuelve a avisar", async () => {
        const { user } = renderAt("/trayecto");
        await choose(user, "Desde", "getafe", "Getafe");
        await choose(user, "Hasta", "getafe", "Getafe");
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        const first = await screen.findByRole("alert");
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        // el aviso se vuelve a montar para que el lector de pantalla lo repita
        await waitFor(() => expect(screen.getByRole("alert")).not.toBe(first));
        expect(screen.getByRole("alert")).toHaveTextContent("El inicio y el final son el mismo punto.");
    });

    it("error de red con Reintentar", async () => {
        vi.spyOn(routeApi, "getRoute").mockRejectedValueOnce(new Error("red"));
        const { user } = renderAt("/trayecto");
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        expect(await screen.findByText("No se pudo calcular la ruta.")).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Reintentar" }));
        expect(await screen.findByRole("list", { name: "Resumen de la ruta" })).toBeInTheDocument();
    });

    it("no cambia la ubicacion de Inicio", async () => {
        const { user } = renderAt("/trayecto");
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        await screen.findByRole("list", { name: "Resumen de la ruta" });
        await user.click(screen.getByRole("link", { name: "Volver" }));
        await screen.findByRole("heading", { level: 1, name: "¿Qué te apetece hacer hoy?" });
        // sin origen, Inicio no ofrece «Sorpréndeme» y el buscador esta vacio
        expect(screen.queryByRole("button", { name: /Sorpréndeme/ })).toBeNull();
        expect(screen.getByLabelText("Escribe una dirección o un municipio")).toHaveValue("");
    });

    it("con la ruta, el mapa ocupa la pantalla y los detalles van en una hoja que se sube y se baja", async () => {
        const { user, container } = renderAt("/trayecto");
        expect(container.querySelector(".map-demo")).toBeNull();
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        await screen.findByRole("list", { name: "Resumen de la ruta" });
        expect(container.querySelector(".gomad-results .map-demo")).not.toBeNull();
        // sin boton de leyenda en esta pantalla
        expect(screen.queryByRole("button", { name: /Leyenda/i })).toBeNull();
        expect(container.querySelector(".results-legend-slot")).toBeNull();
        const handle = screen.getByRole("button", { name: "Mostrar detalles de la ruta" });
        expect(handle).toHaveAttribute("aria-expanded", "false");
        await user.click(handle);
        expect(screen.getByRole("button", { name: "Ocultar detalles de la ruta" })).toHaveAttribute("aria-expanded", "true");
        expect(container.querySelector(".results-sheet")).toHaveClass("results-sheet--expanded");
        await user.click(screen.getByRole("button", { name: "Ocultar detalles de la ruta" }));
        expect(container.querySelector(".results-sheet")).not.toHaveClass("results-sheet--expanded");
    });

    it("al calcular, el foco va al titulo y la hoja dice desde donde y hasta donde", async () => {
        const { user } = renderAt("/trayecto");
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        const heading = await screen.findByRole("heading", { level: 1, name: "Ruta entre dos direcciones" });
        await waitFor(() => expect(heading).toHaveFocus());
        expect(screen.getByText("Getafe → Leganés")).toBeInTheDocument();
    });

    it("«Cambiar direcciones» vuelve al formulario con las direcciones elegidas", async () => {
        const spy = vi.spyOn(routeApi, "getRoute");
        const { user, container } = renderAt("/trayecto");
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        await screen.findByRole("list", { name: "Resumen de la ruta" });
        await user.click(screen.getByRole("button", { name: "Cambiar direcciones" }));
        expect(container.querySelector(".map-demo")).toBeNull();
        expect(screen.getByRole("button", { name: "Cambiar la dirección «Desde»: Getafe" })).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Cambiar la dirección «Hasta»: Leganés" })).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        await screen.findByRole("list", { name: "Resumen de la ruta" });
        expect(spy).toHaveBeenCalledTimes(2);
    });

    it("sin violaciones de axe con la ruta en pantalla", async () => {
        const { user, container } = renderAt("/trayecto");
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        await screen.findByRole("list", { name: "Resumen de la ruta" });
        await expectNoAxeViolations(container);
    });
});

describe("Ruta entre dos direcciones: seguir mi ubicacion", () => {
    let geo: ReturnType<typeof installFakeGeo> | null = null;
    afterEach(() => {
        geo?.restore();
        geo = null;
    });

    it("no pide la ubicacion al entrar; al pulsar recoge la hoja y sigue la posicion", async () => {
        geo = installFakeGeo();
        const { container, user } = renderAt("/trayecto");
        await chooseBoth(user);
        await user.click(screen.getByRole("button", { name: "Calcular ruta" }));
        const button = await screen.findByRole("button", { name: "Seguir mi ubicación" });
        expect(geo.raw.watchPosition).not.toHaveBeenCalled();
        expect(geo.raw.getCurrentPosition).not.toHaveBeenCalled();
        // los controles van al principio de la hoja, antes del titulo
        const heading = screen.getByRole("heading", { level: 1, name: "Ruta entre dos direcciones" });
        expect(button.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
        await user.click(screen.getByRole("button", { name: "Mostrar detalles de la ruta" }));
        await user.click(button);
        expect(geo.raw.watchPosition).toHaveBeenCalledOnce();
        expect(screen.getByRole("button", { name: "Mostrar detalles de la ruta" })).toHaveAttribute("aria-expanded", "false");
        geo.emit(40.2962, -3.6711);
        expect(await screen.findByText(/^Te quedan /)).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });
});
