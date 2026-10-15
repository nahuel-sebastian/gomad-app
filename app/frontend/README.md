# GoMad — frontend

SPA móvil de GoMad (React 19 + Vite 8 + TypeScript 6 + React Router 7). Documentación de trabajo en [`docs/`](docs/): empieza por [`docs/pendientes.md`](docs/pendientes.md); cada pantalla está en [`docs/pantallas.md`](docs/pantallas.md) y la guía técnica en [`docs/guia.md`](docs/guia.md).

## Requisitos

- Node ≥ 20.19 (mejor 22 LTS).

## Arrancar

```bash
npm install
npm run dev        # http://localhost:5173
```

Paso 1 (15/10): la app funciona **solo con datos de ejemplo** de `src/data/mock/`, sin llamadas de red. En «Fuentes y aviso» hay un selector «Datos de ejemplo» con los escenarios de las personas de la demo (Carmen, Lucía, Dani, Ana, familia que se muda).

## Probar

```bash
npm test           # Vitest + Testing Library + axe
npm run lint       # oxlint
npm run build      # tsc + vite build
```

## Contrato con la API

`src/api/openapi.json` lo genera y versiona Motor (no editarlo). Los tipos se regeneran con:

```bash
npm run contract   # openapi-typescript -> src/api/schema.d.ts y tsc
```

Las pantallas solo usan las funciones de `src/data/` (una por endpoint), que hoy devuelven datos de ejemplo con la forma exacta del contrato. En el paso 3 se sustituye el cuerpo de esas funciones por la llamada real a `/api/…`.

## Estructura

```
src/
  api/          openapi.json (contrato), schema.d.ts (generado), types.ts (alias)
  data/         una función por endpoint + mock/ con los datos de ejemplo
  state/        estado de la app en memoria (preferencias, ubicación, resultados)
  components/   pantallas y piezas comunes
  lib/          formato es-ES, textos de las categorías, veredicto
  styles/       main.css (tokens y clases), icons.css (iconos, aplazados)
public/
  fonts/        Figtree (OFL), servida desde nuestro dominio
```
