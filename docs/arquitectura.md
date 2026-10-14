# Arquitectura técnica — GoMad

**Fecha:** 14/10/2026 · **Estado:** aprobada por secciones en la sesión de diseño del 14/10 (pendientes al final, §10).
**Contexto:** `CLAUDE.md` (fuente de verdad del proyecto), `docs/assets/requisitos_fuentes.json`, `docs/informe-datos.md`, `docs/assets/umbrales.md`, `docs/decisiones-pendientes.md`.
**Prioridad:** sacar la app adelante para la demo del **martes 20/10/2026** con un equipo de hasta 4 personas. Ante la duda, lo simple.

---

## 1. Decisiones tomadas en esta sesión

| ID | Decisión | Resumen |
|---|---|---|
| D-01 | **Almacén** | Datos limpios en **GeoParquet** como núcleo; la app sirve con **DuckDB** (solo lectura). Oracle Autonomous DB **opcional**: carga del mismo GeoParquet + APEX para la pantalla de administración, solo si sobra tiempo |
| D-02 | **Pilotos de ruta** | Diseño **regional desde el principio** (179 municipios). **Getafe** para afinar y probar hasta el viernes 16; el sábado 17 se activa toda la Comunidad con validación por muestras. Si falla en algún municipio: ruta directa con aviso, sin tocar código |
| D-03 | **IA para F6** | Interfaz propia (`interpretar`, `redactar`) con un adaptador por proveedor. Primero **OCI Generative AI**; si el jueves 15 a mediodía no funciona, plan B (API de Anthropic). F6 funciona sin LLM (formulario editable) y hay respuestas grabadas para la demo |
| D-04 | **Ubicación escrita (RF-01)** | Buscador de Nomecalles (sin clave) + capa **`callejero_completo_2025`** de Nomecalles para las coordenadas. Respaldo: GPS o centro del municipio |
| — | **Algoritmo de rutas** | Grafo peatonal de toda la Comunidad **en memoria**; **A\* / Dijkstra bidireccional** con coste calculado por petición; **Dijkstra con radio** para las distancias de F1 |
| D-13 | **Despliegue** | **Docker Compose** en una **VM de OCI** (créditos del proyecto; preferir la forma Always Free si hay capacidad). Primer despliegue el **viernes 16** |

Por qué DuckDB y no Oracle como almacén principal: el uso es de **solo lectura** (no hay registro ni datos de usuario; solo escribe la ingesta por lotes) y todo cabe en **menos de 1 GB** limpio. No hace falta un servidor de base de datos. Oracle aporta por sus herramientas (APEX, Select AI, GenAI) y por el patrocinador, no por los datos. Además, si la app pasa a la organización, los datos en un formato abierto se pueden cargar en cualquier almacén.

---

## 2. Visión general

```
                 ┌──────────── ingest (Python, tareas programadas) ─────────────┐
portales ──► download ──► data/raw ──► normalize ──► data/clean/*.parquet ──► build_db
(CKAN, IDEM,  (download_     (+manifest)   (un módulo      (GeoParquet, EPSG:4326)   │
 Nomecalles,   sources.py)                  por fuente)                              ▼
 Ayto, AEMET,                                                    data/gomad.duckdb       (referencia + diario)
 OSM)                                                            data/realtime.duckdb    (aire, previsión)
                                                                 data/graph/<zona>/{nodes,edges}.parquet
                                                                                    │ solo lectura
                                                                                    ▼
                                                              API FastAPI (grafo en memoria) ◄── SPA (MapLibre)
                                                                                    │
                                                                         (opcional) Oracle ADB + APEX
```

---

## 3. Ingesta y almacén

