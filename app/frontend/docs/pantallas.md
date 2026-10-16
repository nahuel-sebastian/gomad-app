# Pantallas — GoMad (especificación para construir a mano)

**Fecha:** 14/10/2026 · **Sustituye a:** Task 9 de `docs/plan-implementacion.md` (bocetos). **Estado:** propuesta del equipo de documentación, **pendiente de validar con la maquetadora** (cada sección acaba con lo que hay que validar).
**Quién lo usa:** la persona que programa el frontend (`app/frontend/`) y la maquetadora. La guía técnica (stack, configuración, plan por días, contrato) está en **`app/frontend/docs/guia.md`**.

**Fuentes de esta especificación:** CLAUDE.md §2 y §5 · `docs/arquitectura.md` §4.1, §5 · contrato de la Task 11 (`docs/plan-implementacion.md`, `schemas.py`) · prototipo `docs/idea/muevete-cerca-prototipo.html` · `docs/idea/pdf/3_GoMAD_Interfaz_de_usuario.pdf` (en adelante, «PDF de interfaz») · `docs/assets/umbrales.md` §1.3–1.5 · código de `app/frontend/` en `main` (commit `4e875de`).

> **Sobre los campos de la API.** El contrato todavía **no existe en `main`** (`app/api/schemas.py` no está; lo crea la Task 11 el jueves 15 a las 9:00). Los nombres de este documento son los modelos Pydantic de la Task 11 tal como están en el plan. Cuando se fusione, la fuente de verdad será `app/frontend/src/api/openapi.json` y los tipos generados (`src/api/types.ts`); si algo no coincide, manda el `openapi.json` y hay que corregir este documento.
>
> Todas las rutas de la API van con el prefijo `/api` desde el navegador (Caddy lo quita antes de pasar a FastAPI): `GET /api/activities` llega a la API como `GET /activities`.

> **Decisiones del 14/10:** se mantienen React 19 / Vite 8 / TS 6; **barra de navegación inferior** (§9.1); iconos con **Google Material Symbols desde un fichero de fuente propio**, **aplazados** (mientras, los indicadores van con color + texto, y el icono se añade después); la conexión con la API se hace en la **siguiente sesión** (hasta entonces, datos de ejemplo). Lista de trabajo: `pendientes.md`.

**Leyenda de estado:** ✅ hecho · 🟡 parcial (existe la maqueta, falta lógica, datos reales o accesibilidad) · ⬜ falta.

---

## 0. Reglas comunes a todas las pantallas

Se aplican en cada pantalla aunque no se repitan.

| Regla | Detalle | Origen |
|---|---|---|
| Un `h1` por pantalla | Al cambiar de pantalla: `document.title = "<h1> · GoMad"` y el foco pasa al `h1` (con `tabIndex={-1}`) | arquitectura §5.3 |
| Navegación | `header` con logo + `nav` «Mi entorno · Municipios · Perfil»; `main id="contenido"`; `footer` con el aviso y el enlace a «Fuentes y aviso» | arquitectura §5, PDF de interfaz §2 |
| URL por pantalla | Cada pantalla tiene su ruta (React Router) para que funcione el «atrás» del móvil. **La ubicación nunca va en la URL** (quedaría en el historial y en los marcadores) | arquitectura §5.1, CLAUDE.md §2.8 |
| Indicadores | Siempre **icono + color + texto**. El icono lleva `aria-hidden="true"`; el significado está en el texto | CLAUDE.md §2.10 |
| Notas | Visible «8,2»; accesible «Nota 8,2 sobre 10» (texto oculto o `aria-label` en el contenedor, no en un `div` sin rol) | arquitectura §5.3 |
| «Sin datos» | Un valor `null` del contrato se muestra como **«sin datos»**, nunca como 0 ni vacío | PDF de interfaz, principio 06 |
| Fuente y fecha | Cada dato mostrado lleva su `DataSource` (`label` + `date`); si `own_criterion` es `true`, añadir «criterio propio» | RF-19, CLAUDE.md §2.9 |
| Aviso médico | Visible en toda pantalla con recomendaciones: texto de `medical_disclaimer` (de `/recommend`) o, donde no llegue, el texto fijo del pie | CLAUDE.md §2.9 |
| Objetivos táctiles | ≥ 44 × 44 px (`--tap-min` ya existe en `main.css:19`) | WCAG 2.5.5 (AAA) / criterio del proyecto |
| Recalcular | Toda actualización de resultados o ruta se anuncia en una región `aria-live="polite"` que **existe desde el primer render** («3 resultados actualizados») | arquitectura §5.3 |
| Estados | Cada pantalla con datos remotos tiene: **cargando**, **error** (con «Reintentar»), **vacío** y **datos parciales** (`warnings`) | PDF de interfaz §4 |
| Fechas y números | Formato `es-ES`: «1,8 km», «22 °C», «20:30», «hace 12 min». Las horas del contrato (`datetime`) se muestran en hora de Madrid | — |
| Movimiento | Respetar `prefers-reduced-motion` (ya en `main.css:105`) | WCAG 2.3.3 |

### 0.1 Pastilla de indicador (componente común)

Se usa para temperatura, aire, tráfico, verde, nivel de calor y categoría del ICA.

- Estructura: `<span class="chip chip--<tono>"><span class="icon" aria-hidden="true">…</span>Aire razonablemente bueno</span>`.
- Tonos del semáforo (ya existen en `main.css`): `chip--good` (`main.css:299`), `chip--warn` (`main.css:706`); faltan `chip--bad` y `chip--nodata`.
- **Aire (ICA):** texto de la categoría oficial del BOE, nunca solo el color. Mapeo del contrato (`AqiCategory`) → texto: `good` «Buena», `fair` «Razonablemente buena», `moderate` «Regular», `poor` «Desfavorable», `very_poor` «Muy desfavorable», `extremely_poor` «Extremadamente desfavorable», `null` «Sin datos». Colores oficiales en `umbrales.md` §1.3.
- **Contraste medido** de los colores oficiales del ICA (cálculo WCAG, 14/10): blanco sobre azul «Buena» 2,91:1 ✗ (negro 6,5:1 ✓); blanco sobre verde 3,28:1 ✗ (negro 5,75:1 ✓); amarillo con blanco 1,31:1 ✗ (usar texto oscuro); blanco sobre rojo 5,22:1 ✓; blanco sobre granate 11,7:1 ✓; blanco sobre morado 4,6:1 ✓; blanco sobre gris «sin datos» 7,06:1 ✓. → **Texto oscuro sobre azul, verde y amarillo; blanco sobre rojo, granate, morado y gris.** Lo revisa `a11y-architect` el lunes (L-5).
- Los colores propios ya usados en `main.css` cumplen 4,5:1 (medido): `--muted` sobre blanco 5,82:1, `--green-dark` sobre `--green-tint` 6,9:1, `#7a4300` sobre `#fcebcb` 6,8:1, blanco sobre `--green-dark` 8,0:1, blanco sobre `#8a4b00` 6,8:1.

---

## 1. Inicio — «¿Qué te apetece hacer?»

**Ruta propuesta:** `/` · **Propósito:** pasar de «quiero moverme» a una recomendación en ≤ 3 interacciones (abrir, elegir actividad, ver resultado; RNF). **Requisitos:** RF-01, RF-02, RF-03, RF-14 (resumen), F2 (estado del momento).

