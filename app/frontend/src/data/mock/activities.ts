import type { ActivitiesResponse } from "../../api/types";

// Catalogo de app/config/activities.yaml y pesos de app/config/weights.yaml
export const ACTIVITIES_MOCK = {
    activities: [
        { id: "walk", label: "Caminar", icon: "directions_walk", outdoor: true },
        { id: "run", label: "Correr", icon: "directions_run", outdoor: true },
        { id: "swim", label: "Nadar", icon: "pool", outdoor: null },
        { id: "padel", label: "Pádel", icon: "sports_tennis", outdoor: null },
        { id: "tennis", label: "Tenis", icon: "sports_tennis", outdoor: null },
        { id: "football", label: "Fútbol", icon: "sports_soccer", outdoor: null },
        { id: "basketball", label: "Baloncesto", icon: "sports_basketball", outdoor: null },
        { id: "gym", label: "Gimnasio y cubierto", icon: "fitness_center", outdoor: false },
    ],
    profiles: ["general", "senior", "stroller", "sensitive"],
    companions: ["dog", "kids"],
    default_weights: {
        proximity: 0.3,
        suitability: 0.25,
        green: 0.2,
        air: 0.15,
        weather: 0.1,
    },
} satisfies ActivitiesResponse;
