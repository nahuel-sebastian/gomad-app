import { describe, expect, it } from "vitest";
import {
    formatDistance,
    formatHour,
    formatMinutes,
    formatNumber,
    formatScore,
    formatSourceDate,
    formatTimeAgo,
} from "../lib/format";
import { aqiLabel, verdictFor } from "../lib/labels";

describe("formato es-ES", () => {
    it("formatea notas con coma decimal", () => {
        expect(formatScore(8.7)).toBe("8,7");
        expect(formatScore(9)).toBe("9,0");
    });

    it("formatea distancias en m o km", () => {
        expect(formatDistance(650)).toBe("650 m");
        expect(formatDistance(1830)).toBe("1,8 km");
        expect(formatDistance(12000)).toBe("12 km");
    });

    it("formatea minutos redondeados", () => {
        expect(formatMinutes(21.6)).toBe("22 min");
        expect(formatMinutes(95)).toBe("1 h 35 min");
    });

    it("formatea numeros con separador de miles", () => {
        expect(formatNumber(183374)).toBe("183.374");
        expect(formatNumber(4.25)).toBe("4,3");
    });

    it("toma la hora local de Madrid del datetime sin zona", () => {
        expect(formatHour("2026-07-15T20:30:00")).toBe("20:30");
    });

    it("formatea la fecha de una fuente", () => {
        expect(formatSourceDate("2026-10-14T18:00:00")).toBe("14/10 18:00");
    });

    it("dice hace cuanto se actualizo", () => {
        const now = new Date("2026-10-15T12:00:00");
        expect(formatTimeAgo("2026-10-15T11:48:00", now)).toBe("hace 12 min");
        expect(formatTimeAgo("2026-10-15T09:00:00", now)).toBe("hace 3 h");
        expect(formatTimeAgo("2026-10-12T12:00:00", now)).toBe("hace 3 días");
    });
});

describe("textos", () => {
    it("da el texto oficial del ICA o sin datos", () => {
        expect(aqiLabel("fair")).toBe("Razonablemente buena");
        expect(aqiLabel("extremely_poor")).toBe("Extremadamente desfavorable");
        expect(aqiLabel(null)).toBe("Sin datos");
    });

    it("calcula el veredicto a partir de la nota (P-02)", () => {
        expect(verdictFor(8.7).text).toBe("Muy buena opción");
        expect(verdictFor(7).text).toBe("Buena opción");
        expect(verdictFor(5.2).text).toBe("Opción aceptable");
    });
});
