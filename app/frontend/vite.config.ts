/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// API de desarrollo: por defecto uvicorn local en :8000 (sin el prefijo /api, como Caddy).
// Con GOMAD_API (p. ej. GOMAD_API=https://<YOUR_DOMAIN> npm run dev) se usa la API
// desplegada, que ya atiende en /api: solo lectura, sirve para trabajar el diseño sin backend local.
const remoteApi = process.env.GOMAD_API;

// https://vite.dev/config/
export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            "/api": remoteApi
                ? { target: remoteApi, changeOrigin: true, secure: true }
                : {
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