### Datos
| Qué | Endpoint | Campos |
|---|---|---|
| Actividades | `GET /api/activities` | `ActivitiesResponse.activities[]`: `id`, `label`, `icon` (nombre de Material Symbols), `outdoor` (`true`/`false`/`null` = ambas). También `profiles[]`, `companions[]`, `default_weights` (`Weights`: `proximity`, `suitability`, `green`, `air`, `weather`) para el resumen de preferencias |
| Ubicación escrita | `GET /api/location?text=<texto>` (mín. 3, máx. 200 caracteres) | `LocationResponse.candidates[]`: `label`, `municipality`, `ine_code`, `coordinate` (`lat`, `lon`), `precision` (`address` \| `street` \| `municipality`) |
| Ubicación GPS | `navigator.geolocation.getCurrentPosition` **solo tras pulsar un botón** | Se guarda en memoria como `Coordinate`; **nunca** en `localStorage` ni en la URL |
| Estado del momento (municipio, temperatura, aire) | **No hay endpoint en el contrato** | Ver Preguntas P-01. Mientras tanto: solo el municipio (de `/location`) o nada |

### Contenido y textos (del prototipo y del PDF de interfaz)
1. Cabecera con ilustración y `h1` «Hoy es un gran día para moverte» → el texto **no puede ser fijo**: si hay calor, lluvia o aire desfavorable el mensaje debe cambiar (Carmen, CLAUDE.md §5.2). Propuesta: `h1` neutro «¿Qué te apetece hacer?» y el estado del momento como pastillas; o un `h1` que dependa de los datos (P-01).
2. Pastillas del estado del momento: municipio, temperatura, aire (icono + color + texto).
3. Ubicación: botón «Usar mi ubicación» + campo «Escribe una dirección o un municipio» con lista de candidatos.
4. «¿Qué te apetece hacer?»: rejilla de actividades del catálogo (en el prototipo: Correr, Caminar, Nadar, Pádel, Otra).
5. «O simplemente… **Sorpréndeme** — Te propongo un plan según tu ubicación y tu tiempo libre.» → `activity: null` en `/recommend` (RF-03).
6. «Tus preferencias: 45 min · hasta 3 km · interior o exterior» + botón «Ajustar» (abre Perfil/preferencias, §6).
7. Pie: «Recomendaciones orientativas con datos abiertos. No es consejo médico.» + enlace «Fuentes y aviso».

### Componentes y estados
- **Sin ubicación todavía:** al tocar una actividad, si no hay ubicación, se pide (GPS o texto) y después se navega a Resultados sin volver a tocar la actividad (sigue siendo ≤ 3 interacciones).
- **GPS denegado o no disponible:** mensaje «No podemos usar tu ubicación. Escribe una dirección o un municipio.» y foco al campo de texto.
- **`/location` cargando / sin candidatos / error:** «Buscando…» · «No encontramos esa dirección. Prueba con el nombre del municipio.» · «No se pudo buscar ahora. Inténtalo de nuevo.»
- **Candidato con `precision: "municipality"`:** avisar «Usaremos el centro de <municipio>» (D-04, respaldo).
- **`/activities` cargando / error:** esqueleto de la rejilla / mensaje + «Reintentar».
- **«Otra»:** el prototipo la tiene, pero el catálogo es cerrado (RF-02). Propuesta: «Otra» abre la lista completa de `activities[]` (P-04).

### Accesibilidad
- Orden de foco: «Saltar al contenido» → logo → menú → ubicación (botón GPS, campo) → actividades → Sorpréndeme → Ajustar → pie.
- Actividades: `ul` > `li` > `button` con texto visible; icono `aria-hidden`.
- Campo de dirección: `label` visible; candidatos como lista de botones (o patrón *combobox* con `aria-expanded`/`aria-activedescendant` si se hace autocompletar); resultados anunciados en `aria-live="polite"` («4 direcciones encontradas»).
- El texto de la ilustración (SVG) ya es `aria-hidden` (`Hero.tsx:20`).

### Estado actual
| Elemento | Estado | Dónde |
|---|---|---|
| Cabecera con skip link, `main`, `lang="es"` | ✅ | `App.tsx:22-26`, `index.html:2` |
| `h1` | 🟡 fijo «Hoy es un gran día para moverte» | `Hero.tsx:75` |
| Pastillas de estado | 🟡 datos fijos (`Getafe`, `22 °C`, `Aire bueno`) pasados como props; **sin icono** (el campo `icon` se define y no se pinta) | `App.tsx:29-33`, `Hero.tsx:8-12`, `Hero.tsx:76-84` |
| Actividades | 🟡 lista fija en el código, no de `/activities`; el recuadro del icono está vacío; se pasa la **etiqueta** («Correr») en vez del `id` | `Home.tsx:5-11`, `Home.tsx:29-30` |
| Sorpréndeme | 🟡 navega con la cadena «Sorpréndeme» como marcador | `Home.tsx:43`, `Results.tsx:57-60` |
| Resumen de preferencias | 🟡 texto fijo; «Ajustar» sin acción | `Home.tsx:13`, `Home.tsx:59-61` |
| Ubicación (GPS / texto) | ⬜ | — |
| Estados cargando / error | ⬜ | — |
| Aviso médico en pie | ✅ (solo en Inicio) | `App.tsx:46-55` |
| Cambio de pantalla: foco al `h1` y título | ⬜ (solo `window.scrollTo`) | `App.tsx:17` |

### Validar con la maquetadora
- Texto del `h1` y si depende del tiempo y del aire (P-01).
- Dónde va la ubicación (encima de las actividades o como paso intermedio) sin pasar de 3 interacciones.
- Iconos de cada actividad y qué hace «Otra».
- La ilustración: muestra el skyline de Madrid capital (torres KIO, Cuatro Torres, Torrespaña; `Hero.tsx:24-46`) aunque el piloto sea Getafe y el ámbito los 179 municipios.

---

## 2. Resultados — lista + mapa

**Ruta propuesta:** `/resultados` (la petición vive en el estado de la app, no en la URL; ver P-07) · **Propósito:** las 3 mejores opciones con nota, distancia, tiempo y mejor hora; el mapa acompaña. **Requisitos:** RF-05, RF-06 (resumen), RF-07, RF-08 (mejor hora), RF-09, RF-10 (breve), RF-11, RF-16 (recálculo), RF-19.

### Datos
`POST /api/recommend` con `RecommendRequest`:

| Campo | De dónde sale en el front |
|---|---|
| `origin` (`lat`, `lon`) | Ubicación de Inicio (memoria) |
| `activity` | `Activity.id` elegido; `null` = Sorpréndeme |
| `window_start`, `window_end` | Ventana horaria: ahora → ahora + N horas (P-06). Debe cumplir `window_end > window_start` (si no, la API responde 422) |
| `duration_min` (10–480) | Preferencias: «Tiempo disponible» |
| `max_distance_m` (200–50.000) | Preferencias: «Distancia máxima a pie» |
| `setting` (`outdoor` \| `indoor` \| `any`) | Preferencias: «Lugar» |
| `profile`, `companions` | Preferencias: perfil y «Salgo con…» |
| `weights` | `null` = por defecto del servidor; si la persona los ha movido, el objeto `Weights` completo |
| `limit` (por defecto 3), `offset` | «Ver más opciones» → `offset` = nº de resultados ya mostrados |

