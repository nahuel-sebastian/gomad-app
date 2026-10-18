import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { RouteVariant } from "../api/types";
import { useRouteNavigation } from "../components/RouteNavigation";
import { toLineString } from "../lib/geometry";
import { expectNoAxeViolations } from "./render";
import { installFakeGeo, NAV_KM_LON, NAV_LAT, NAV_LON0, navVariant } from "./geoMock";

// Controles y panel comunes de navegacion (Task 184)

function Harness({ variant }: { variant: RouteVariant | null }) {
    const nav = useRouteNavigation(variant);
    return (
        <main>
            <p data-testid="map" data-follow={String(nav.follow)} data-live={JSON.stringify(nav.live)} />
            <button type="button" onClick={nav.onUserMove}>
                Mover el mapa
            </button>
            {nav.controls}
        </main>
    );
}

let geo: ReturnType<typeof installFakeGeo> | null = null;

afterEach(() => {
    geo?.restore();
    geo = null;
    vi.restoreAllMocks();
});

async function start(variant: RouteVariant = navVariant(), secure = true) {
    geo = installFakeGeo({ secure });
    const user = userEvent.setup();
    const view = render(<Harness variant={variant} />);
    await user.click(screen.getByRole("button", { name: "Seguir mi ubicación" }));
    return { user, ...view, geo };
}

function status() {
    return screen.getByRole("status");
}

