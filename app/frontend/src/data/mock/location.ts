import type { LocationCandidate, LocationResponse } from "../../api/types";
import { normalize } from "../../lib/text";
import { ApiError } from "../errors";
import { MUNICIPALITIES } from "./municipalities";

// Buscador de ejemplo: municipios por nombre y una direccion inventada

export function locationMock(text: string): LocationResponse {
    const query = normalize(text);
    if (query.length < 3 || text.length > 200) {
        throw new ApiError(422, "Escribe entre 3 y 200 caracteres.");
    }
    const candidates: LocationCandidate[] = [];
    if (query.includes("calle") || query.includes("plaza")) {
        candidates.push({
            label: "Calle del Ejemplo 10, Getafe (ejemplo)",
            municipality: "Getafe",
            ine_code: "28065",
            coordinate: { lat: 40.3057, lon: -3.7329 },
            precision: "address",
        });
    }
    for (const m of MUNICIPALITIES) {
        if (candidates.length >= 6) break;
        if (normalize(m.name).includes(query.replace(/^(calle|plaza)\s+/, ""))) {
            candidates.push({
                label: m.name,
                municipality: m.name,
                ine_code: m.ine_code,
                coordinate: { lat: m.lat, lon: m.lon },
                precision: "municipality",
            });
        }
    }
    return { candidates };
}