Respuesta `RecommendResponse`: `results[]` (`Recommendation`), `has_more`, `warnings[]`, `medical_disclaimer`. Por resultado:
- `destination`: `id`, `name`, `type` (`facility` \| `park` \| `recreation_area` \| `trail` \| `bathing_area`), `covered`, `municipality`, `ine_code`, `coordinate`, `source`.
- `distance_m`, `duration_min`, `score` (0–10), `best_hour` (o `null`), `indoor_alternative`, `explanation`, `factors[]` (`factor`, `value` 0–10 o `null`, `weight`, `text`), `hours[]` (para el Detalle), `sources[]`.

### Contenido y textos
- `h1`: «Correr cerca de ti» / «Planes para ti hoy» (Sorpréndeme). Subtítulo: «Las 3 mejores opciones cerca de <municipio>».
- Tarjeta numerada (1, 2, 3, el mismo número que el marcador del mapa): nombre; «Parque · 1,8 km · 22 min a pie»; pastillas (temperatura, aire, verde…); nota «8,7» + veredicto en texto («Muy buena opción», «Buena opción», «Opción aceptable» en el prototipo; P-02); mejor hora («Mejor a las 20:30») si `best_hour` no es la hora actual.
- `indoor_alternative: true` → etiqueta «Alternativa cubierta» con el motivo (de `explanation`), p. ej. «Instalación cubierta: puedes ir aunque llueva o haga calor.» (prototipo).
- `warnings[]` en un bloque visible encima de la lista («Verde: sin datos en este municipio»).
- `medical_disclaimer` visible al final de la lista.
- «Ver más opciones» solo si `has_more`.
- Barra de filtros del prototipo («Cerca de ti», «Aire bueno», «Parques», «Con sombra», «Con fuentes», «Sin tráfico»): **no existen en el contrato** (P-03). O se quitan, o se convierten en accesos a los pesos/preferencias.

### Componentes y estados
| Estado | Qué ve la persona |
|---|---|
| Cargando | Esqueleto de 3 tarjetas + «Buscando los mejores sitios…» (en `aria-live`) |
| Error (red o 5xx) | «No se pudieron cargar las recomendaciones.» + «Reintentar» |
| 422 (petición inválida) | Mensaje + «Ajustar preferencias» |
| Vacío (`results` = []) | «Ningún destino encaja con tus preferencias. Prueba a ampliar la distancia máxima o a cambiar entre interior y exterior.» (prototipo) + botón «Ajustar preferencias» |
| Datos parciales | `warnings[]` visibles; factor con `value: null` → «Verde: sin datos» |
| Dato viejo | El aviso llega en `warnings[]` con la hora real del dato (Foco de revisión n.º 2) |
| Alternativa cubierta | Etiqueta «Alternativa cubierta» + motivo (RF-09) |
| Recalculando (pesos cambiados) | La lista anterior se mantiene atenuada hasta que llega la nueva; anuncio «3 resultados actualizados» |

### Mapa (RF-11, viernes V-F1)
- Marcadores numerados igual que la lista; tocar una tarjeta resalta el marcador y al revés.
- **La lista es el equivalente completo del mapa**: el mapa lleva `aria-hidden="true"` o un `aria-label` descriptivo y no contiene información que no esté en la lista.
- En móvil: mapa a pantalla completa y lista en hoja inferior (ya maquetado, ver Estado actual). En escritorio: lista a la izquierda, mapa a la derecha.

### Accesibilidad
- Resultados como `ol`/`ul` > `li`; el número de la tarjeta es visual (`aria-hidden`) si la lista ya es ordenada.
- Cada tarjeta es **un enlace** al Detalle (`a`, navegación), con el nombre como texto del enlace; no anidar botones dentro.
- Nota accesible: «Nota 8,7 sobre 10, muy buena opción».
- Región `aria-live="polite"` presente desde el principio para «N resultados actualizados».
- Asa de la hoja inferior: ya es `button` con `aria-expanded` y etiqueta (`Results.tsx:172-189`); su barra visual (`--border` sobre blanco) tiene **1,28:1** de contraste: subir a ≥ 3:1 (WCAG 1.4.11).
- Los chips de filtro miden 40 px de alto (`main.css:633`): subir a 44 px.
- El veredicto usa 11 px (`main.css:737`): demasiado pequeño para personas mayores; mínimo 14 px.

### Estado actual
| Elemento | Estado | Dónde |
|---|---|---|
| Maqueta de tarjetas (nombre, meta, pastillas, nota, veredicto) | 🟡 datos fijos con nombres reales de Getafe y notas inventadas (el subtítulo dice «datos de ejemplo») | `Results.tsx:15-55`, `Results.tsx:195-196` |
| `h1` | ✅ | `Results.tsx:193` |
| Lista semántica | ⬜ son `div`, no `ul`/`li` | `Results.tsx:200-202` |
| Nota accesible «sobre 10» | ⬜ | `Results.tsx:224-231` |
| Pastillas con icono | ⬜ solo texto y color | `Results.tsx:213-220` |
| Hoja inferior con arrastre y asa accesible | ✅ (falta contraste del asa) | `Results.tsx:117-189`, `main.css:536-580` |
| Volver | ✅ botón (con el «atrás» del móvil no funciona: no hay router) | `Results.tsx:65-78` |
| Filtros | 🟡 botones sin acción ni `aria-pressed` | `Results.tsx:79-113` |
| «Ver más opciones» | 🟡 sin acción | `Results.tsx:235-239` |
| Mapa | ⬜ hueco reservado | `Results.tsx:243` |
| Estados cargando / error / vacío / warnings / aviso médico | ⬜ (el pie con el aviso solo sale en Inicio) | `App.tsx:46` |
| `aria-live` | ⬜ | — |

### Validar con la maquetadora
- Umbrales y textos del veredicto (P-02).
- Qué pastillas lleva cada tarjeta (el prototipo pone tráfico, que `/recommend` no devuelve; P-03).
- Qué hacer con la barra de filtros (P-03).
- Dónde va la mejor hora y la etiqueta «Alternativa cubierta» en la tarjeta.

---

## 3. Detalle — «¿Por qué te recomendamos este lugar?»

**Ruta propuesta:** `/resultados/:id` (con `id` = `destination.id`; los datos salen de la respuesta de `/recommend` ya en caché) · **Requisitos:** RF-06, RF-07, RF-08, RF-09, RF-10, RF-19. Plan: V-F2 (viernes).

### Datos
De la `Recommendation` elegida (sin petición nueva): `destination`, `score`, `factors[]`, `best_hour`, `hours[]` (`hour`, `score`, `outdoor_ok`, `reasons[]`, `temperature_c`, `feels_like_c`, `precip_prob`, `aqi_category`), `indoor_alternative`, `explanation`, `sources[]`. Y `medical_disclaimer` de la respuesta.

