# Frontend — estado y guía para construirlo a mano

**Fecha:** 14/10/2026 · **Auditado:** `app/frontend/` en `main`, commit `4e875de` (último cambio del front: `aa5102f` «Frontend: ajustes interfaz»).
**Sustituye a:** Task 10 de `docs/plan-implementacion.md` como guía de ejecución. Las Tasks 23–25 y las filas de Front de viernes a domingo se hacen **a mano** siguiendo §3 de este documento (ver la nota **[manual guiado]** en el plan).
**Especificación de pantallas:** `docs/pantallas.md` (qué lleva cada pantalla, campos del contrato, estados y accesibilidad).

> Esta guía **no programa la interfaz**: da el estado, los desajustes, el orden de trabajo, la configuración (que no es UI) y los criterios para dar cada paso por terminado. Los componentes de pantalla los escribe la persona del front.

---

## 1. Inventario (lo que hay hoy)

### 1.1 Historia
| Commit | Qué |
|---|---|
| `e7d5548` | Directorio vacío `app/frontend/` |
| `22b9f66`, `a651fc7`, `995adfc` | `Caddyfile` (proxy `/api/*` → `api:8000`, SPA con `try_files`, logs sin URL ni IP) y `Dockerfile` provisional |
| `91a6892` | Proyecto Vite (plantilla `react-ts` con Oxlint), cabecera, inicio, resultados, `main.css`, logo |
| `aa5102f` | Ajustes de interfaz (Hero, Results, `main.css`) |

### 1.2 Ficheros
| Fichero | Contenido |
|---|---|
| `package.json` | Scripts `dev`, `build` (`tsc -b && vite build`), `lint` (`oxlint`), `preview`. **Sin** `test`, `types` ni `contract` |
| `package-lock.json` | Resuelve `react`/`react-dom` 19.3.0, `vite` 8.3.4, `typescript` 6.0.3, `@vitejs/plugin-react` 6.1.2, `oxlint` 1.88.0, `@types/node` 24.19.2 |
| `vite.config.ts` | Solo `react()`. Sin proxy de desarrollo para `/api` ni configuración de Vitest |
| `tsconfig*.json`, `.oxlintrc.json`, `.gitignore`, `README.md` | Los de la plantilla de Vite (el README es el genérico en inglés) |
| `index.html` | `lang="es"`, `viewport-fit=cover`, `theme-color`, **carga Figtree desde `fonts.googleapis.com`** (`index.html:10-14`), CSS enlazados con `<link>` (Vite los empaqueta), título «GoMAD · Muévete cerca» |
| `src/main.tsx` | `createRoot` + `StrictMode` |
| `src/App.tsx` | Navegación con `useState<"home" \| "results">` (`App.tsx:9`), sin router; skip link; pie con aviso solo en Inicio |
| `src/components/Header.tsx` | Logo + botón hamburguesa (`aria-expanded`, `aria-controls`) + `nav` con enlaces `#entorno`, `#municipios`, `#perfil`; componente `Icon` local |
| `src/components/Hero.tsx` | Ilustración SVG (`aria-hidden`) + `h1` fijo + pastillas con props fijas |
| `src/components/Home.tsx` | Rejilla de 5 actividades fijas, «Sorpréndeme», resumen de preferencias fijo |
| `src/components/Results.tsx` | 3 resultados fijos, filtros sin acción, hoja inferior arrastrable (puntero + botón), hueco para el mapa |
| `src/styles/main.css` | 904 líneas: variables (`main.css:1-21`, solo tema claro), base, `:focus-visible` (`main.css:73`), skip link, `prefers-reduced-motion` (`main.css:105`), cabecera, pastillas, actividades, botones, resultados, hoja inferior, puntos de corte en 768 px |
| `src/styles/icons.css` | **Una línea: un comentario sin cerrar** (`/* Iconos de GoMAD.`); no define ningún icono |
| `public/images/logo.png` | 516 KB |
| `Dockerfile` | Provisional de la Task 5: `FROM caddy:2.8.4` + `COPY Caddyfile` + `COPY dist /srv/web` |
| `Caddyfile` | Correcto y alineado con la arquitectura (no tocar) |

**Datos:** todo es simulado y está escrito dentro de los componentes (`App.tsx:29-33`, `Home.tsx:5-13`, `Results.tsx:15-55`). No hay llamadas a la API, ni MSW, ni tipos del contrato. Los resultados usan **nombres reales de parques de Getafe con notas inventadas** (el subtítulo avisa «datos de ejemplo»).

