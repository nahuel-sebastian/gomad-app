// En las pruebas (MODE=test) las funciones de src/data usan los datos de ejemplo: nunca la red.
// Se lee en cada llamada para que una prueba pueda simular otro modo con vi.stubEnv.
export function sampleDataMode(): boolean {
    return import.meta.env.MODE === "test";
}