### Contenido y textos (prototipo y PDF de interfaz §4)
- `h1` con el nombre; meta «Parque · 1,8 km · 22 min a pie»; nota + veredicto.
- Tres indicadores del momento: temperatura, aire, (tráfico; P-03).
- «¿Por qué te recomendamos este lugar?»: `explanation` + lista de `factors[]` con su `text` y su nota («Aire: razonablemente bueno — 8 sobre 10»). Factor con `value: null` → «sin datos (no cuenta en la nota)».
- «Mejor franja horaria»: línea de horas (`hours[]`) con la mejor marcada; con calor/lluvia/aire malo: «Ahora no: calor extremo. Mejor a las 20:30» (Carmen) y alternativa cubierta.
- Fuentes: lista de `sources[]` con `label`, fecha («Aire: Comunidad de Madrid, 14/10 18:00») y «criterio propio» si `own_criterion`.
- Botones «Ver ruta en el mapa» (→ Ruta) y «Ver otras opciones» (→ Resultados).
- Aviso médico; si el aire es «Regular» o peor, la recomendación literal del BOE para el perfil (`umbrales.md` §1.4), solo si la API la envía en `explanation`/`reasons` (el front no la elige; P-05).

### Componentes y estados
- Acceso directo a la URL sin datos en caché (recarga de página): volver a Resultados o pedir de nuevo `/recommend` (P-07).
- Horas con `score: null` / `outdoor_ok: null` → «sin datos» en la línea horaria.

### Accesibilidad
- Línea horaria: **tabla** (`table` con `th` de hora) o lista; nunca solo un gráfico. Cada hora: «20:00, nota 8,1, 24 °C, aire razonablemente bueno, apta para exterior».
- Mejor hora destacada con texto («Mejor hora»), no solo color.

### Estado actual
⬜ No existe (no hay pantalla de detalle; las tarjetas no son enlaces).

### Validar con la maquetadora
- Forma de la línea horaria en móvil (tabla desplazable o lista).
- Cuántos factores se ven sin desplegar.

---

## 4. Ruta saludable

**Ruta propuesta:** `/ruta/:id` · **Requisitos:** RF-11, RF-12, RF-13 (Should). Plan: S-F1 (sábado).

### Datos
`POST /api/route` con `RouteRequest`: `origin`, `destination` (= `destination.coordinate`), `profile`, `weights` (`RouteWeights`: `traffic`, `green`, `fountains`; `null` = por defecto).
Respuesta `RouteResponse`: `direct` y `healthy` (`RouteVariant`: `kind`, `geometry` GeoJSON LineString, `distance_m`, `duration_min`, `green_pct` o `null`, `traffic_m`, `pois[]` con `type` `fountain`/`bench`/`bin`/`toilet`/`dog_area`/`playground`/`aed`/`outdoor_gym`/`supermarket`, `approximate`, `description`), `warnings[]`, `sources[]`.

### Contenido y textos
- `h1` «Ruta a <destino>»; pestañas o selector «Ruta recomendada» / «Ruta directa» (prototipo).
- Métricas por variante: Distancia, Tiempo estimado, Zonas verdes (%), metros con tráfico; fuentes, bancos, desfibriladores en ruta.
- `description` de cada variante como **resumen en texto** («2,4 km, 30 min, 68 % por zona verde, 2 fuentes»): es el equivalente del mapa.
- Leyenda del mapa: «Zonas verdes», «Recomendada», «Tráfico intenso».
- `approximate: true` → aviso «Ruta aproximada en línea recta: no hay red peatonal en esta zona.»; fuera de los pilotos, «Ruta directa con aviso de cobertura» (PDF de interfaz §4).
- Desnivel y sombra (prototipo): **no están en `RouteVariant`** (D-12, desnivel fuera del MVP). No mostrarlos (P-08).
- Botón «Elegir esta ruta» del prototipo: sin función definida en el contrato (P-08).

### Accesibilidad
- Selector de variante: `role="tablist"` o grupo de `radio`.
- Al cambiar la variante, anuncio en `aria-live`.
- PDI en ruta como lista con conteo por tipo («2 fuentes, 5 bancos, 1 desfibrilador»).

### Estado actual
⬜ No existe.

### Validar con la maquetadora
- Comparación lado a lado o por pestañas en móvil.
- Iconos de cada tipo de PDI.

---

## 5. Municipio

**Ruta propuesta:** `/municipios` (selector) y `/municipios/:ine_code` · **Requisitos:** RF-17, RF-18 (Should), RF-19. Plan: S-F2 (sábado). Persona: «Familia que se muda».

### Datos
`GET /api/municipality/{ine_code}` → `MunicipalityResponse`: `ine_code`, `name`, `population` (o `null`), `indicators[]` (`category` `sport`/`nature`/`mobility`/`health`/`education`/`connectivity`/`social`, `key`, `label`, `value` o `null`, `unit`, `year`, `source`), `fit[]` (frases sin ranking).
Código inexistente → 404 legible (S-M1).
Selector de municipio: **no hay endpoint que liste los 179** (P-09). Opciones: usar `/location?text=` (candidatos con `precision: "municipality"`) o una lista estática generada.

### Contenido y textos (prototipo + PDF de interfaz §5)
- `h1` con el nombre; subtítulo «Lo que ofrece el municipio para tu bienestar»; población.
- «¿Qué ofrece este municipio?»: una sección por categoría (`h2`) — Deporte, Naturaleza, Movilidad, Salud, Educación, Conectividad (y «Social», que está en el contrato pero no en el PDF; P-10). Cada indicador: `label`, valor con `unit`, año, fuente.
- `value: null` → «Sin datos» (y por qué si la fuente lo dice: «la EIEL no cubre este municipio»).
- «¿Cómo encaja contigo?»: `fit[]`.
- «Buscar actividad en <municipio>» → Inicio con ese municipio como ubicación (centro del municipio).
- **Sin rankings ni comparaciones** entre municipios (CLAUDE.md §5).

### Accesibilidad
- Indicadores como lista de definiciones (`dl`) o tabla por categoría.
- «Sin datos» en texto, no un guion.

### Estado actual
⬜ No existe. El enlace «Municipios» del menú apunta a `#municipios`, que no existe en la página (`Header.tsx:18`).

### Validar con la maquetadora
- Cómo se elige el municipio (buscador, lista, mapa).
- Aspecto de «sin datos» (que no parezca un error).

---

## 6. Perfil / preferencias

**Ruta propuesta:** hoja inferior o diálogo que se abre desde «Ajustar» (Inicio, Resultados) y desde «Perfil» en el menú (`/perfil`) · **Requisitos:** RF-14, RF-15, RF-16. Plan: V-F3 (viernes).

### Datos
- De `GET /api/activities`: `profiles[]` (`general`, `senior`, `stroller`, `sensitive`), `companions[]` (`dog`, `kids`), `default_weights`.
- Se guardan **solo en `localStorage`** (con `try/catch`; si falla, en memoria): perfil, acompañantes, pesos, tiempo disponible, distancia máxima, lugar. **Nunca la ubicación.**

### Contenido y textos (prototipo)
- `h2` «Tus preferencias»; botón «Listo».
- «Tiempo disponible» (deslizador; → `duration_min`), «Distancia máxima a pie» (→ `max_distance_m`), «Lugar»: Indiferente / Exterior / Interior (→ `setting`: `any`/`outdoor`/`indoor`).
- «Perfil (opcional)»: General, Persona mayor, Familia con carrito, Sensible a la contaminación (→ `profile`).
- «Salgo con…»: perro, niños (→ `companions`; CLAUDE.md §5 F4; no está en el prototipo).
- «¿A qué le das más importancia?»: Cercanía y rapidez (`proximity`), Sombra y zona verde (`green`), Aire limpio (`air`), Meteorología (`weather`). El contrato tiene un quinto peso, `suitability` (adecuación), que el prototipo no muestra (P-11).
- «Restablecer valores por defecto» → `weights: null`.
- Todos a 0 → la API vuelve a los pesos por defecto con aviso (Foco de revisión n.º 4): mostrar el `warning`.

