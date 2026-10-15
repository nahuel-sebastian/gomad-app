// Error de la API con su codigo HTTP (404, 422, 5xx). El cliente real del
// paso 3 lanzara el mismo error, asi que las pantallas no cambian.
export class ApiError extends Error {
    status: number;

    constructor(status: number, message: string) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}
