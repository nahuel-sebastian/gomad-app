# Informe de perfil de datos — GoMad

**Generado:** 14/10/2026, de madrugada, sobre `data/raw/` (descarga del 14/10/2026 02:08, 46 fuentes, 222 MB).
**Herramienta:** `scripts/profile_sources.py` (solo stdlib; se vuelve a ejecutar en ~5 s). Detalle completo por columna: `data/perfil/perfil.json` (no se sube: está en `data/`).
**Referencia de municipios:** los 179 de `municipios.geojson` (`CDMUNICIPIO` → INE `28` + 3 dígitos).

> Lo que este informe **confirma** del CLAUDE.md va marcado ✔; lo que lo **corrige o añade**, ⚠. Las correcciones al CLAUDE.md no se han aplicado: están listadas en `docs/PENDIENTES.md`.

---

## 1. Resumen por fuente

Cobertura = municipios distintos reconocidos sobre 179. «Vía» = cómo se identificó el municipio (código INE o nombre).

| Fuente | Filas | Cobertura | Columna (vía) | Codificación | Coordenadas | Notas |
|---|---:|---:|---|---|---|---|
| `municipios` | 179 | 179 | `CDMUNICIPIO` (código) | — | 25830 | Referencia |
| **Deporte** | | | | | | |
| `nmc_deporte` | 1.358 | **178** | `CMUN` | UTF-8 | 25830 `UTM_X/Y` | Falta **Patones**. ✔ capital 596, Getafe 19 |
| `nmc_deporteotros` | 87 | 54 | `CMUN` | UTF-8 | 25830 | Tiro, hípica, aeródromos… |
| `eiel_deporte` | 726 | **155** | `MUN` | — | 25830 | ✔ Getafe **0** (no está en EIEL) |
| `ay_polideportivos` | 82 | capital | — | **cp1252** | 4326 `LATITUD/LONGITUD` | |
| `ay_idb` | 607 | capital | — | **cp1252** | 4326 | 1 punto fuera de Madrid |
| `ay_piscinas` | 56 | capital | — | **cp1252** | 4326 | |
| **Verde y naturaleza** | | | | | | |
| `vpla_redes` | 37.167 | **166** | `CD_MUNICIPIO` | — | 25830 | ✔ 13 ausentes (ver §3) |
| `eiel_parques` | 2.100 | 155 | `MUN` | — | 25830 | |
| `nmc_parques` | **845** | 62 | `CMUN` | UTF-8 | 25830 | ⚠ CLAUDE.md dice 780. ⚠ `.prj` erróneo (ver §2) |
| `ay_parques` | 208 | capital | — | **cp1252** | 4326 | 5 sin coordenadas |
| `areas_recreativas` | 84 | 51 | `DS_MUNI` (nombre) | — | 25830 | 6 con nombre de municipio no reconocido |
| `sendas` | 224 | — | sin campo de municipio | — | 25830 | Habría que cruzar por geometría |
| `vias_pecuarias` | 1.694 | 169 | `CD_MUNI` | — | 25830 | 48 tramos sin municipio |
| `zonas_bano` | **5** | 4 | nombre | UTF-8 BOM | 25830 | Solo 5 zonas; una «Insuficiente» en 2025 |
| **Aire** | | | | | | |
| `aire_estaciones` | 28 | 26 | nombre | UTF-8 BOM | 4326 y 25830 | ⚠ coma decimal en lat/lon (23) y UTM (28) |
| `aire_dia` | 180 | 28 | `municipio` (código sin ceros: `6`, `16`) | UTF-8 BOM | — | ⚠ ver §2 (bandera `T`, día anterior) |
| `aire_zonas` | 179 | 178 | nombre | UTF-8 BOM | — | ⚠ **solo nombres**, sin código INE |
| `zonas_aire` | 180 | — | — | — | 25830 | Polígonos |
| `estaciones_aire_idem` | 48 | 10 | nombre | — | 4326/25830 | Coma decimal en lat/lon (23) |
| `ay_aire` | 126 | capital | `MUNICIPIO`=079 | UTF-8 BOM | — | Bandera `V`; a las 02:08 ya traía el día 14 |
| `ay_aire_estaciones` | 24 | capital | — | UTF-8 BOM | 4326 | |
| `ay_meteo` | 68 | capital | `MUNICIPIO`=079 | UTF-8 BOM | — | |
| **Servicios** | | | | | | |
| `sanitarios` | 45.978 | 179 | `municipio_nombre` | UTF-8 BOM | 25830 | ✔ una fila por servicio: 15.879 centros; **429** centros de salud + consultorios. 20 puntos fuera de Madrid |
| `farmacias` | 2.956 | 160 | `MUNICIPIO_NOMBRE` | UTF-8 BOM | 25830 | ⚠ coma decimal en 2.760 coordenadas |
| `educativos` | 7.757 | 170 | `CDMUNI` | UTF-8 BOM | 25830 | ✔ ALTA 3.906 (BAJA 3.552). De ALTA, 55 sin coordenadas |
| `atencion_social` | 2.648 | 137 | `municipio_codigo` | UTF-8 BOM | 25830 | ⚠ 177 filas con municipio «RESERVADO» |
| `desfibriladores` | 12.941 | 161 | `municipio_codigo` | UTF-8 BOM | 4326 y 25830 | ⚠ lat/lon con **coma decimal en todas**; 9,3 % sin municipio (usar coordenadas) |
| `eiel_sanitario` / `_ensenanza` / `_cultural` / `_nucleos` | 194 / 636 / 659 / 467 | 154 / 135 / 153 / 155 | `MUN` | — | 25830 | |
| `nmc_bibliotecas` | **16** | **1** | `CMUN`=079 | UTF-8 | 25830 | ⚠ solo las 16 bibliotecas públicas de la **red regional en la capital** |
| **Movilidad y comercio** | | | | | | |
| `nmc_busparadas` | 15.037 | 179 | `CMUN` | UTF-8 | 25830 | ⚠ 62 puntos fuera de Madrid, 10 con coordenadas 0 |
| `nmc_estmetro` / `nmc_estcerca` | 297 / 93 | 15 / 34 | `CMUN` | UTF-8 | 25830 | |
| `nmc_hipermercados` / `galimentacion` / `mercadoabastos` | 54 / 141 / 62 | 24 / 27 / 11 | `CMUN` | UTF-8 | 25830 | ⚠ `hipermercados` **sin `.prj`** |
| **Mobiliario capital** | | | | | | |
| `ay_bancos` | 76.640 | capital | — | UTF-8 BOM | ⚠ ver §2 | Todos «OPERATIVO» |
| `ay_fuentes` | 2.270 | capital | — | UTF-8 BOM | 4326 y 25830 completas | |
| `ay_areas_caninas` | 112 | capital | — | UTF-8 BOM | ⚠ ver §2 | |
| `ay_trafico` (`pm.xml`) | 4.897 puntos | capital | — | — | 25830 `st_x/st_y` | ⚠ coma decimal en todos. Instantánea 14/10/2026 02:00 |
| **Estadística** | | | | | | |
| `padron` / `densidad` / `renta` | 18.718 / 7.640 / 5.157 | 179 | `Territorio` (nombre) | **cp1252** | — | ✔ cp1252. ⚠ mezclan municipios, zonas estadísticas y total regional: filtrar `Tipo territorio = Municipios` |