### 3.1 Descarga
Se amplía `app/ingest/scripts/download_sources.py` (no se reescribe):
- Campo `refresh` (`reference|weekly|daily|hourly|on_demand`) en cada entrada de `FUENTES` y opción `--refresh <nivel>` (CLAUDE.md §6.4).
- **Comprobación de cambios** antes de descargar (`metadata_modified` de CKAN, `Last-Modified`/`ETag`). Si no cambia, no se descarga ni se reprocesa.
- Fuentes nuevas: **OSM** (extracto de Geofabrik de Madrid), **AEMET** (previsión horaria por municipio, clave en `.env`) y **`callejero_completo_2025`** (Nomecalles).
- `data/raw/manifest.json` guarda la fecha de cada recarga (RF-19).

### 3.2 Normalización
Un módulo por fuente en `app/ingest/normalize/` que escribe GeoParquet en `data/clean/`. Aplica las trampas de `docs/informe-datos.md` §2 y §4:
- codificación (UTF-8 BOM / cp1252);
- comas decimales en coordenadas y números;
- reproyección EPSG:25830 → 4326, **ignorando los `.prj` de Nomecalles**;
- código INE de 5 dígitos (`28` + 3); si solo hay nombre, unión por nombre normalizado;
- filtro de puntos fuera de la Comunidad y de coordenadas a 0;
- Ayuntamiento: `COORD_GIS_X/Y` en bancos y áreas caninas.

Añadir una fuente = añadir un módulo.

### 3.3 Construcción
`app/ingest/build_db.py` une los GeoParquet en las tablas del modelo de CLAUDE.md §6.1 (`municipality`, `destination`, `air_station`, `air_reading`, `forecast`, `route_poi`, `service`, `municipality_indicator`).

Dos ficheros según el ritmo de los datos:
| Fichero | Contenido | Se reconstruye |
|---|---|---|
| `data/gomad.duckdb` | Referencia y diario | De madrugada (y al publicarse una versión nueva de las fuentes de referencia) |
| `data/realtime.duckdb` | `air_reading` (con medias móviles del ICA: O₃ 8 h, PM 24 h), `forecast` | Cada hora, en segundos |

- DuckDB admite un solo proceso escritor: **la ingesta escribe un fichero nuevo y lo sustituye de golpe** (`rename`). La API solo abre en lectura.
- **Si una fuente falla, el fichero anterior se mantiene**; `manifest.json` lo apunta.
- Tráfico de la capital (cada 5 min): **no se guarda**; caché en memoria de la API (5–15 min).

### 3.4 Grafo peatonal
- Construcción **semanal** desde el extracto de OSM con **pyrosm** (`get_network("walking")`); si se queda sin memoria con toda la región, filtrar antes con **osmium**.
- `app/ingest/graph.py`. Salida: `data/graph/<zona>/nodes.parquet` y `data/graph/<zona>/edges.parquet` con **factores precalculados por tramo**: longitud, penalización por tipo de vía (`highway`), % de verde (VPLA en 166 municipios; parques de OSM / cubierta terrestre en los 13 sin VPLA, capital incluida), sombra si hay dato, fuente/banco/desfibrilador cerca.
- Tamaño estimado (sin verificar): del orden de 1–pocos millones de tramos, unos cientos de MB en memoria. **Medir con el extracto.**

### 3.5 Oracle (opcional)
Script que carga los mismos `data/clean/*.parquet` en Autonomous DB y pantalla de administración en APEX (+ Select AI). Solo si F1–F5 están terminados.

---

## 4. API y motor

FastAPI **sin estado**: sin sesiones ni registro; **la ubicación nunca se escribe en los logs**. Al arrancar carga el grafo en memoria y abre los dos DuckDB en solo lectura.