**Cómo se navega hoy:** Inicio → tocar actividad o «Sorpréndeme» → Resultados (cambio de estado, sin URL) → «Volver». El menú (Mi entorno, Municipios, Perfil) son anclas `#` sin destino. El «atrás» del móvil sale de la app.

### 1.3 Comprobaciones hechas (en una copia, sin tocar `app/frontend/`)
Hechas el 14/10 en un *worktree* temporal de `main` (`/tmp/gomad-front-audit`, ya borrado), con Node 20.20.2:

| Comprobación | Resultado |
|---|---|
| `npm ci` | OK |
| `npm run build` | ✅ OK: `dist/index.html` 0,87 kB, CSS 11,2 kB, JS 229,7 kB (71,8 kB gzip) |
| `npm run lint` (oxlint) | ✅ sin avisos |
| axe (Vitest 4.1.11 + jsdom 26.1.0 + vitest-axe 0.1.0, prueba temporal) | ✅ 0 violaciones en Inicio y en Resultados. **Ojo:** jsdom no calcula contraste; el contraste se midió aparte (ver `docs/pantallas.md` §0.1) |
| `h1` | 1 en Inicio («Hoy es un gran día para moverte»), 1 en Resultados («Correr cerca de ti») |
| `document.title` / regiones `aria-live` | Título vacío en la prueba (no se gestiona) / 0 regiones |
| `docker build` con el `Dockerfile` actual sin `dist/` | ❌ `failed to compute cache key: … "/dist": not found` |
| `docker build` con el multi-stage de §3 (paso 0) y `node:22-alpine` | ✅ imagen con `/srv/web/index.html` y `assets/` |
| Node 18 del sistema (`/usr/bin/node`) | No sirve: Vite 8 exige Node `^20.19.0 \|\| >=22.12.0`, y el sistema no trae `npm` |
| Compatibilidad del stack con React 19.3 / Vite 8.3 / TS 6.0 (`npm install --dry-run`) | Ver §2.1 |

---

## 2. Desajustes con la arquitectura y el plan

Gravedad: 🔴 bloquea la demo o el despliegue · 🟠 incumple una regla del proyecto (privacidad, accesibilidad, stack) · 🟡 mejora o riesgo menor.

### 2.1 Versiones (🟠)
El plan (cabecera y Task 10) y la arquitectura dicen **Node 20, React 18, Vite 5**; el proyecto real usa **React 19.3, Vite 8.3, TypeScript 6.0**. Comprobado con `npm install --dry-run` el 14/10 sobre el `package.json` actual:

| Pieza | Versión que encaja | Resultado |
|---|---|---|
| `react-router` | 7.18.4 | ✅ (la 8.x pide React ≥ 19.2.7; también encajaría, sin probar) |
| `@tanstack/react-query` | 5.x (5.104.2) | ✅ peer `react ^18 \|\| ^19` |
| `react-map-gl` + `maplibre-gl` | 8.1.3 + 5.24.0 | ✅ (maplibre 6.x sin probar) |
| `@radix-ui/react-slider`, `@radix-ui/react-dialog` | 1.6.1, 1.3.1 | ✅ peer React 19 |
| `vitest` + `jsdom` + Testing Library + `vitest-axe` | 4.1.11 + 26.1.0 + `@testing-library/react` 16, `@testing-library/dom` 10, `@testing-library/jest-dom` 6 + 0.1.0 | ✅ instalado **y ejecutado** (prueba con axe en verde) |
| `msw` | 2.15.0 | ✅ peer `typescript >=4.8` |
| `openapi-typescript` | 7.13.0 | ❌ **`ERESOLVE`**: peer `typescript ^5.x` contra TS 6.0.3. Funciona igual: con `--legacy-peer-deps` genera tipos que `tsc` 6.0.3 compila sin errores (comprobado). Solución recomendada en §4.2: ejecutarlo con `npx` sin añadirlo a `package.json` |

Consecuencias:
- **Los comandos de instalación de la Task 10 (paso 2) no sirven**: fijan versiones para Vite 5/React 18 (`vitest@2.1.1`, `react-map-gl@7.1.7`, `maplibre-gl@4.7.1`, `msw@2.4.9`…). Usar las de la tabla.
- **Node:** Vite 8 necesita Node ≥ 20.19 (o ≥ 22.12). Node 20 dejó de tener soporte el 30/04/2026. Recomendación: **Node 22 LTS** en el Dockerfile (`node:22-alpine`, comprobado) y en local (`nvm install 22`); Node 20.20 también funciona.
- **Recomendación: no bajar versiones.** Todo el stack encaja salvo `openapi-typescript`, que tiene un rodeo sencillo; bajar a React 18/Vite 5 costaría tiempo y rompería el trabajo en curso. Si el equipo prefiere evitar el rodeo, bajar **solo TypeScript a 5.9** (pregunta Q-01).
- React 19: `forwardRef` ya no hace falta y `ref` es una prop; las guías de React 18 siguen valiendo en lo demás.

