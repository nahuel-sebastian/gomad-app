import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { axe } from "vitest-axe";
import AppRoutes from "../AppRoutes";
import { AppStateProvider } from "../state/AppState";
import type { AppStateInit } from "../state/context";

// Pinta la app completa en una ruta, con el estado inicial que pida la prueba
export function renderAt(path: string, init?: AppStateInit) {
    const user = userEvent.setup();
    const result = render(
        <MemoryRouter initialEntries={[path]}>
            <AppStateProvider init={init}>
                <AppRoutes />
            </AppStateProvider>
        </MemoryRouter>,
    );
    return { user, ...result };
}

// Comprueba con axe que no hay violaciones (el contraste no se mide en jsdom)
export async function expectNoAxeViolations(container: Element) {
    const results = await axe(container, {
        rules: { "color-contrast": { enabled: false } },
    });
    const summary = results.violations.map(
        (v) => `${v.id}: ${v.nodes.map((n) => n.html).join(" | ")}`,
    );
    if (summary.length > 0) {
        throw new Error(`Violaciones de axe:\n${summary.join("\n")}`);
    }
}

// Ubicacion de ejemplo para las pruebas (nunca va a la URL)
export const SAMPLE_ORIGIN = {
    label: "Plaza Mayor de Getafe (ejemplo)",
    municipality: "Getafe",
    ine_code: "28065",
    coordinate: { lat: 40.3057, lon: -3.7329 },
    precision: "address" as const,
};