### 4.1 Endpoints
| Endpoint | Entrada | Salida | RF |
|---|---|---|---|
| `GET /activities` | — | Catálogo cerrado de actividades y perfiles | RF-02, RF-15 |
| `GET /location?texto=…` | Dirección o municipio | Candidatos con coordenadas (buscador de Nomecalles + callejero) | RF-01 |
| `POST /recommend` | Ubicación, actividad o «sorpréndeme», ventana de tiempo, duración, distancia máx., interior/exterior, perfil, pesos | Top 3 (+ «ver más»), nota 0–10 por factor, mejor franja, motivo, fuente y fecha de cada dato | RF-03…RF-10, RF-14…RF-16, RF-19 |
| `POST /route` | Origen, destino, perfil, pesos | Ruta directa y saludable: GeoJSON, distancia, tiempo, % verde, tramos con tráfico, fuentes/bancos/desfibriladores en ruta | RF-11…RF-13 |
| `GET /municipality/{ine_code}` | — | Indicadores por categoría (con «sin datos» explícito) y encaje con preferencias, sin ranking | RF-17, RF-18 |
| `POST /assistant/interpret` | Texto libre | Parámetros JSON validados contra esquema cerrado, editables | RF-20, RF-21, RF-24 |
| `POST /assistant/route` | Parámetros | Ruta por distancia objetivo + condiciones cumplidas/no cumplidas + explicación redactada | RF-22, RF-23 |
| `GET /sources` | — | Atribución, licencia y última recarga por fuente | RF-19 |

La API llama al buscador de Nomecalles en nombre del navegador: el front no habla con terceros.

### 4.2 Flujo de `/recommend` (determinista, sin LLM)
1. **Candidatos:** destinos de la actividad dentro de un radio en línea recta (consulta en DuckDB).
2. **Distancia real a pie:** un **Dijkstra con límite** desde el origen (`scipy.sparse.csgraph.dijkstra` con `indices` y `limit`) da en una pasada la distancia a todos los candidatos; se descartan los que superan la distancia máxima.
3. **Contexto:** previsión horaria del municipio (AEMET) y aire de la estación más cercana o de su zona.
4. **Por cada hora de la ventana:** filtros duros (lluvia, calor, aire por encima del umbral del perfil → solo cubiertos) y nota ponderada.
5. **Mejor franja** = la hora con mejor nota. Si ninguna hora es viable al aire libre → alternativa cubierta (RF-09).
6. **Explicación con plantillas** a partir de los factores dominantes (RF-10 sin LLM).

### 4.3 Módulos del motor
Cada uno se prueba por separado:
| Módulo | Responsabilidad |
|---|---|
| `repository.py` | Todas las consultas SQL (único punto que conoce DuckDB) |
| `engine/rules.py` | Filtros duros con umbrales leídos de configuración (ICA del BOE, calor, lluvia) |
| `engine/scoring.py` | Factores normalizados 0–1 × pesos → nota 0–10 |
| `engine/slots.py` | Evaluación hora a hora y mejor franja |
| `engine/explanation.py` | Plantillas en lenguaje llano con fuente y fecha |
| `routing/` | Grafo, A\*, Dijkstra con límite, ruta circular (F6) |
| `ai/` | Interfaz `interpretar` / `redactar` + adaptadores (OCI, plan B) |

### 4.4 Rutas
- **Grafo entero en memoria**, cargado una vez al arrancar. Nodo más cercano con **KD-tree** (`scipy.spatial.cKDTree`).
- **Coste por petición, vectorizado con numpy:** `coste = longitud × factor`, con `factor = 1 + w_tráfico·t − w_verde·v − …` calculado para todos los tramos a la vez (milisegundos).
- ⚠ **El coste nunca puede ser negativo ni cero** (Dijkstra/A\* lo exigen). La «bonificación» restada de CLAUDE.md §6 se implementa como **factor multiplicativo con suelo** (p. ej. `factor ≥ 0,5`). Ese suelo hace admisible la heurística de A\*: distancia en línea recta × factor mínimo.
- **A\* (o Dijkstra bidireccional)** para A→B; directa (coste = longitud) y saludable **en paralelo**.
- **F1** no calcula rutas por destino: Dijkstra con límite (§4.2). La ruta completa se calcula solo al tocar un destino.
- **Ruta circular por distancia (F6, RF-22):** puntos de paso a ≈ objetivo/3 encadenados con la ruta saludable; ±10 %.
- **Librerías:** igraph (A\*) y/o `scipy.sparse.csgraph` (Dijkstra con límite). Confirmar con una prueba el jueves.
- **Latencia estimada (sin verificar):** decenas de ms en Getafe, ~100–300 ms en la capital. Se mide el jueves/viernes. Si la capital no llega a < 5 s: **Contraction Hierarchies precalculadas para 3–4 perfiles fijos** y los deslizadores saltan entre ellos.