### 2.2 Tabla de desajustes

| # | Gravedad | Desajuste | Por qué importa | Dónde | Se arregla en |
|---|---|---|---|---|---|
| D1 | 🔴 | **Dockerfile provisional** de un solo paso que copia `dist/` local; sin `.dockerignore` | `docker compose build` falla en la VM y en cualquier clon limpio (`dist/` está en `.gitignore`); bloquea el primer despliegue (V-F4, viernes) | `Dockerfile:1-3` | Paso 0 |
| D2 | 🔴 | **Sin capa de datos**: ni tipos del contrato, ni cliente, ni MSW, ni TanStack Query; todo fijo en los componentes | Ninguna pantalla puede enseñar datos reales; el criterio 1.1 del jurado («tratamiento de datos abiertos») depende de ello | `App.tsx:29-33`, `Home.tsx:5-13`, `Results.tsx:15-55` | Paso 1 |
| D3 | 🔴 | **Sin router**: navegación por `useState` | El «atrás» del móvil cierra la app; no hay URL por pantalla; no se puede enlazar Fuentes desde el pie; 8 pantallas no caben en un `if` | `App.tsx:9` | Paso 0 |
| D4 | 🟠 | **Fuentes de Google** (`fonts.googleapis.com`, `fonts.gstatic.com`) | Cada visita envía la IP a Google (RGPD; arquitectura §5.1 lo prohíbe expresamente) | `index.html:10-14` | Paso 0 |
| D5 | 🟠 | **Iconos inexistentes**: `.gomad-icon` no tiene estilos; `icons.css` es un comentario sin cerrar; las pastillas no pintan icono | El botón de menú se ve **vacío** en móvil; los indicadores incumplen «icono + color + texto» (CLAUDE.md §2.10) | `Header.tsx:9-14,51`, `Hero.tsx:8-12,76-84`, `Results.tsx:213-220`, `icons.css:1` | Paso 0 |
| D6 | 🟠 | **Sin pruebas**: ni Vitest, ni axe, ni script `test` | El plan exige Vitest + axe en cada pantalla y `npx vitest run` en el cierre de cada día y en la congelación (D-X) | `package.json` | Paso 0 |
| D7 | 🟠 | **Piezas del stack que faltan**: React Router, TanStack Query, react-map-gl/MapLibre, Radix (deslizador, diálogo), MSW, `openapi-typescript`, Vitest + axe | Arquitectura §5.1 | `package.json` | Pasos 0 y 1 |
| D8 | 🟠 | **Accesibilidad**: resultados en `div` (no `ul`/`li`); nota sin «sobre 10»; sin `aria-live`; al cambiar de vista no se mueve el foco ni cambia el título; `aria-current` fijo en «Mi entorno»; chips de filtro de 40 px; veredicto a 11 px; asa de la hoja con contraste 1,28:1 | WCAG 2.1 AA (CLAUDE.md §2.10; arquitectura §5.3) | `Results.tsx:200-231`, `App.tsx:17`, `Header.tsx:63`, `main.css:633,737,580` | Pasos 2–3 |
| D9 | 🟠 | **Aviso médico solo en Inicio**; sin fuente ni fecha en ningún dato | CLAUDE.md §2.9; RF-19 | `App.tsx:46-55` | Pasos 3 y 8 |
| D10 | 🟠 | **Navegación superior / hamburguesa** en vez de barra inferior | Arquitectura §5 y PDF de interfaz §2 dicen barra inferior; decidir con la maquetadora (Q-05) | `Header.tsx:43-68`, `main.css:164-215` | Paso 0 o al maquetar |
| D11 | 🟡 | Sin tema oscuro en las variables | Arquitectura §5.4: las variables claro/oscuro del prototipo deberían estar desde el principio (el modo oscuro en sí está fuera del MVP) | `main.css:1-21` | Cuando sobre tiempo |
| D12 | 🟡 | Nombres reales de parques con notas inventadas | El plan pide nombres **ficticios marcados «(ejemplo)»** en los datos simulados (Task 23, paso 3) para no parecer datos oficiales | `Results.tsx:18,31,44` | Paso 1 (al pasar a MSW) |
| D13 | 🟡 | `h1` «Hoy es un gran día para moverte» fijo | Contradice a Carmen (36 °C, «Ahora no») si no depende de los datos | `Hero.tsx:75` | Paso 2 (P-01) |
| D14 | 🟡 | Logo PNG de 516 KB | Penaliza la primera carga en móvil (RNF: primera recomendación < 1 min, ruta < 5 s) | `public/images/logo.png` | Paso 0 |
| D15 | 🟡 | Se pasa la etiqueta («Correr») en vez del `id` y «Sorpréndeme» como cadena mágica | `/recommend` espera `activity` = `id` o `null` | `Home.tsx:29,43`, `Results.tsx:57-60` | Paso 2 |
| D16 | 🟡 | Sin proxy de desarrollo para `/api` | En `npm run dev` las llamadas a `/api/...` no llegan a la API local | `vite.config.ts` | Paso 0 |
| D17 | 🟡 | README genérico de la plantilla y `name: "frontend"` | Documentación del servicio | `README.md`, `package.json:2` | Cuando sobre tiempo |

