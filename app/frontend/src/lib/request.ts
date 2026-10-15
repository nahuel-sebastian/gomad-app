import type { Coordinate, RecommendRequest } from "../api/types";
import type { Preferences } from "../state/context";

// «2026-10-15T18:05:00» en hora local, sin zona (como pide el contrato)
export function localDateTime(date: Date): string {
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:00`;
}

// Peticion a /recommend con las preferencias en memoria (P-06: ahora -> +N h)
export function buildRecommendRequest(
    origin: Coordinate,
    activity: string | null,
    prefs: Preferences,
    page: { offset?: number; limit?: number } = {},
    now: Date = new Date(),
): RecommendRequest {
    const end = new Date(now.getTime() + prefs.windowHours * 3600_000);
    return {
        origin,
        activity,
        window_start: localDateTime(now),
        window_end: localDateTime(end),
        duration_min: prefs.durationMin,
        max_distance_m: prefs.maxDistanceM,
        setting: prefs.setting,
        profile: prefs.profile,
        companions: prefs.companions,
        weights: prefs.weights,
        limit: page.limit ?? 3,
        offset: page.offset ?? 0,
    };
}

// Clave estable de lo que cambia la respuesta (sin la hora)
export function preferencesKey(activity: string | null, prefs: Preferences, origin: Coordinate | null) {
    return JSON.stringify([activity, prefs, origin]);
}

// Resumen «45 min · hasta 3 km · interior o exterior»
export function preferencesSummary(prefs: Preferences): string {
    const km = prefs.maxDistanceM / 1000;
    const distance = km < 1 ? `${prefs.maxDistanceM} m` : `${String(km).replace(".", ",")} km`;
    const place = { any: "interior o exterior", outdoor: "exterior", indoor: "interior" }[prefs.setting];
    return `${prefs.durationMin} min · hasta ${distance} · ${place}`;
}
