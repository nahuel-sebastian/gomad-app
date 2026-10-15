import type { ActivitiesResponse } from "../api/types";
import { ACTIVITIES_MOCK } from "./mock/activities";
import { simulate } from "./mock/delay";

// GET /api/activities
// paso 3: sustituir por la llamada real a /api/activities
export function getActivities(): Promise<ActivitiesResponse> {
    return simulate(() => structuredClone(ACTIVITIES_MOCK));
}