### 2.3 Privacidad (estado y lo que hay que vigilar al construir)
- ✅ Caddy no guarda URLs ni IP (`Caddyfile:3-18,32-34`); la API arranca con `--no-access-log`.
- ⬜ La ubicación todavía no se usa. Al añadirla: **GPS solo tras un gesto** («Usar mi ubicación»), **nunca en `localStorage`, `sessionStorage` ni en la URL**, y solo se envía en el cuerpo `POST` de `/recommend`, `/route` y `/assistant/route`.
- ⚠ `GET /location?text=` lleva la dirección en la URL: es aceptable porque Caddy la redacta y la API no guarda log de acceso, pero **no cachearla en `localStorage`** ni mostrarla en el título.
- ⚠ **Mapa base:** con OpenFreeMap, el navegador pide teselas a un tercero y revela la zona que mira la persona. Aceptable en desarrollo; para la demo, PMTiles propio (arquitectura §5.4). Decirlo en «Fuentes y aviso».
- ⚠ No usar CDNs (fuentes, iconos, librerías): todo se sirve desde nuestro dominio.

---

## 3. Plan de trabajo (a mano), alineado con el calendario

Cada paso: objetivo · ficheros · qué hacer · terminado cuando · cómo probarlo · depende de. Rutas relativas a `app/frontend/`. Commits pequeños por paso, en español (`Front: …`), en ramas `front/<día>-<tema>` y PR a `main`.

### Paso 0 — Base técnica (mié 14 noche o jue 15 antes de las 11:00) · cierra lo que quedaba de la Task 10
**Objetivo:** que el proyecto actual tenga el stack, las pruebas, las fuentes propias y un Dockerfile desplegable, sin cambiar todavía el diseño.

**Ficheros:** `package.json`, `package-lock.json`, `vite.config.ts`, `src/setupTests.ts`, `src/App.test.tsx`, `Dockerfile`, `.dockerignore`, `index.html`, `src/styles/main.css` (`@font-face`), `src/styles/icons.css`, `public/fonts/`, `src/App.tsx` (router), `README.md`.

**Qué hacer:**
1. Node 22 (o ≥ 20.19) con `nvm`; comprobar `node -v`.
2. Dependencias (versiones comprobadas en §2.1):
   ```bash
   npm install react-router@7 @tanstack/react-query@5 react-map-gl@8 maplibre-gl@5 @radix-ui/react-slider@1 @radix-ui/react-dialog@1
   npm install -D vitest@4 jsdom@26 @testing-library/react@16 @testing-library/dom@10 @testing-library/jest-dom@6 @testing-library/user-event@14 vitest-axe@0.1.0 msw@2
   ```
   (`@testing-library/user-event` no se probó en la auditoría; es la forma recomendada de simular toques y teclado.)
3. `vite.config.ts` con proxy de desarrollo y Vitest:
   ```ts
   /// <reference types="vitest/config" />
   import react from "@vitejs/plugin-react";
   import { defineConfig } from "vite";

   // https://vite.dev/config/
   export default defineConfig({
       plugins: [react()],
       server: {
           // en desarrollo, /api va a la API local (uvicorn en :8000) quitando el prefijo, como Caddy
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
   ```
   `src/setupTests.ts`:
   ```ts
   import "@testing-library/jest-dom/vitest";
   ```
   Scripts en `package.json`: `"test": "vitest run"`. Si `tsc -b` se queja de `test` en la configuración, mover la parte de Vitest a un `vitest.config.ts` aparte (en la auditoría se usó así y funcionó).