**No descargadas** (marcadas PESADAS en el script, no hacen falta aún): `viales`, `cubierta_terrestre`, `aire_historico`.

---

## 2. Trampas nuevas (no estaban en el CLAUDE.md §8)

1. **Bancos y áreas caninas del Ayuntamiento casi sin lat/lon.** `ay_bancos`: solo 3.733 de 76.640 filas tienen `LATITUD/LONGITUD`, pero 76.627 tienen `COORD_GIS_X/Y` (EPSG:25830). `ay_areas_caninas`: lat/lon en 2 de 112, UTM en las 112. → **Usar `COORD_GIS_X/Y` y reproyectar**, no `LATITUD/LONGITUD`. El CLAUDE.md dice «Incluye LATITUD/LONGITUD» para el Ayuntamiento: no es cierto en estas capas.
2. **`.prj` erróneo en Nomecalles `parques`:** declara `GEOGCS["GCS_ETRS_1989"]` (geográficas), pero los valores son UTM (x 380.883–480.160). `hipermercados` **no trae `.prj`**. → Forzar EPSG:25830 en todas las capas de Nomecalles, sin fiarse del `.prj`.
3. **Bandera de validación del aire regional: también existe `T`.** En `aire_dia` las columnas `v01…v24` valen `T`/`N`. Según la [descripción oficial del fichero](https://datos.comunidad.madrid/dataset/3dacd589-ecca-485c-81b9-a61606b7199f/resource/8336936d-6ef7-419e-ad6e-e5e86216bb92/download/descripcion-fichero-datos-de-contaminantes-v2.pdf), `T` = «dato temporal pendiente de la validación por parte de los técnicos de la Consejería»; luego pasa a `V` (válido) o `N` (no válido). El CLAUDE.md solo menciona `V`/`N`. `ay_aire` (Ayuntamiento) trae `V`. → En tiempo real, aceptar `T` y `V`; descartar `N`.
4. **`aire_dia` descargado a las 02:08 del 14/10 contiene el día 13/10** (horas 1–23 con dato, h24 vacía). A primera hora el fichero «del día» es el de ayer. → La ingesta horaria debe leer `ano/mes/dia` de cada fila, no suponer «hoy».
5. **Código de municipio sin ceros a la izquierda** en `aire_dia` (`6`, `16`, `171`) y de 3 dígitos en casi todas las fuentes (`079`). Siempre normalizar a `28` + 3 dígitos.
6. **`aire_zonas` solo trae nombres de municipio en mayúsculas**, sin código. Hay que unirlo por nombre normalizado; «Horcajo de la Sierra-Aoslos» no casa: en el CSV aparece como «HORCAJO DE LA SIERRA».
7. **Más comas decimales de las esperadas:** `farmacias` (2.760 de 2.952), `desfibriladores` lat/lon (todas), `aire_estaciones` (todas), `estaciones_aire_idem` (23), `pm.xml` (todas).
8. **`atencion_social`:** 177 filas con municipio, calle y código postal «RESERVADO» (centros protegidos). No se pueden situar: excluirlas del mapa y contarlas aparte.
9. **Coordenadas fuera de la Comunidad:** 62 paradas de bus (y 10 con 0,0), 20 servicios sanitarios, 1 instalación del Ayuntamiento. → Filtro de caja/polígono en la ingesta.
10. **`nmc_bibliotecas` no sirve para RF-09** (alternativa cubierta) fuera de la capital: son 16 bibliotecas de la red regional, todas en Madrid. Para el resto de municipios: EIEL `cultural` (columna `BIBLIOTECA`, 153 municipios).
11. **Nomecalles `deporte`: la columna `CATEGORIA` no da el deporte** (un solo valor, «INSTALACION DEPORTIVA»). Sí hay `URL` hacia `escorpio.csd.gob.es` (Censo Nacional de Instalaciones Deportivas del CSD) en parte de las filas y `DS_REVISAR=true` en 179. ✔ Se confirma que hay que deducir el deporte del nombre (§6.5).
12. **Padrón, densidad y renta mezclan tipos de territorio** (municipios, zonas estadísticas, Comunidad): filtrar por `Tipo territorio`.

## 3. Cifras del CLAUDE.md comprobadas

| Afirmación | Resultado |
|---|---|
| EIEL deporte: 726 filas, 155 municipios | ✔ |
| 25 instalaciones `ESTADO = MALO`, 77 `SIN ACCESO` en silla | ✔ (BUENO 589, REGULAR 104, EN EJECUCIÓN 8) |
| Columna `NATACION` vacía | ✔ 0 filas con valor |
| Columnas por deporte: `PADEL` 154, `TENIS` 164, `FUTBOL` 322, `BALONCESTO` 330, `ATLETISMO` 22, `GIMNASIA` 242 | ✔ exactas |
| Piscinas por `TIPOINSTAL` | 35 «PISCINAS AL AIRE LIBRE» + 10 «PISCINAS CUBIERTAS» |
| VPLA: 37.167 polígonos, 166 municipios, 16.867 zonas verdes (en 162 municipios: El Atazar, Cervera de Buitrago, Gargantilla del Lozoya y Tielmes no tienen ninguna), 738 «Deportivos» | ✔ |
| VPLA: faltan 13 | ✔ Boadilla del Monte, Brunete, Ciempozuelos, Guadarrama, **Madrid**, Pinto, Pozuelo de Alarcón, Rivas-Vaciamadrid, Las Rozas de Madrid, Sevilla la Nueva, Torrelodones, Villanueva de la Cañada, Villanueva del Pardillo |
| Getafe en VPLA: 172,8 m² de zona verde/hab | Coherente: 648 polígonos verdes, 33,39 M m² (falta dividir por el padrón) |
| Nomecalles por nombre: polideportivo 190, piscina 40, pádel 57, tenis 29, campo de fútbol 48 | ✔ salvo campo de fútbol: **50**. Otros: pabellón 38, frontón 17, skate 8, atletismo 2 |
| Nomecalles `parques` 780 | ⚠ **845** filas (779 nombres distintos) |
| Educativos: 3.552 de baja | ✔ |

## 4. Implicaciones para la ingesta (resumen accionable)

- Reproyectar todo a EPSG:4326 desde 25830, ignorando los `.prj` de Nomecalles.
- Normalizar números: coma → punto en todas las coordenadas.
- Leer en cp1252: `padron`, `densidad`, `renta`, `ay_idb`, `ay_parques`, `ay_piscinas`, `ay_polideportivos`.
- Municipio: código INE de 5 dígitos; si solo hay nombre, unión por nombre normalizado (sin tildes, artículos «(La)»/«, El» reordenados) contra `municipios.geojson`.
- Filtrar puntos fuera de la Comunidad y coordenadas a 0.
- Ayuntamiento: `COORD_GIS_X/Y` en bancos y áreas caninas.
- Aire: fecha por fila; aceptar `T` y `V`, descartar `N`; códigos de magnitud y estación según la descripción oficial (ver `docs/assets/umbrales.md`).