---

## 5. Frontend

**SPA móvil primero en React + Vite**, partiendo del prototipo `docs/idea/muevete-cerca-prototipo.html` (flujo, estilo, fuente Figtree, variables de color claro/oscuro). Navegación inferior «Mi entorno · Municipios · Perfil». Compila a estáticos que sirve Caddy.

### 5.1 Stack técnico
| Pieza | Elección | Motivo |
|---|---|---|
| Lenguaje | **TypeScript**, tipos generados del OpenAPI (`openapi-typescript`) | Si cambia el contrato de la API, el front no compila |
| Mapa | **react-map-gl** (modo MapLibre) | Capas GeoJSON para rutas y puntos |
| Navegación | **React Router** | URL por pantalla; el «atrás» del móvil funciona |
| Datos del servidor | **TanStack Query** | Caché, reintentos, estado de carga/error y descarte de respuestas viejas al mover los pesos |
| Estado local | Contexto de React + `localStorage` | Perfil, pesos y preferencias; sin cuenta |
| Estilos | **Dos ficheros globales:** `main.css` (variables de diseño del prototipo + clases de apoyo: rejilla, espaciados, tarjetas, botones, tipografía) e `icons.css` (clases de iconos) | Se aprovecha el CSS del prototipo; cambiar la identidad = cambiar variables |
| Iconos | **Google Material Symbols**, **fuente servida desde nuestro servidor** (Apache 2.0) | No cargar de `fonts.googleapis.com`: enviaría la IP de cada visitante a Google (RGPD). Igual con Figtree |
| Componentes accesibles | **Radix UI** solo para deslizador, hoja inferior y diálogo | Teclado, foco y lector de pantalla resueltos |
| Desarrollo en paralelo | **MSW** con respuestas simuladas a partir de los tipos | El front avanza sin esperar a la API |
| Pruebas | **Vitest** (lógica) + **axe** (pantallas principales) | |

### 5.2 Pantallas (partiendo del prototipo; detalle con la maquetadora)
| Pantalla | En el prototipo | Falta |
|---|---|---|
| Inicio «¿Qué te apetece hacer?» | Sí (actividades, Sorpréndeme) | Ubicación por GPS o texto (`/ubicacion`) |
| Resultados | Sí (lista, «Ver más») | Mapa MapLibre sincronizado; panel «Ajustar» con deslizadores de pesos (recálculo al soltar) |
| Detalle «¿Por qué te recomendamos este lugar?» | Sí | Nota por factor, línea horaria con mejor franja, aire y tiempo con icono + color + texto, fuente y fecha |
| Ruta | Sí | Directa vs. saludable reales, métricas, fuentes/bancos/desfibriladores, descripción en texto |
| Municipio | Sí (Getafe) | Datos reales, «sin datos» explícito, encaje con preferencias |
| Perfil (hoja de preferencias) | Sí (interior/exterior) | Perfil (mayor, carrito, sensible…), «Salgo con…», tiempo, distancia |
| Asistente (F6) | No | Texto → chips editables → ruta + condiciones cumplidas/no cumplidas |
| Fuentes y aviso | No | Licencias, fechas, «no es consejo médico», privacidad |

### 5.3 Accesibilidad (WCAG 2.1 AA)
**Diseño visual y contraste**
- Texto ≥ 4,5:1; texto grande, iconos, bordes de controles y gráficos ≥ 3:1.
- Nunca solo color: semáforo = icono + color + texto; colores del ICA (umbrales.md §1.3) como fondo de pastilla con texto de contraste suficiente.
- Foco siempre visible; legible al 200 % y a 320 px sin desplazamiento horizontal; objetivos táctiles de 44 px; respeta `prefers-reduced-motion`.