describe("useRouteNavigation", () => {
    it("pulsar Seguir mi ubicacion cambia a Dejar de seguir y sigue la posicion", async () => {
        const { geo: g } = await start();
        expect(g.raw.watchPosition).toHaveBeenCalledOnce();
        const stop = screen.getByRole("button", { name: "Dejar de seguir" });
        expect(stop).toHaveAttribute("aria-pressed", "true");
        g.emit(NAV_LAT, NAV_LON0);
        expect(screen.getByTestId("map")).toHaveAttribute("data-follow", "true");
        expect(screen.getByTestId("map")).toHaveAttribute("data-live", JSON.stringify({ lat: NAV_LAT, lon: NAV_LON0 }));
    });

    it("sobre la ruta muestra lo que queda", async () => {
        const { geo: g } = await start();
        g.emit(NAV_LAT, NAV_LON0 + NAV_KM_LON / 2);
        expect(screen.getByText("Te quedan 500 m · 6 min")).toBeInTheDocument();
    });

    it("lejos de la linea avisa de que te has alejado", async () => {
        const { geo: g } = await start();
        g.emit(NAV_LAT + 0.001, NAV_LON0 + NAV_KM_LON / 2); // ~111 m
        expect(screen.getAllByText("Te has alejado de la ruta").length).toBeGreaterThan(0);
    });

    it("cerca del final dice Has llegado", async () => {
        const { geo: g } = await start();
        g.emit(NAV_LAT, NAV_LON0 + NAV_KM_LON * 0.99);
        expect(status()).toHaveTextContent("Has llegado");
        expect(screen.queryByText(/Te quedan/)).not.toBeInTheDocument();
    });

    it("cambiar de ruta deja de seguir y reinicia la llegada", async () => {
        const { geo: g, rerender, user } = await start();
        g.emit(NAV_LAT, NAV_LON0 + NAV_KM_LON * 0.99);
        rerender(<Harness variant={navVariant({ kind: "direct", distance_m: 990 })} />);
        expect(g.raw.clearWatch).toHaveBeenCalledWith(1);
        expect(screen.getByRole("button", { name: "Seguir mi ubicación" })).toHaveAttribute("aria-pressed", "false");
        await user.click(screen.getByRole("button", { name: "Seguir mi ubicación" }));
        g.emit(NAV_LAT, NAV_LON0);
        expect(status()).toHaveTextContent("Siguiendo tu ubicación");
    });

    it("mover el mapa suelta el seguimiento y Centrar en mi lo recupera", async () => {
        const { geo: g, user } = await start();
        g.emit(NAV_LAT, NAV_LON0);
        expect(screen.queryByRole("button", { name: "Centrar en mí" })).not.toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: "Mover el mapa" }));
        expect(screen.getByTestId("map")).toHaveAttribute("data-follow", "false");
        await user.click(screen.getByRole("button", { name: "Centrar en mí" }));
        expect(screen.getByTestId("map")).toHaveAttribute("data-follow", "true");
        expect(screen.queryByRole("button", { name: "Centrar en mí" })).not.toBeInTheDocument();
    });

    it("sin permiso explica la causa y vuelve a Seguir mi ubicacion", async () => {
        const { geo: g, user } = await start();
        g.fail(1);
        expect(
            screen.getByText(
                "No podemos seguir tu ubicación: el navegador no tiene permiso. Actívalo en los ajustes del navegador.",
            ),
        ).toBeInTheDocument();
        expect(screen.getByRole("button", { name: "Seguir mi ubicación" })).toHaveAttribute("aria-pressed", "false");
        expect(g.raw.watchPosition).toHaveBeenCalledOnce();
        // volver a pulsar lo intenta otra vez (una vez, sin bucle)
        await user.click(screen.getByRole("button", { name: "Seguir mi ubicación" }));
        expect(g.raw.watchPosition).toHaveBeenCalledTimes(2);
    });

    it("sin HTTPS dice que hace falta una conexion segura", async () => {
        const { geo: g } = await start(navVariant(), false);
        expect(screen.getByText(/No podemos seguir tu ubicación: .*HTTPS/)).toBeInTheDocument();
        expect(g.raw.watchPosition).not.toHaveBeenCalled();
    });

    it("la region de estado solo anuncia cambios de estado", async () => {
        const { geo: g, user } = await start();
        expect(status()).toHaveTextContent("Siguiendo tu ubicación");
        g.emit(NAV_LAT, NAV_LON0 + NAV_KM_LON / 4);
        g.emit(NAV_LAT, NAV_LON0 + NAV_KM_LON / 2);
        expect(status()).toHaveTextContent(/^Siguiendo tu ubicación$/);
        g.emit(NAV_LAT + 0.001, NAV_LON0 + NAV_KM_LON / 2);
        expect(status()).toHaveTextContent(/^Te has alejado de la ruta$/);
        await user.click(screen.getByRole("button", { name: "Dejar de seguir" }));
        expect(status()).toHaveTextContent(/^Has dejado de seguir tu ubicación$/);
    });

    it("sin ruta no pinta controles", () => {
        geo = installFakeGeo();
        render(<Harness variant={null} />);
        expect(screen.queryByRole("button", { name: "Seguir mi ubicación" })).not.toBeInTheDocument();
    });

    it("no tiene violaciones de axe con la navegacion activa", async () => {
        const { geo: g, container } = await start();
        g.emit(NAV_LAT, NAV_LON0 + NAV_KM_LON / 2);
        await expectNoAxeViolations(container);
    });
});

describe("useRouteNavigation: llegada", () => {
    it("en una ruta de ida y vuelta no dice Has llegado al salir", async () => {
        const back = navVariant({
            // la vuelta va ~2 m al norte de la ida, como pasa con el GPS: al salir, la vuelta queda mas cerca
            geometry: toLineString([[NAV_LON0, NAV_LAT], [NAV_LON0 + NAV_KM_LON, NAV_LAT], [NAV_LON0, NAV_LAT + 0.00002]]),
            distance_m: 2000,
            duration_min: 24,
        });
        const { geo: g } = await start(back);
        g.emit(NAV_LAT + 0.000018, NAV_LON0 + NAV_KM_LON / 100);
        expect(status()).toHaveTextContent(/^Siguiendo tu ubicación$/);
        expect(screen.getByText(/^Te quedan 2,0 km/)).toBeInTheDocument();
    });

    it("lejos de la ruta pasado el final no dice Has llegado", async () => {
        const { geo: g } = await start();
        g.emit(NAV_LAT, NAV_LON0 + NAV_KM_LON * 1.3); // ~300 m mas alla del final
        expect(status()).toHaveTextContent(/^Te has alejado de la ruta$/);
    });
});