4. Prueba base `src/App.test.tsx` (la de la Task 10, paso 5: un `h1` y `axe` sin violaciones).
5. **Router:** `BrowserRouter` con las rutas de `docs/pantallas.md` (`/`, `/resultados`, `/resultados/:id`, `/ruta/:id`, `/municipios`, `/municipios/:ine_code`, `/perfil`, `/asistente`, `/fuentes`); las que aún no existan, con una página «Próximamente» que tenga su `h1`. Un componente de diseño común que, al cambiar de ruta, ponga `document.title` y mueva el foco al `h1`. Caddy ya hace `try_files {path} /index.html`, así que las URLs profundas funcionan en producción.
6. **Fuentes propias** (quitar `index.html:10-14`):
   - Figtree (OFL 1.1): copiar `figtree-latin-{400,500,600,700}-normal.woff2` y `figtree-latin-ext-…` a `public/fonts/` con su `LICENSE` (por ejemplo, del paquete `@fontsource/figtree` 5.3.0 o del repositorio oficial). Cada `.woff2` latino pesa ~11 KB.
   - `@font-face` en `main.css`:
     ```css
     @font-face {
         font-family: "Figtree";
         font-style: normal;
         font-weight: 400;
         font-display: swap;
         src: url("/fonts/figtree-latin-400-normal.woff2") format("woff2");
         unicode-range: U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD;
     }
     /* repetir para 500, 600 y 700 (y latin-ext con su unicode-range) */
     ```
   - **Iconos:** Material Symbols Rounded completo pesa **5,4 MB** (`material-symbols` 0.48.0) — demasiado para móvil. Opciones (Q-04): (a) **SVG sueltos** de Material Symbols (Apache 2.0) en `public/icons/` y `icons.css` con `mask-image` por clase, que encaja con las clases `gomad-icon--<nombre>` que ya usa el código (recomendada); (b) la fuente recortada con `pyftsubset` a los ~30 iconos usados. En cualquier caso, cerrar el comentario de `icons.css` y definir `.gomad-icon` (tamaño con `--gomad-icon-size`, `display:inline-block`, `background-color: currentColor`).
7. **Dockerfile multi-stage** (comprobado con `docker build` el 14/10):
   ```dockerfile
   # 1) compila la SPA
   FROM node:22-alpine AS build
   WORKDIR /srv/frontend
   COPY package.json package-lock.json ./
   RUN npm ci
   COPY . .
   RUN npm run build

   # 2) Caddy sirve los estaticos y hace de proxy a la API
   FROM caddy:2.8.4
   COPY Caddyfile /etc/caddy/Caddyfile
   COPY --from=build /srv/frontend/dist /srv/web
   ```
   `.dockerignore`:
   ```
   node_modules/
   dist/
   .env*
   ```
8. Logo: exportar a WebP o SVG (objetivo < 50 KB) y poner `width`/`height` en el `<img>`.
9. README del servicio: cómo arrancar (`npm run dev`, `VITE_MOCK=1 npm run dev`), probar y generar tipos.

**Terminado cuando:** `npm run build`, `npm test` y `npm run lint` en verde; `grep -rn "googleapis\|gstatic" index.html src` no devuelve nada; el botón de menú muestra su icono; `(cd ../deploy && docker compose build frontend)` funciona **sin** `dist/` local; el «atrás» del móvil vuelve de Resultados a Inicio.
**Cómo probarlo:** los comandos anteriores; en el navegador, pestaña Red: ninguna petición a dominios de terceros.
**Depende de:** nada. Avisar a Motor antes de fusionar (cambia el Dockerfile del Compose).

### Paso 1 — Tipos del contrato, cliente y MSW (jue 15, desde las 11:00) · Task 23
**Objetivo:** el front habla con la API a través de tipos generados y puede trabajar sin ella.
**Ficheros:** `src/api/openapi.json` (lo genera y versiona **Motor** en la Task 11; no crearlo a mano), `src/api/types.ts` (generado), `src/api/client.ts`, `src/mocks/handlers.ts`, `src/mocks/browser.ts`, `src/mocks/server.ts`, `src/mocks/data/*.json`, `src/mocks/data.test.ts`, `public/mockServiceWorker.js` (generado), `src/main.tsx`, `package.json`.
**Qué hacer:** según la Task 23 del plan y §4 de esta guía: scripts `types`/`contract`, cliente (el de la Task 23, paso 2, vale tal cual), datos simulados por endpoint **tipados con `satisfies`**, con nombres ficticios «(ejemplo)», un factor `green` a `null` y un resultado con `indoor_alternative: true`; `npx msw init public/ --save`; arrancar el *worker* solo con `VITE_MOCK=1`. Envolver la app en `QueryClientProvider`.
**Terminado cuando:** `npm run contract && npm test` en verde; `VITE_MOCK=1 npm run dev` funciona sin API.
**Depende de:** Task 11 fusionada (`openapi.json` en `main`, previsto jue 15 a las 11:00).