**Navegación por teclado**
- Todo operable sin ratón, orden de foco lógico, enlace «Saltar al contenido», sin trampas de foco; hojas y diálogos devuelven el foco al cerrar.
- **La lista es el equivalente completo del mapa**: todo lo que muestra el mapa está en la lista y en el resumen de ruta.

**Lectores de pantalla**
- Iconos con `aria-hidden="true"` (si no, se lee la ligadura, p. ej. «directions_run»); el significado va en texto visible o `aria-label`.
- Recalcular resultados o ruta → anuncio `aria-live="polite"` («3 resultados actualizados»).
- Ruta descrita en texto («2,4 km, 30 min, 68 % por zona verde, 2 fuentes»); notas completas («Nota 8,2 sobre 10»).

**HTML semántico**
- `lang="es"`; `header`, `nav`, `main`, `footer`; un `h1` por pantalla y encabezados en orden; `button` para acciones y `a` para navegar; formularios con `label`; resultados en `ul`/`li`.
- Al cambiar de pantalla se actualiza el título del documento y el foco va al `h1`.

**Verificación:** axe en las pruebas; revisión con `a11y-architect` antes del ensayo del lunes; prueba manual con teclado y lector de pantalla (NVDA o TalkBack) en el flujo principal.

### 5.4 Otros
- **Perfil y preferencias:** solo en `localStorage`; nada sale del dispositivo salvo la consulta.
- **Mapa base:** OpenFreeMap (sin clave) para desarrollar; **PMTiles de la Comunidad** servido como fichero estático para la demo y la entrega.
- **Modo oscuro (secundario, fuera del MVP):** interruptor en «Perfil», guardado en `localStorage`, por defecto la preferencia del sistema. Las variables de color claro/oscuro del prototipo se mantienen en `main.css` desde el principio, así que activarlo cuesta poco; al hacerlo hay que volver a comprobar el contraste en el tema oscuro.
- **Fuera del MVP:** PWA, modo sin conexión, otros idiomas.

---

## 6. Despliegue

**Docker Compose en una VM de OCI** (créditos del proyecto). Si la forma Always Free (Ampere A1) tiene capacidad en la región, usarla: no gasta créditos y sigue funcionando después del reto.

```
frontend Caddy: HTTPS automático (Let's Encrypt); sirve el front estático y los PMTiles; proxy a la API
api      FastAPI + grafo en memoria; DuckDB en solo lectura
ingest   cron: horario (aire, previsión), diario 04:00 (servicios, Nomecalles, Ayto.), semanal (OSM + grafo)
```

- Un directorio por servicio en `app/` (`api/`, `ingest/`, `frontend/`) con su `Dockerfile`; `app/deploy/docker-compose.yml`; `app/config/` montado en solo lectura en `api` e `ingest`; `app/data/` como volumen compartido.
- Necesidades: HTTPS (geolocalización), 1–2 GB de RAM para el grafo (a medir), disco persistente para `data/`.
- Claves solo en `.env` en la VM, nunca en el repositorio ni en la imagen.
- Dominio: depende del nombre (D-10); mientras tanto, subdominio gratuito.
- **Demo sin red:** el mismo Compose en un portátil con datos congelados y respuestas de IA grabadas.

---

## 7. Fiabilidad

| Fallo | Comportamiento |
|---|---|
| Cae una fuente en la ingesta | Se mantiene el fichero anterior; `manifest.json` lo registra |
| Dato viejo | La API devuelve la fecha de cada dato; el front avisa («Aire de hace 3 h: el portal no responde») |
| Cae el LLM | F6 sigue con el formulario editable; respuestas de reserva en la demo |
| Cae el tráfico en tiempo real | Penalización por tipo de vía (disponible en toda la Comunidad) |
| Municipio sin datos de mobiliario | Se muestra «sin datos» con aviso de cobertura |

---

## 8. Pruebas (pytest, solo donde hay riesgo)

