// Retraso simulado de red (en las pruebas, sin espera)
const DELAY_MS = import.meta.env.MODE === "test" ? 0 : 350;

export function simulate<T>(make: () => T): Promise<T> {
    return new Promise((resolve, reject) => {
        setTimeout(() => {
            try {
                resolve(make());
            } catch (error) {
                reject(error);
            }
        }, DELAY_MS);
    });
}
