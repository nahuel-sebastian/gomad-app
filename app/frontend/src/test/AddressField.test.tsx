import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { LocationCandidate } from "../api/types";
import AddressField from "../components/AddressField";
import * as locationApi from "../data/location";
import { expectNoAxeViolations, SAMPLE_ORIGIN } from "./render";

const GETAFE: LocationCandidate = {
    label: "Getafe",
    municipality: "Getafe",
    ine_code: "28065",
    coordinate: { lat: 40.3057, lon: -3.7329 },
    precision: "municipality",
};

afterEach(() => {
    vi.restoreAllMocks();
});

describe("AddressField", () => {
    it("muestra candidatos con 3 letras y elegir uno llama a onChange", async () => {
        const search = vi.spyOn(locationApi, "searchLocation").mockResolvedValue({ candidates: [GETAFE] });
        const onChange = vi.fn();
        const user = userEvent.setup();
        render(<AddressField label="Desde" value={null} onChange={onChange} />);
        await user.type(screen.getByLabelText("Desde"), "get");
        await user.click(await screen.findByRole("button", { name: "Getafe" }));
        expect(search).toHaveBeenCalledWith("get");
        expect(onChange).toHaveBeenCalledWith(GETAFE);
    });

    it("con valor muestra la etiqueta y «Cambiar» llama a onChange(null)", async () => {
        const onChange = vi.fn();
        const user = userEvent.setup();
        render(<AddressField label="Hasta" value={SAMPLE_ORIGIN} onChange={onChange} />);
        expect(screen.getByText(SAMPLE_ORIGIN.label)).toBeInTheDocument();
        await user.click(screen.getByRole("button", { name: /Cambiar/ }));
        expect(onChange).toHaveBeenCalledWith(null);
    });

    it("«Usar mi ubicación» solo con allowCurrentLocation", async () => {
        const onChange = vi.fn();
        const user = userEvent.setup();
        const { rerender } = render(<AddressField label="Desde" value={null} onChange={onChange} />);
        expect(screen.queryByRole("button", { name: /Usar mi ubicación/ })).toBeNull();
        rerender(<AddressField label="Desde" value={null} onChange={onChange} allowCurrentLocation />);
        await user.click(screen.getByRole("button", { name: /Usar mi ubicación/ }));
        expect(onChange).toHaveBeenCalledWith(locationApi.sampleLocation());
    });

    it("error de búsqueda muestra un mensaje", async () => {
        vi.spyOn(locationApi, "searchLocation").mockRejectedValue(new Error("red"));
        const user = userEvent.setup();
        render(<AddressField label="Desde" value={null} onChange={vi.fn()} />);
        await user.type(screen.getByLabelText("Desde"), "getafe");
        expect(await screen.findByText("No se pudo buscar la dirección.")).toBeInTheDocument();
    });

    it("sin violaciones de axe, con candidatos y con valor elegido", async () => {
        vi.spyOn(locationApi, "searchLocation").mockResolvedValue({ candidates: [GETAFE] });
        function Harness() {
            const [value, setValue] = useState<LocationCandidate | null>(null);
            return <AddressField label="Desde" value={value} onChange={setValue} allowCurrentLocation />;
        }
        const user = userEvent.setup();
        const { container } = render(<Harness />);
        await user.type(screen.getByLabelText("Desde"), "get");
        await screen.findByRole("button", { name: "Getafe" });
        await expectNoAxeViolations(container);
        await user.click(screen.getByRole("button", { name: "Getafe" }));
        expect(screen.getByText("Getafe")).toBeInTheDocument();
        await expectNoAxeViolations(container);
    });
});
