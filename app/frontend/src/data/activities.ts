import type { ActivitiesResponse } from "../api/types";
import { getJson } from "./http";
import { ACTIVITIES_MOCK } from "./mock/activities";
import { simulate } from "./mock/delay";
import { sampleDataMode } from "./mode";

// GET /api/activities
export function getActivities(): Promise<ActivitiesResponse> {
    if (sampleDataMode()) return simulate(() => structuredClone(ACTIVITIES_MOCK));
    return getJson<ActivitiesResponse>("/activities");
}
