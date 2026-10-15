import { describe, expect, it } from "vitest";
import type { RouteVariant } from "../api/types";
import { lineCoordinates, toLineString } from "./geometry";

describe("geometria de la ruta", () => {
    it("lee las coordenadas de un LineString", () => {
        const g = toLineString([
            [-3.7, 40.3],
            [-3.71, 40.31],
        ]);
        expect(lineCoordinates(g)).toHaveLength(2);
    });

    it("devuelve vacio si la geometria no es un LineString", () => {
        const g = { type: "Point" } as unknown as RouteVariant["geometry"];
        expect(lineCoordinates(g)).toEqual([]);
        expect(lineCoordinates(undefined)).toEqual([]);
    });
});