### Componentes y estados
- **Recálculo al soltar** el deslizador (no en cada movimiento): una sola petición; TanStack Query descarta la respuesta vieja (RF-16).
- Para «dos personas, mismo sitio, distinta respuesta» (guion de la demo), el cambio de perfil tiene que verse al instante en la lista de detrás.

### Accesibilidad
- Hoja/diálogo: Radix Dialog (foco atrapado mientras está abierta, `Esc` cierra, el foco vuelve a «Ajustar»).
- Deslizadores: Radix Slider con `aria-label` y `aria-valuetext` en palabras («45 minutos», «3 km», «Importancia del aire: alta»).
- Lugar y perfil: grupos de `radio` con `fieldset`/`legend`.

### Estado actual
⬜ No existe. «Ajustar» no hace nada (`Home.tsx:59`); «Perfil» del menú apunta a `#perfil` inexistente (`Header.tsx:19`).

### Validar con la maquetadora
- Hoja inferior (móvil) y panel lateral (escritorio) o la misma hoja.
- Escala de los pesos (0–1 continuo o 3–5 niveles con palabras).

---

## 7. Asistente de rutas (F6, Should)

**Ruta propuesta:** `/asistente` · **Requisitos:** RF-20 a RF-24. Plan: D-F1 (domingo). **Primer recorte** si falta tiempo (plan, «Orden de recorte»). Debe funcionar **sin IA** (formulario).

### Datos
1. `POST /api/assistant/interpret` con `InterpretRequest` `{ text }` (3–500 caracteres) → `InterpretResponse`: `params` (`AssistantParams`) **o** `clarification` **o** `rejection`.
2. `POST /api/assistant/route` con `AssistantRouteRequest` `{ origin, params }` → `AssistantRouteResponse`: `route` (`RouteVariant`), `conditions[]` (`condition`, `met`, `detail`), `explanation`, `written_by_ai`.

`AssistantParams` (esquema cerrado): `activity` (`walk` \| `run`), `distance_km` (≤ 42) o `duration_min` (≤ 480), `loop`, `pass_by[]` (`park`, `fountain`, `bench`, `supermarket`, `dog_area`, `playground`), `avoid[]` (`traffic`, `hills`).

### Contenido y textos (PDF de interfaz §6)
Tres bloques siempre visibles:
1. **La petición**, tal como se escribió (campo de texto con ejemplo: «15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado»).
2. **Lo que se ha entendido**: etiquetas editables (actividad, distancia, circular/ida, pasar por, evitar). Es también el **formulario sin IA**: se puede rellenar a mano sin escribir texto.
3. **La ruta propuesta** con comprobación condición por condición: ✓ «Pasa por 2 parques» / ✗ «Ningún banco entre el km 3 y el 5» (`detail`).
- `clarification` → mostrar la pregunta y dejar responder.
- `rejection` → mostrarlo tal cual (fuera de catálogo o consejo médico).
- `written_by_ai: false` → «Explicación generada sin IA» (transparencia).
- Aviso: «La IA interpreta el texto y redacta la respuesta; la ruta la calcula el motor con datos abiertos.»

### Accesibilidad y privacidad
- Las etiquetas son controles reales (casillas, selects), no solo chips.
- Respuesta anunciada en `aria-live="polite"`; cumplido/no cumplido con icono + texto («Cumple», «No cumple»).
- **No se envía la ubicación a `/assistant/interpret`** (solo `text`); la ubicación va únicamente a `/assistant/route`.

### Estado actual
⬜ No existe.

### Validar con la maquetadora
- Cómo se editan las etiquetas en móvil.

---

## 8. Fuentes y aviso

**Ruta propuesta:** `/fuentes` (enlazada desde el pie de **todas** las pantallas) · **Requisitos:** RF-19, CLAUDE.md §2.9 y §2.11, RGPD. Plan: D-F2 (domingo).

### Datos
`GET /api/sources` → `SourcesResponse.sources[]`: `id`, `name`, `publisher`, `license`, `url`, `last_refresh`, `last_failure`.

