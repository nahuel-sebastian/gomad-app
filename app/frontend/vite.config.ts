/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    // proxy de desarrollo para /api (guia §3, paso 0, punto 3): uvicorn en el puerto 8000
    server: {
        proxy: {
            "/api": {
                target: "http://localhost:8000",
                rewrite: (path) => path.replace(/^\/api/, ""),
            },
        },
    },
    test: {
        environment: "jsdom",
        setupFiles: ["./src/setupTests.ts"],
    },
});
