import {
    SCENARIOS,
    getMockScenario,
    setMockScenario,
    type ScenarioId,
    type ScenarioInfo,
} from "./mock/scenario";

export type { ScenarioId, ScenarioInfo };

// Escenarios de la demo para elegir «Datos de ejemplo» (solo paso 1).
// paso 3: eliminar este modulo y su selector en Fuentes
export function listScenarios(): ScenarioInfo[] {
    return SCENARIOS;
}

export function currentScenario(): ScenarioInfo {
    return getMockScenario();
}

export function selectScenario(id: ScenarioId) {
    setMockScenario(id);
}