- **`reglas` y `puntuacion`:** umbrales del ICA en los límites de banda; regla por perfil; personas de la demo (Carmen a 36 °C, Lucía con ozono alto).
- **Normalizadores:** muestra pequeña real de cada fuente → coordenadas dentro de la Comunidad, código INE de 5 dígitos, codificación correcta.
- **Rutas:** coste siempre positivo; la saludable nunca es más corta que la directa; destino inalcanzable → error claro; **prueba de latencia** en Getafe y la capital (< 5 s ruta, < 3 s recomendación).
- **API:** una prueba por endpoint con datos de ejemplo.

---

## 9. Roles y calendario

**Contrato entre roles (jueves por la mañana):** modelos Pydantic de entrada y salida de la API → OpenAPI. El front trabaja contra respuestas simuladas desde el primer día.

| Día | Datos | Motor | Rutas | Front (maquetadora) |
|---|---|---|---|---|
| **Mié 14** | Script: `refresco`, comprobación de cambios, OSM, AEMET, callejero. Verificar AEMET | Estructura del repo, Compose básico, VM de OCI creada | Extracto de OSM y prueba de pyrosm | Bocetos y decisión de framework |
| **Jue 15** | Normalizadores → `gomad.duckdb` y `tiempo_real.duckdb` (medias móviles del ICA) | Contrato de la API; `reglas`, `puntuacion`, `franja` con pruebas; probar OCI GenAI antes de mediodía | Grafo de Getafe + factores + A\* + Dijkstra con límite; prueba de latencia | Inicio y resultados contra respuestas simuladas |
| **Vie 16** | `indicador_municipio` (F5), `/ubicacion` | `/recomendar` con datos reales, explicaciones | `/ruta` en Getafe | Mapa, detalle, ajustes. **Primer despliegue en OCI con HTTPS** |
| **Sáb 17** | `/fuentes`, `manifest` con fechas | `/municipio` | **Grafo de toda la Comunidad** + validación (capital, San Lorenzo, uno sin datos) | Ruta, vista de municipio |
| **Dom 18** | Caché ante caídas, cron en la VM | F6: `/asistente/*` + respuestas grabadas | Ruta circular (F6) | Asistente, fuentes y aviso. **Fin del día: no se añaden más funcionalidades** |
| **Lun 19** | Todos: ensayo con las personas de la demo, errores, guion de 10 min, demo sin red |||
| **Mar 20** | **Demo** |||

**Orden de recorte si falta tiempo:** F6 → ruta saludable en toda la Comunidad (solo Getafe) → Oracle/APEX.

---

## 9b. Estructura del repositorio

Nombres en inglés y un directorio por servicio desde el 14/10 (CLAUDE.md §2.1 y §3). Ningún servicio importa código de otro: lo compartido va por `app/data/`, `app/config/`, `app/.env` y el `openapi.json`.

```
CLAUDE.md, docs/       raíz del repositorio
app/
  .env.example  .env   .env compartido por los servicios (no se sube)
  api/                 servicio API (FastAPI); pyproject.toml, Dockerfile, .venv/ local
    main.py            arranque: carga el grafo y abre DuckDB en solo lectura
    schemas.py         modelos Pydantic (contrato → OpenAPI → tipos del front)
    settings.py        rutas compartidas (GOMAD_DATA_DIR, GOMAD_CONFIG_DIR) y carga de config/*.yaml
    engine/            rules, scoring, slots, explanation
    routing/           grafo, A*, Dijkstra con límite, ruta circular
    repository.py      todas las consultas SQL
    ai/                interfaz interpretar/redactar + adaptadores (oci, plan B)
    scripts/  tests/
  ingest/              servicio de ingesta; pyproject.toml, Dockerfile, .venv/ local
    common.py          utilidades de normalización
    normalize/         un módulo por fuente → data/clean/*.parquet
    build_db.py        GeoParquet → gomad.duckdb / realtime.duckdb (sustitución atómica)
    graph.py           OSM → data/graph/<zona>/{nodes,edges}.parquet
    scripts/           download_sources.py, profile_sources.py
    tests/
  frontend/            React + Vite, compilado y servido con Caddy
    src/styles/        main.css, icons.css
    public/fonts/      Material Symbols y Figtree (servidas por nosotros)
  config/              umbrales, actividades, pesos y perfiles por defecto (con cita a la fuente); solo lectura
  deploy/              docker-compose.yml
  data/                volumen compartido, no se versiona (raw, clean, *.duckdb, graph, PMTiles)
```

