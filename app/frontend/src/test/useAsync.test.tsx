import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { useAsync } from "../data/useAsync";

describe("useAsync", () => {
    it("pasa de cargando a datos", async () => {
        const { result } = renderHook(() =>
            useAsync(() => Promise.resolve(42), []),
        );
        expect(result.current.status).toBe("loading");
        await waitFor(() => expect(result.current.status).toBe("success"));
        expect(result.current.data).toBe(42);
    });

    it("da error y se recupera con reload", async () => {
        let calls = 0;
        const { result } = renderHook(() =>
            useAsync(() => {
                calls += 1;
                return calls === 1
                    ? Promise.reject(new Error("caida"))
                    : Promise.resolve("ok");
            }, []),
        );
        await waitFor(() => expect(result.current.status).toBe("error"));
        expect(result.current.error).toBeInstanceOf(Error);
        act(() => result.current.reload());
        await waitFor(() => expect(result.current.status).toBe("success"));
        expect(result.current.data).toBe("ok");
    });

    it("descarta la respuesta vieja si cambia la peticion", async () => {
        const resolvers: ((v: string) => void)[] = [];
        const { result, rerender } = renderHook(
            ({ key }) =>
                useAsync(
                    () =>
                        new Promise<string>((resolve) => {
                            resolvers.push(resolve);
                        }),
                    [key],
                ),
            { initialProps: { key: "a" } },
        );
        rerender({ key: "b" });
        await act(async () => resolvers[1]("nueva"));
        await act(async () => resolvers[0]("vieja"));
        expect(result.current.data).toBe("nueva");
    });

    it("mantiene los datos anteriores mientras recalcula", async () => {
        const { result, rerender } = renderHook(
            ({ key }) => useAsync(() => Promise.resolve(key), [key]),
            { initialProps: { key: "a" } },
        );
        await waitFor(() => expect(result.current.data).toBe("a"));
        rerender({ key: "b" });
        expect(result.current.status).toBe("loading");
        expect(result.current.data).toBe("a");
        await waitFor(() => expect(result.current.data).toBe("b"));
    });
});