### Paso 2 — Inicio con datos (jue 15) · Task 24
**Objetivo:** Inicio según `docs/pantallas.md` §1: actividades de `/activities`, Sorpréndeme, ubicación por GPS o texto, resumen de preferencias.
**Ficheros:** los de la Task 24 (`src/screens/Home.tsx`, `src/components/LocationPicker.tsx`, `src/state/preferences.tsx`, `src/screens/Home.test.tsx`), reutilizando `Hero`, `Home` y `main.css` actuales.
**Terminado cuando:** las pruebas de la Task 24 en verde (`renders activities as buttons`, `has one h1`, `navigates to /results after activity + location`, `has no axe violations`, `never stores lat/lon in localStorage`); Inicio → Resultados en ≤ 3 toques con datos simulados.
**Depende de:** paso 1; P-01, P-04 (`docs/pantallas.md` §10) para el `h1` y «Otra».

### Paso 3 — Resultados con datos, sin mapa (jue 15) · Task 25
**Objetivo:** `docs/pantallas.md` §2 sin el mapa: `useQuery(["recommend", request])`, lista `ul/li`, nota accesible, mejor hora, «Ver más» con `offset`, `warnings`, `medical_disclaimer`, `aria-live`, estados cargando/error/vacío.
**Ficheros:** los de la Task 25 (`src/screens/Results.tsx`, `src/components/ResultCard.tsx`, `src/components/Indicator.tsx`, `src/screens/Results.test.tsx`), reutilizando la hoja inferior actual.
**Terminado cuando:** las pruebas de la Task 25 en verde (`renders 3 list items`, `shows 'Verde: sin datos' when green is null`, `'Ver más' requests offset=3`, `updates the aria-live region`, `has no axe violations`, `Indicator always has visible text`).
**Depende de:** paso 2; P-02, P-03, P-06.

### Paso 4 — Mapa, Detalle y Ajustes (vie 16) · V-F1, V-F2, V-F3
- **Mapa (V-F1):** `src/components/Map.tsx` con `react-map-gl/maplibre`, OpenFreeMap en desarrollo, marcadores numerados sincronizados con la lista; el mapa nunca tiene información que no esté en la lista. Importar `maplibre-gl/dist/maplibre-gl.css`. Cargarlo con `React.lazy` para no engordar la primera carga. **Terminado:** Vitest «seleccionar tarjeta cambia el marcador activo» (simular el mapa en jsdom, que no tiene WebGL).
- **Detalle (V-F2):** `src/screens/Detail.tsx` según `docs/pantallas.md` §3. **Terminado:** Vitest + axe; contraste de las pastillas del ICA según la tabla de `docs/pantallas.md` §0.1.
- **Ajustes (V-F3):** `src/components/SettingsSheet.tsx` (Radix Dialog + Slider) según `docs/pantallas.md` §6. **Terminado:** Vitest «soltar un peso lanza una sola petición»; mover un peso cambia el orden sin recargar.
- **Depende de:** paso 3; DEC-07 (pesos por defecto, los da `/activities`).

### Paso 5 — Primer despliegue HTTPS (vie 16, con Motor) · V-F4
**Objetivo:** `https://<dominio>/` abre en un móvil y pide la ubicación (la geolocalización exige HTTPS).
**Ficheros:** ninguno del front si el paso 0 está hecho; `app/deploy/.env` en la VM (`DOMAIN=<dominio>`).
**Terminado cuando:** `curl -I https://<dominio>/api/health` → 200 con certificado válido; la SPA carga en el móvil; recargar `/resultados` no da 404.
**Depende de:** paso 0 (D1), VM (Task 6), dominio (DEC-10).