| Spec (español) | Código |
|---|---|
| scripts de descarga y perfilado (nombres en español hasta el 14/10) | `app/ingest/scripts/download_sources.py`, `profile_sources.py` |
| campo `refresco`, niveles `referencia/diario/horario/demanda` | `refresh`: `reference/weekly/daily/hourly/on_demand` |
| `ingesta/`, `normalizar/`, `construir.py`, `grafo.py` | `app/ingest/`, `normalize/`, `build_db.py`, `graph.py` |
| `esquemas.py`, `motor/` (`reglas`, `puntuacion`, `franja`, `explicacion`), `rutas/`, `repositorio.py`, `ia/` | `app/api/schemas.py`, `engine/` (`rules`, `scoring`, `slots`, `explanation`), `routing/`, `repository.py`, `ai/` |
| `web/` | `app/frontend/` |
| `tiempo_real.duckdb`, `grafo/{nodos,tramos}` | `app/data/realtime.duckdb`, `app/data/graph/<zona>/{nodes,edges}` |
| tablas `municipio`, `destino`, `estacion_aire`, `lectura_aire`, `prevision`, `tramo`, `poi_ruta`, `servicio`, `indicador_municipio` | `municipality`, `destination`, `air_station`, `air_reading`, `forecast`, `edge`, `route_poi`, `service`, `municipality_indicator` |
| `/recomendar`, `/ruta`, `/municipio/{cod_ine}`, `/asistente/*`, `/fuentes`, `/actividades`, `/ubicacion` | `/recommend`, `/route`, `/municipality/{ine_code}`, `/assistant/*`, `/sources`, `/activities`, `/location` |

---

## 10. Pendientes

| # | Pendiente | Quién / cuándo | Notas |
|---|---|---|---|
| A-01 | ~~Framework del frontend~~ | ✅ 14/10 | React + Vite sobre el prototipo (§5) |
| A-02 | Detalle de cada pantalla (§5.2) | Con la maquetadora, al maquetar | No cambia la arquitectura |
| A-03 | Nombre y dominio (D-10) | Equipo | Afecta al dominio del despliegue |
| A-04 | Pesos por defecto y velocidades (D-07) | Motor, jue 15 | Velocidades con fuente citada o marcadas como criterio propio |
| A-05 | Regla de aire por perfil (D-05) | Motor, jue 15 | Ver `umbrales.md` §1.5 |
| A-06 | Umbrales de calor (D-06) | Bloqueado por P-03 (leer el plan de Sanidad) y por el esquema real de AEMET | |
| A-07 | Tabla actividad → destino definitiva (D-08) | Datos/Motor, jue 15 | |
| A-08 | Indicadores de F5 (D-09) | Datos, vie 16 | |
| A-09 | Usos de IA de CLAUDE.md §6.5 (D-11) | Equipo | Recomendado: solo el n.º 1 |
| A-10 | Forma de la VM de OCI (Always Free o de pago con créditos) | Mié 14, al crearla | Depende de la capacidad de la región |
| A-11 | Tamaño real del grafo regional y latencia en la capital | Rutas, jue 15–sáb 17 | Si no llega: CH por perfiles fijos |

### Ideas para después de la demo (no se hacen ahora)
- **Núcleo fijo y bordes configurables para la entrega a la organización:** fuentes, umbrales (con cita), pesos, perfiles, actividades y municipios con ruta en ficheros de configuración; repositorio con contrato para poder sustituir DuckDB por Oracle u otro almacén (DDL de Oracle con `SDO_GEOMETRY`, script de carga desde GeoParquet, pruebas de contrato que cualquier implementación debe pasar); `README` de entrega.
- Publicar el catálogo unificado en GeoParquet como dataset abierto CC BY.