### Contenido y textos
- `h1` «Fuentes, licencias y aviso».
- Tabla de fuentes: nombre, publicador, licencia (CC BY 4.0 Comunidad y Ayuntamiento; ODbL OpenStreetMap; CC BY 4.0 de Open-Meteo con su atribución «Weather data by Open-Meteo.com» y enlace a https://open-meteo.com/), enlace, «actualizado hace 12 min» (de `last_refresh`), aviso si `last_failure` es posterior a `last_refresh` («última recarga fallida: se muestra el dato anterior»).
- **Aviso médico** completo: «GoMad da recomendaciones orientativas a partir de datos abiertos. No es consejo médico.» + referencia a las recomendaciones oficiales del ICA (BOE-A-2020-10426) y al plan de calor de Sanidad (`umbrales.md`).
- **Privacidad:** sin registro; la ubicación solo se usa para la consulta y no se guarda ni se escribe en los registros; las preferencias se guardan solo en este dispositivo (`localStorage`) y se borran con «Borrar mis preferencias»; al proveedor de IA no se envía la ubicación; fuentes tipográficas e iconos servidos desde nuestro servidor; mapa base (OpenFreeMap en desarrollo; PMTiles propio en la demo).
- Atribución del mapa (© OpenStreetMap) también visible en el propio mapa.
- Licencia de los datos que publiquemos: CC BY.

### Accesibilidad
- Tabla con `caption` y `th scope="col"`; en móvil, lista de tarjetas.

### Estado actual
⬜ No existe. El pie solo dice «Recomendaciones orientativas con datos abiertos (datos de ejemplo). No es consejo médico.» y solo en Inicio (`App.tsx:46-55`).

### Validar con la maquetadora
- Si el aviso médico va también como banda fija en Resultados y Detalle.

---

## 9. Navegación global

| Elemento | Spec | Estado actual |
|---|---|---|
| Barra «Mi entorno · Municipios · Perfil» | arquitectura §5 y PDF de interfaz §2: **barra inferior** en móvil | 🟡 menú hamburguesa desplegable en móvil y barra superior en escritorio (`Header.tsx:43-68`, `main.css:164-215`); enlaces `#hash` sin destino; `aria-current="page"` siempre en el primero (`Header.tsx:63`) |
| Icono del botón de menú | Desaparece con la barra inferior | ⬜ hoy se ve vacío (`Header.tsx:51`, `icons.css:1`); deja de importar al quitar la hamburguesa |
| Logo | `docs/idea/logo_gomad.png` | 🟡 `public/images/logo.png` pesa **516 KB** (lento en móvil; convertir a WebP/SVG o reducir) |
| Título del documento | Cambia con cada pantalla | ⬜ fijo «GoMAD · Muévete cerca» (`index.html:17`); nombre final pendiente (DEC-10) |

### 9.1 Barra de navegación inferior (decidida el 14/10)

Sustituye al menú hamburguesa en móvil. **Pendiente de construir** (ver `pendientes.md`).

- **Destinos:** «Mi entorno» (`/`), «Municipios» (`/municipios`), «Perfil» (`/perfil`). Con router son enlaces reales (`a`/`NavLink`), no anclas `#`. Hasta que haya router, pueden cambiar la vista con el estado actual, pero deben ser `button` si no navegan a una URL.
- **Marcado:** `<nav aria-label="Principal">` con `ul` > `li` > enlace; el activo con `aria-current="page"` **según la pantalla actual** (hoy está fijo en el primero, `Header.tsx:63`).
- **Cada destino: icono + texto visible** (nunca solo icono). Mientras los iconos estén aplazados, solo texto; cuando lleguen, el icono va con `aria-hidden="true"` encima del texto.
- **Tamaño:** cada destino ocupa un tercio del ancho y ≥ 44 px de alto (`--tap-min`); altura de la barra ~56–64 px.
- **Posición:** `position: fixed; bottom: 0` con `padding-bottom: env(safe-area-inset-bottom)` (ya hay `viewport-fit=cover` en `index.html:7`). El contenido (`main` y el pie) necesita `padding-bottom` igual a la altura de la barra para no quedar tapado.
- **Conflicto con la hoja inferior de Resultados** (`Results.tsx:117-189`, `main.css:536-560`, también `bottom: 0`): la hoja debe quedar **encima de la barra** (su `bottom` = altura de la barra) o la barra se oculta en Resultados. A validar con la maquetadora.
- **Activo:** además del color, otra marca visible (negrita, subrayado o fondo), para no depender solo del color; contraste ≥ 3:1 del indicador.
- **Orden de foco:** la barra va en el DOM **después** de `main` (o al final del `body`), para que «Saltar al contenido» y el orden de lectura tengan sentido; o antes de `main` si se acepta el orden de cabecera. Recomendación: después de `main`.
- **Escritorio (≥ 768 px):** la misma `nav` arriba, en la cabecera (como ahora). A validar con la maquetadora.
- **Qué se elimina:** botón hamburguesa y `nav--open` (`Header.tsx:23,43-52`, `main.css:152-181`).

---

## 10. Preguntas abiertas de esta especificación

Se repiten, con contexto, en `app/frontend/docs/guia.md` §6.

| ID | Pregunta | Afecta |
|---|---|---|
| P-01 | El estado del momento de Inicio (temperatura y aire del lugar) no tiene endpoint. ¿Se añade uno al contrato (p. ej. `GET /conditions?lat&lon`), se deriva de la primera hora de `/recommend` o se quita de Inicio? | Inicio |
| P-02 | Veredicto en texto («Muy buena opción», «Buena opción», «Opción aceptable»): ¿lo manda la API o el front lo calcula de `score`? ¿Con qué cortes? | Resultados, Detalle |
| P-03 | Las pastillas de tráfico y los filtros del prototipo no tienen campo en `/recommend` (`Factor` = `proximity`, `suitability`, `green`, `air`, `weather`). ¿Se quitan o se amplía el contrato? | Resultados, Detalle |
| P-04 | ¿Qué hace «Otra» si el catálogo es cerrado? | Inicio |
| P-05 | ¿La recomendación literal del BOE por perfil llega en `explanation`/`reasons` o el front la pinta según `aqi_category` y perfil? (El motor decide, CLAUDE.md §2.4: mejor que llegue de la API) | Detalle |
| P-06 | Ventana horaria por defecto (`window_start`/`window_end`): ¿ahora → +3 h, el resto del día, elegible? | Resultados |
| P-07 | ¿La petición de `/recommend` se guarda en `sessionStorage` (sin ubicación) para sobrevivir a una recarga, o recargar devuelve a Inicio? | Resultados, Detalle |
| P-08 | Desnivel, sombra y «Elegir esta ruta» del prototipo: fuera del contrato. ¿Se quitan? | Ruta |
| P-09 | No hay endpoint con la lista de municipios para el selector. ¿`/location` o lista estática? | Municipio |
| P-10 | `Indicator.category` incluye `social`, que el PDF de interfaz no tiene. ¿Se muestra? | Municipio |
| P-11 | El quinto peso `suitability` no está en el prototipo. ¿Se expone? | Perfil |

---

## Decisiones tomadas al construir (15/10)

Paso 1 del front (rama `front/jue15-todas-pantallas`): todas las pantallas con datos de ejemplo y la forma exacta del contrato, sin red. Cada línea: `Front: Ruling: <qué> — <por qué> — <coste si me equivoco>`. El equipo puede cambiar cualquiera.

### Preguntas abiertas (§10)
- Front: Ruling: **P-01** `h1` neutro «¿Qué te apetece hacer hoy?»; el estado del momento son las pastillas de municipio, temperatura y aire de la **primera hora** (`hours[0]`) del primer resultado de `/recommend` (`activity: null`, `limit: 1`), solo si hay ubicación — no hay endpoint de condiciones y el `h1` fijo contradecía a Carmen — una petición más a `/recommend` en Inicio; si se crea `/conditions`, solo cambia `MomentChips` en `Home.tsx`.
- Front: Ruling: **P-02** el veredicto lo calcula el front: ≥ 8 «Muy buena opción», ≥ 6,5 «Buena opción», resto «Opción aceptable» (`VERDICT_THRESHOLDS` en `src/lib/labels.ts`, criterio propio) — el contrato no lo trae — si Motor lo manda, se cambia `verdictFor` y nada más.
- Front: Ruling: **P-03** fuera la barra de filtros y las pastillas de tráfico en Resultados y Detalle; queda un botón «Ajustar» que abre las preferencias. Pastillas de cada tarjeta: temperatura ahora, aire (ICA) y verde (factor `green`). En el Detalle, la tercera tesela «Tráfico» pasa a «Lluvia» (`precip_prob`) — `/recommend` no devuelve tráfico; el tráfico está en Ruta — si se amplía el contrato, hay que volver a añadirlas.
- Front: Ruling: **P-04** sin «Otra»: se muestran las 8 actividades del catálogo (`activities.yaml`) — catálogo cerrado (RF-02) — ninguno.
- Front: Ruling: **P-05** la recomendación literal del BOE solo se pinta si llega de la API en `reasons`/`explanation` (el Detalle muestra los `reasons` de ahora y de la mejor hora); los datos de ejemplo la ponen en `reasons` con el prefijo «Recomendación oficial (BOE):» — el motor decide (CLAUDE.md §2.4) — si Motor no la manda, no aparece.
- Front: Ruling: **P-06** ventana por defecto ahora → +3 h, editable de 1 a 12 h con el deslizador «Ventana horaria» de Preferencias — propuesta del encargo — si el motor necesita el resto del día, solo cambia `DEFAULT_PREFERENCES.windowHours`.
- Front: Ruling: **P-07** sin persistencia: `/resultados`, `/resultados/:id` y `/ruta/:id` sin estado en memoria vuelven a Inicio con el aviso «Elige una actividad para ver recomendaciones: los resultados no se guardan al recargar la página.» — más simple y sin guardar nada (Q-09) — quien recargue pierde la lista.
- Front: Ruling: **P-08** fuera sombra y «Elegir esta ruta»; desnivel siempre «sin datos de desnivel» — no están en `RouteVariant` (DEC-12 llega el sábado) — cuando el contrato traiga el desnivel, añadirlo en `RouteView.tsx`.
- Front: Ruling: **P-09** lista de los 179 municipios generada de `Comun:IDEM_V_MUNICIPIOS` (`app/data/raw/municipios/municipios.geojson`, CC BY 4.0) con centro aproximado (media de los vértices del contorno, reproyectado a EPSG:4326) en `src/data/mock/municipalities.ts`, servida por `listMunicipalities()` — no hay endpoint — en el paso 3 hay que decidir si la da la API o se queda estática; el centro de Madrid capital sale desplazado al norte (media de vértices).
- Front: Ruling: **P-10** `social` se muestra como «Servicios sociales», la última categoría — está en el contrato — ninguno.
- Front: Ruling: **P-11** `suitability` se expone como «Importancia de adecuación a la actividad», el último de los cinco pesos — está en el contrato y el encargo lo pide — un peso más que entender.

### Desviaciones de pantallas.md, guia.md y pendientes.md
- Front: Ruling: preferencias **solo en memoria** (contexto de React), no en `localStorage` como dice §6 — instrucción del paso 1 — se pierden al recargar; en el paso 3 se puede añadir `localStorage` con `try/catch`, nunca con la ubicación.
- Front: Ruling: tipos generados en `src/api/schema.d.ts` (no `types.ts` como dice guia §4.2) y alias legibles en `src/api/types.ts`; script `npm run contract` — instrucción del encargo — ninguno.
- Front: Ruling: un solo `<nav aria-label="Principal">` dentro de la cabecera, fijo abajo en móvil y arriba en ≥ 768 px; en el DOM va antes de `main` (§9.1 recomendaba después) — evita duplicar la navegación; el skip link la salta — orden de foco cabecera → navegación → contenido.
- Front: Ruling: la hoja inferior de Resultados queda **encima** de la barra (la pantalla ya resta su altura) y se despliega sola al recibir el foco — sin enlaces enfocables fuera de la vista — ninguno.
- Front: Ruling: en el Detalle se quita el botón «Cerrar» (duplicaba «Volver a resultados») y la imagen decorativa lleva `aria-hidden` — menos ruido — ninguno.
- Front: Ruling: «Sorpréndeme» (RF-03): `Recommendation` no dice qué actividad propone; los 3 resultados son de **tipos de destino distintos** (`destination.type`) y la explicación lo cuenta — no hay campo de actividad por resultado — si Motor quiere enseñar la actividad, hace falta un campo nuevo en el contrato.
- Front: Ruling: `RouteVariant.geometry` es `{"type": "object"}` sin propiedades en `openapi.json`, que `openapi-typescript` convierte en `Record<string, never>`; se lee y se construye con `src/lib/geometry.ts` (comprueba que sea un `LineString`) — no se toca el contrato — **petición a Motor:** tipar `geometry` como GeoJSON `LineString` (`type` + `coordinates`).
- Front: Ruling: el motivo de un indicador «Sin datos» se toma de `source.label` (p. ej. «EIEL 2023 · no cubre este municipio»), porque `Indicator` no tiene campo de motivo — sin cambiar el contrato — si la API no pone el motivo en la etiqueta, solo se verá «Sin datos».
- Front: Ruling: rangos de la interfaz más cortos que el contrato: tiempo 10–180 min (contrato 10–480), distancia 0,5–10 km (contrato 0,2–50 km); pesos en % de 0 a 100 de 5 en 5 con palabras (ninguna, baja, media, alta, máxima; criterio propio) — deslizadores usables en móvil — quien quiera más, no puede desde la interfaz.
- Front: Ruling: «Usar mi ubicación» usa una **ubicación de ejemplo** en Getafe y lo dice; sin geolocalización real hasta el paso 3 — encargo — ninguno.
- Front: Ruling: escenarios de la demo (Carmen, Lucía, Dani, Ana, familia y «día normal» para «dos personas, mismo sitio») en un selector «Datos de ejemplo» al final de Fuentes (`src/data/scenarios.ts`); en el paso 3 se borran el módulo y el selector — discreto y sin tocar las pantallas — ninguno.
- Front: Ruling: textos del asistente sin decir «IA generativa»: «El asistente solo interpreta tu texto y redacta la respuesta con los resultados del motor» — DEC-03: OCI Language + reglas, sin LLM — si se añade un LLM, cambiar el texto.
- Front: Ruling: en el asistente, distancia **o** duración: si hay distancia, manda la distancia y `duration_min: null` — el esquema admite ambos y el motor espera uno — ninguno.
- Front: Ruling: todo el texto de contenido a ≥ 14 px (antes había 11–13 px), asa de la hoja con `--muted` (≥ 3:1) y filtros a 44 px — checklist §5 — algo más de altura en las tarjetas.
- Front: Ruling: en escritorio el `h1` de Resultados estaba oculto (`display: none`) y había un contador fijo «536 resultados» en CSS; ahora el `h1` se ve y el contador se quita — un `h1` visible por pantalla — ninguno.
- Front: Ruling: **logo** sigue en PNG de 516 KB (con `width`/`height` y `alt=""`, el enlace lleva `aria-label`) — no hay herramienta local para WebP (ni `cwebp`, ni `sharp`, ni ImageMagick, ni Pillow) — primera carga más lenta en móvil; queda en `pendientes.md`.
- Front: Ruling: iconos aplazados: componente `Icon` que pinta `<span class="icon" aria-hidden="true" data-icon="…">` vacío (oculto con `.icon:empty`), ya colocado en pastillas, actividades y categorías — decisión del equipo — al llegar la fuente, solo cambian `Icon.tsx` e `icons.css`.
- Front: Ruling: el mapa es `MapView`, un SVG de marcador de posición sin teselas con la interfaz final (`markers`, `selectedId`, `origin`, `route`, `secondaryRoute`), oculto a lectores (la lista y la descripción son el equivalente) — sin red en el paso 1 — en el paso 3 falta la sincronización tarjeta ↔ marcador.
- Front: Ruling: los datos de ejemplo usan un umbral de calor de 33 °C de criterio propio (solo en `src/data/mock/recommend.ts`) — DEC-06 sigue pendiente — ninguno en producción: lo decide el motor.
- Front: Ruling: el estado de error se prueba espiando las funciones de `src/data` (`vi.spyOn`) — sin MSW en el paso 1 — en el paso 3 se pueden pasar a MSW.

### Conexión a la API (paso 3 parcial, 16/10, rama `motor/vie16-api-conexion`)
- Front: Ruling: `getActivities`, `recommend`, `getRoute` y `searchLocation` llaman a la API con `src/data/http.ts` (base `/api`, 15 s de tiempo límite, `ApiError`); en `MODE=test` usan los datos de ejemplo (`sampleDataMode()`), así las pruebas no tocan la red — encargo — una prueba de pantalla no detecta un cambio de forma de la API (lo cubre el contrato).
- Front: Ruling: «Usar mi ubicación» toma el municipio por **punto en polígono** con `src/data/municipalityShapes.json` (contornos simplificados ~50 m, 217 KB, carga diferida al pulsar; `scripts/municipality_shapes.py`) — con los centros aproximados de P-09 el centro de Getafe salía Leganés — a menos de ~50 m de un límite puede salir el vecino o «fuera de la Comunidad».
- Front: Ruling: la ubicación de ejemplo solo en pruebas y como respaldo del GPS en desarrollo (`import.meta.env.DEV`), con su aviso; en producción, mensaje de error y se escribe la dirección — encargo — ninguno.
- Front: Ruling: fuera el selector de escenarios de Fuentes (la recomendación ya es real); `scenarios.ts` y `mock/` se quedan para las pruebas; la tabla de Fuentes dice «Lista de ejemplo» hasta S-D1 — ninguno.

### Versiones
- Front: Ruling: instaladas `react-router` 7.18.4, `@radix-ui/react-dialog` 1.3.1, `@radix-ui/react-slider` 1.6.1; dev `vitest` 4.1.12, `jsdom` 26.1.0, `@testing-library/react` 16.3.3, `@testing-library/dom` 10.4.2, `@testing-library/jest-dom` 6.9.1, `@testing-library/user-event` 14.6.8, `vitest-axe` 0.1.0 — las de guia §2.1 — ninguno.
- Front: Ruling: npm 10.8.2 (Node 20.20.2) falla al instalar `vitest` con «Cannot read properties of null (reading 'edgesOut')» (fallo de arborist); se instaló con `npx npm@11 install` — mismo `lockfileVersion` 3 — si `npm ci` del Dockerfile (paso 2) se queja, regenerar el lock con su versión de npm.
- Front: Ruling: `vitest-axe` se usa llamando a `axe()` y comprobando `violations` (sin sus *matchers*), con la regla `color-contrast` desactivada porque jsdom no mide colores — el contraste se revisa a mano (§0.1) — un fallo de contraste no lo detectan las pruebas.

### Revisión final (15/10)
- Front: Ruling: de la revisión de código y de `a11y-architect` se aplicaron todos los Critical e Important con su prueba (captura del puntero en la hoja, texto de privacidad del asistente, errores de «Ver más», «Buscar actividad en» y «Ver este ejemplo», foco y anuncios, tablas, objetivos de 44 px, barra fija que tapaba el foco, reflow). Los Minor y las comprobaciones que jsdom no puede hacer quedan en `pendientes.md` §B2 — plazo — hay que probar en móvil real antes de la demo.

### Correcciones de la verificación (15/10)
- Front: Ruling: la pastilla de verde de Resultados muestra `factor.text` de la API y tono neutro (`info`), sin semáforo — así el front no pone cortes sobre `value` (solo se admite el de P-02) — si se quiere color, la API tendría que mandar el tono o se añade una constante marcada criterio propio.
- Front: Ruling: sin `/activities` no se pintan los 5 pesos («Cargando pesos…» o error con «Reintentar»); el resto del formulario sigue usable — así nunca se envían pesos que no vienen del motor — si `/activities` cae en la demo, no se pueden mover los pesos hasta que vuelva.
- Front: Ruling: al recalcular no se atenúa la lista; se avisa con «Actualizando…» (`--blue-tint` + `--navy`) y `aria-busy` — contraste intacto — ninguno.
- Front: Ruling: reflow a 320 px solo con CSS (pastillas `white-space: normal` dentro de la tarjeta y nota debajo del título por debajo de 400 px); sin prueba automática porque jsdom no maqueta — pendiente comprobar en navegador (`pendientes.md` B2) — si no basta, se ajusta tras verlo.
- Front: Ruling: `aria-current="page"` solo en la ruta exacta del enlace y `"true"` en sus subpantallas, con la misma marca visual (`.nav__link[aria-current]`) — ninguno.
- Front: Ruling: `--border-strong: #7a8c9e` (3,46:1 sobre `--surface`, 3,21:1 sobre `--bg`, medido) en los bordes de `.option`, `.seg`, `.candidate` y `.button--quiet`; el resto de bordes decorativos sigue con `--border` — ninguno.
- Front: Ruling: botón con `aria-disabled="true"`: `--nodata-bg` de fondo, `--muted` de texto y `cursor: not-allowed`, sin opacidad — el texto mantiene ≥ 4,5:1 — ninguno.
- Front: Ruling: las pruebas de estilo (`src/styles/styles.test.ts`) leen `main.css` del disco con `node:fs` porque Vitest entrega vacío el CSS importado con `?raw`; usan `@types/node`, que ya venía en el proyecto — ninguno.
- Front: Ruling: `role="list"` en todas las `ul`/`ol` de los componentes, porque `main.css` quita `list-style` a todas — VoiceOver — ninguno.
- Front: Ruling: en Resultados vacío o con 422 hay dos botones «Ajustar preferencias» (cabecera y aviso) que abren lo mismo — mismo nombre, misma acción — ninguno.
- Front: Ruling: la comprobación `grep -rn "FALLBACK_WEIGHTS\|>= 7" src --include=*.tsx` no sale vacía: encaja con el punto de corte `>= 768` de `Results.tsx` y de un comentario de `Header.tsx`; no son cortes del motor — ninguno.

### Despliegue del front (paso 2)
- Deploy: Ruling: imagen de Node fijada a `node:22.23.3-alpine` (no `node:22-alpine` como en guia §3 paso 0 punto 7) — la última de la rama 22 con más de dos semanas (23/09/2026), build reproducible — las correcciones de Node 22 hay que subirlas a mano.
- Deploy: Ruling: `npm ci` con el npm de la imagen (10.9.9), sin npm 11 y sin tocar el `package-lock.json` — el fallo de arborist era de npm 10.8.2 en local; en la imagen `npm ci` instala 159 paquetes sin error — si un lock futuro lo rompe, cambiar a `RUN npx -y npm@11 ci`.
- Deploy: Ruling: el `.dockerignore` **no** excluye las pruebas (`*.test.*`, `setupTests.ts`) — `tsc -b` del build comprueba los tipos de todo `src`, pruebas incluidas, y eso sirve de red; solo viven en la etapa de build, la imagen final solo lleva `dist` — ~1 s más de build.
- Deploy: Ruling: el `.dockerignore` además deja fuera `dist-ssr/`, `*.local`, `*.log`, `coverage/`, `.vscode/`, `.idea/`, `.DS_Store`, `Dockerfile`, `.dockerignore` y `README.md` — nada de eso hace falta para compilar — si algún día el build necesita uno, falla en `docker build` y se ve enseguida.
- Deploy: Ruling: no se toca `app/deploy/docker-compose.yml` ni el `Caddyfile` — no hacía falta — ninguno.
- Deploy: Ruling: `deploy.sh` admite `--no-pull`, `GOMAD_URL` (por defecto `http://localhost`, para el HTTPS con dominio) y `GOMAD_WAIT_S` (90 s); da por buena la portada solo si referencia `/assets/index-` (así distingue la SPA de la página de prueba) — ninguno; con dominio, `GOMAD_URL=https://<dominio>`.
- Deploy: Ruling: `deploy.sh` reconstruye también la `api` (`up -d --build` de todo el Compose) — un despliegue = el commit entero — el primer build de la api en la VM tarda ~1 min (pip).
- Deploy: Ruling: `deploy.sh` separa `fail` (configuración, docker, `git pull`: sin pista) de `fail_compose` (desde `docker compose up`: con `ps`/`logs`) y guarda las respuestas de `curl` en variables antes del `grep` — verificación del paso 2 — ninguno.
- Deploy: Ruling: el primer despliegue es `git pull --ff-only` a mano + `deploy.sh --no-pull` — antes del primer pull la VM no tiene el guion — ninguno; los siguientes, `deploy.sh` a secas.