### Paso 6 — Ruta y Municipio (sáb 17) · S-F1, S-F2
- **Ruta (S-F1):** `src/screens/Route.tsx` según `docs/pantallas.md` §4. **Terminado:** descripción en texto completa sin mirar el mapa; aviso si `approximate`; Vitest + axe.
- **Municipio (S-F2):** `src/screens/Municipality.tsx` según `docs/pantallas.md` §5. **Terminado:** Getafe (28065), Madrid (28079) y Patones con «sin datos» visibles; Vitest + axe.
- **Depende de:** `/route` (V-R1) y `/municipality` (S-M1) o sus simulaciones; P-08, P-09, P-10.

### Paso 7 — Asistente y Fuentes (dom 18) · D-F1, D-F2
- **Asistente (D-F1):** `src/screens/Assistant.tsx` según `docs/pantallas.md` §7; funciona solo con el formulario. **Primer recorte** si no hay tiempo.
- **Fuentes y aviso (D-F2):** `src/screens/Sources.tsx` según `docs/pantallas.md` §8, enlazada desde el pie de todas las pantallas.
- **Terminado:** Vitest + axe en ambas.
- **23:59 — congelación (D-X):** lo que no esté en `main` con `npm test` en verde no entra.

### Paso 8 — Accesibilidad y ensayo (lun 19) · L-5
Revisión con `a11y-architect`, recorrido completo con teclado y con lector de pantalla (NVDA o TalkBack) en el flujo Inicio → Resultados → Detalle → Ruta; contraste de las pastillas del ICA; checklist de §5.

---

## 4. Contrato con la API

### 4.1 De dónde sale
1. Motor escribe los modelos en `app/api/schemas.py` y las rutas en `app/api/main.py` (Task 11).
2. `app/api/scripts/export_openapi.py` escribe **`app/frontend/src/api/openapi.json`** y se versiona. Es el único fichero de `app/frontend/` que toca otro rol: **no crearlo a mano** para evitar conflictos.
3. La prueba `test_versioned_openapi_is_up_to_date` (en `app/api/tests/test_contract.py`) falla si el `openapi.json` versionado no coincide con la API. Si falla: `cd app/api && .venv/bin/python scripts/export_openapi.py` y regenerar los tipos del front.

Mientras no exista: los modelos de la Task 11 en `docs/plan-implementacion.md` son la referencia (resumen por pantalla en `docs/pantallas.md`).

### 4.2 Generar los tipos
Como `openapi-typescript` 7.13.0 no declara compatibilidad con TypeScript 6 (§2.1), no se añade a `package.json`; se ejecuta con `npx` y versión fija (comprobado: el resultado compila con `tsc` 6.0.3):
```json
"scripts": {
    "types": "npx -y openapi-typescript@7.13.0 src/api/openapi.json -o src/api/types.ts",
    "contract": "npm run types && tsc -b"
}
```
`src/api/types.ts` se versiona (así el Dockerfile no necesita generarlo). Si cambia el contrato y el front no compila, es lo esperado: es el aviso de la arquitectura §5.1.

### 4.3 Simular la API (MSW 2)
```ts
// src/mocks/browser.ts
import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);
```
```ts
// src/mocks/server.ts (pruebas con Vitest)
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```
```ts
// src/setupTests.ts
import "@testing-library/jest-dom/vitest";
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```
```ts
// src/main.tsx: arrancar el worker solo con VITE_MOCK=1, antes de pintar
async function enableMocks() {
    if (import.meta.env.VITE_MOCK !== "1") return;
    const { worker } = await import("./mocks/browser");
    await worker.start({ onUnhandledRequest: "bypass" });
}
enableMocks().then(() => createRoot(document.getElementById("root")!).render(/* … */));
```
`npx msw init public/ --save` crea `public/mockServiceWorker.js` (se versiona). Los *handlers* usan las rutas con `/api` (`http.post("/api/recommend", …)`), igual que el navegador. Los JSON de `src/mocks/data/` se comprueban con `satisfies Schemas["RecommendResponse"]` en `src/mocks/data.test.ts`.

### 4.4 Convención de rutas
| Dónde | Petición del navegador | Llega a FastAPI |
|---|---|---|
| Producción (Caddy) | `/api/recommend` | `/recommend` (`handle /api/*` + `uri strip_prefix /api`, `Caddyfile:22-25`) |
| Desarrollo (`npm run dev`) | `/api/recommend` | `/recommend` en `localhost:8000` (proxy de `vite.config.ts`, paso 0) |
| Desarrollo con `VITE_MOCK=1` | `/api/recommend` | no sale: responde MSW |

El cliente usa siempre la base `/api` (Task 23, `client.ts`). Nada de URLs absolutas ni llamadas a terceros desde el front (la API llama a Nomecalles en su nombre).

---

## 5. Checklist antes de fusionar cada PR del front

