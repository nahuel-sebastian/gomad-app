# GoMad — frontend

SPA móvil de GoMad (React 19 + Vite 8 + TypeScript 6 + React Router 7). Documentación de trabajo en [`docs/`](docs/): empieza por [`docs/pendientes.md`](docs/pendientes.md); cada pantalla está en [`docs/pantallas.md`](docs/pantallas.md) y la guía técnica en [`docs/guia.md`](docs/guia.md).

## Requisitos

- Node ≥ 20.19 (mejor 22 LTS).

## Arrancar

```bash
npm ci
npm run dev        # http://localhost:5173, con la API local de uvicorn en :8000
```

**Solo front, contra la API desplegada** (sin Python, Docker ni datos en tu PC):

```bash
GOMAD_API=https://<YOUR_DOMAIN> npm run dev
```

Vite envía `/api/*` a la VM. La API solo lee datos, así que no se puede romper nada; se ve el backend desplegado (no el de una rama sin fusionar) y, si la VM está apagada, las pantallas muestran el error de carga. Los cambios van por rama y PR, nunca en la VM.

Paso 1 (15/10): la app funciona **solo con datos de ejemplo** de `src/data/mock/`, sin llamadas de red. En «Fuentes y aviso» hay un selector «Datos de ejemplo» con los escenarios de las personas de la demo (Carmen, Lucía, Dani, Ana, familia que se muda).

## Probar

```bash
npm test           # Vitest + Testing Library + axe
npm run lint       # oxlint
npm run build      # tsc + vite build
```

## Imagen de producción y despliegue

El `Dockerfile` es multi-stage: `node:22.23.3-alpine` hace `npm ci` y `npm run build`, y la imagen final (`caddy:2.8.4`) solo lleva el `Caddyfile` y `dist` en `/srv/web`. No hace falta `dist/` local; el `.dockerignore` deja fuera `node_modules/`, `dist/`, `docs/` y `.env*`. Las pruebas no se ejecutan en la imagen: pásalas antes (`npm test`).

En local, desde `app/` (con `app/.env` y `app/deploy/.env`, `DOMAIN=:80`):

```bash
docker compose -f deploy/docker-compose.yml up -d --build
curl -s localhost/api/health             # {"status":"ok"}
docker compose -f deploy/docker-compose.yml down
```

`app/deploy/deploy.sh` (en local, con `--no-pull`) hace `git pull --ff-only`, `up -d --build`, comprueba `/` y `/api/health` y resume el commit y los contenedores.

### Desplegar en la VM

**Primer despliegue** (antes del primer `git pull` la VM no tiene `deploy.sh`, así que se actualiza a mano y el guion va con `--no-pull`). Desde el PC:

```bash
ssh -i ~/.ssh/gomad-oci.key ubuntu@<SERVER_IP>
```

En la VM:

```bash
cd ~/GoMad
git status --short          # debe salir vacío
git pull --ff-only          # la primera vez: así ya existe app/deploy/deploy.sh
rm -r app/frontend/dist     # solo la página de prueba creada a mano
app/deploy/deploy.sh --no-pull
```

Comprobación desde el PC (y abrir `http://<SERVER_IP>/` en el navegador del móvil):

```bash
curl -s http://<SERVER_IP>/ | grep -o '<title>.*</title>'                              # <title>GoMad</title>
curl -s http://<SERVER_IP>/api/health                                                  # {"status":"ok"}
curl -s -o /dev/null -w "%{http_code} %{content_type}\n" http://<SERVER_IP>/resultados/x   # 200 text/html
```

Si falla, en la VM desde `~/GoMad/app`:

```bash
docker compose -f deploy/docker-compose.yml ps
docker compose -f deploy/docker-compose.yml logs --tail=80
```

**Despliegues siguientes:** `app/deploy/deploy.sh` desde `~/GoMad` (ya hace el `git pull --ff-only`).

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