**Accesibilidad**
- [ ] Un `h1` por pantalla; encabezados en orden; `document.title` cambia y el foco va al `h1`.
- [ ] Todo se puede hacer con teclado; foco visible; sin trampas; hojas y diálogos devuelven el foco.
- [ ] Indicadores con icono (`aria-hidden`) + color + **texto**; «sin datos» en texto.
- [ ] Notas leídas como «Nota X sobre 10».
- [ ] Listas de resultados en `ul`/`ol` > `li`; `button` para acciones y `a` para navegar; `label` en cada campo.
- [ ] `aria-live="polite"` presente desde el primer render en las vistas que se recalculan.
- [ ] Objetivos táctiles ≥ 44 px; texto ≥ 14 px en contenido.
- [ ] Contraste ≥ 4,5:1 en texto y ≥ 3:1 en iconos, bordes de controles y foco (axe en jsdom **no** lo mide: comprobar a mano).
- [ ] A 320 px de ancho y con zoom al 200 %, sin desplazamiento horizontal.
- [ ] Mapa con equivalente completo en la lista o en el resumen de texto.
- [ ] `npm test` con axe en verde.

**Privacidad**
- [ ] La ubicación no está en `localStorage`, `sessionStorage`, la URL, el título ni la consola.
- [ ] GPS solo tras un gesto de la persona.
- [ ] Ninguna petición a terceros salvo las teselas del mapa en desarrollo (pestaña Red).
- [ ] `/assistant/interpret` recibe solo `text`, nunca la ubicación.

**Contenido y datos**
- [ ] Aviso «no es consejo médico» visible donde haya recomendaciones.
- [ ] Fuente y fecha de cada dato; «criterio propio» cuando `own_criterion`.
- [ ] Datos simulados con nombres ficticios «(ejemplo)».
- [ ] Textos en español con tildes; código en inglés; comentarios en español sin tildes (CLAUDE.md §2.1).

**Técnica**
- [ ] `npm run contract`, `npm test`, `npm run lint`, `npm run build` en verde.
- [ ] `docker compose build frontend` funciona en limpio.

---

## 6. Preguntas para el equipo

Decisiones que **no** toma esta guía.

| ID | Pregunta | Recomendación | Quién |
|---|---|---|---|
| Q-01 | ¿Se mantienen React 19 / Vite 8 / TS 6 (y se actualiza el plan) o se baja algo? | Mantener; si molesta el rodeo de `openapi-typescript`, bajar solo TS a 5.9 | Front + equipo |
| Q-02 | ¿Node 22 LTS en el Dockerfile y en local? (Node 20 sin soporte desde el 30/04/2026) | Sí, `node:22-alpine` | Front + Motor |
| Q-03 | Navegación: ¿barra inferior (arquitectura, PDF) o la hamburguesa actual? | Barra inferior en móvil, superior en escritorio | Maquetadora |
| Q-04 | Iconos: ¿SVG sueltos con `mask-image` o la fuente Material Symbols recortada? (completa: 5,4 MB) | SVG sueltos | Front |
| Q-05 | ¿El `h1` de Inicio depende del tiempo y el aire? ¿De dónde sale el estado del momento? (P-01) | Endpoint pequeño en la API o derivarlo de `/recommend` | Motor + maquetadora |
| Q-06 | Veredictos en texto y sus cortes (P-02) | Que los mande la API con la nota (el motor decide, CLAUDE.md §2.4) | Motor |
| Q-07 | Tráfico y filtros del prototipo sin campo en `/recommend` (P-03) | Quitar los filtros; tráfico solo en Ruta | Motor + maquetadora |
| Q-08 | Ventana horaria por defecto (P-06) | Ahora → fin del día, editable | Motor |
| Q-09 | Recarga de página en Resultados/Detalle (P-07) | Volver a Inicio (más simple; sin guardar nada) | Front |
| Q-10 | Lista de municipios para el selector (P-09) | `/location` con `precision: "municipality"` | Motor + Datos |
| Q-11 | ¿Se muestra la categoría `social` y el peso `suitability`? (P-10, P-11) | `social` sí si DEC-09 la incluye; `suitability` no (lo fija la actividad) | Equipo |
| Q-12 | Nombre final (DEC-10): afecta al logo, al título y a «GoMAD» en el código (`Header.tsx:39`, `index.html:17`) | — | Equipo |
| Q-13 | Desnivel y sombra en Ruta (prototipo) sin campo en el contrato (P-08) | Quitarlos (D-12) | Equipo |
