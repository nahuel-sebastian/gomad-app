# Umbrales oficiales para el motor de reglas

Regla del proyecto (CLAUDE.md §2.9 y §6.2): los umbrales se **copian de la fuente oficial, no de memoria**, y se citan en la app. Este documento recoge solo lo verificado contra la fuente primaria. Lo que falta está en `docs/PENDIENTES.md`.

---

## 1. Calidad del aire — Índice Nacional de Calidad del Aire (ICA)

**Estado: ✅ verificado contra el BOE** (14/10/2026).

**Norma vigente:**
- Orden TEC/351/2019, de 18 de marzo, por la que se aprueba el Índice Nacional de Calidad del Aire (BOE núm. 75, 28/03/2019, [BOE-A-2019-4494](https://www.boe.es/eli/es/o/2019/03/18/tec351)).
- **Anexo sustituido por** la Resolución de 2 de septiembre de 2020, de la Dirección General de Calidad y Evaluación Ambiental (BOE núm. 242, 10/09/2020, págs. 75835–75838, [BOE-A-2020-10426](https://www.boe.es/diario_boe/txt.php?id=BOE-A-2020-10426)). **Esta es la tabla que vale.** La de 2019 (5 niveles, «muy bueno… muy malo») está derogada: no usarla.
- Tabla de bandas copiada de la imagen oficial del BOE: <https://www.boe.es/datos/imagenes/disp/2020/242/10426_5606.png>.
- Recomendaciones copiadas de: <https://www.boe.es/datos/imagenes/disp/2020/242/10426_5740.png>.
- Página divulgativa de MITECO (colores): <https://www.miteco.gob.es/es/calidad-y-evaluacion-ambiental/temas/atmosfera-y-calidad-del-aire/visualizacion-datos-calidad-del-aire/ica.html>. ⚠ La URL del CLAUDE.md (`…/calidad-del-aire/ica.html`) da **404**.

### 1.1 Bandas de concentración (µg/m³)

| Categoría | NO₂ | O₃ | PM10 | PM2,5 | SO₂ |
|---|---|---|---|---|---|
| Buena | 0–40 | 0–50 | 0–20 | 0–10 | 0–100 |
| Razonablemente buena | 41–90 | 51–100 | 21–40 | 11–20 | 101–200 |
| Regular | 91–120 | 101–130 | 41–50 | 21–25 | 201–350 |
| Desfavorable | 121–230 | 131–240 | 51–100 | 26–50 | 351–500 |
| Muy desfavorable | 231–340 | 241–380 | 101–150 | 51–75 | 501–750 |
| Extremadamente desfavorable | 341–1000 | 381–800 | 151–1200 | 76–800 | 751–1250 |

### 1.2 Periodo de cálculo (texto de la Resolución de 2020)

| Contaminante | Valor que se compara con la tabla |
|---|---|
| NO₂, SO₂ | Media de la última hora |
| O₃ | **Media móvil de las últimas 8 horas** |
| PM10, PM2,5 | **Media móvil de las últimas 24 horas** |

- **Índice global = la peor categoría** de los contaminantes disponibles (basta con uno).
- Concentraciones por encima del máximo de «extremadamente desfavorable» se descartan como erróneas.
- Si un contaminante no tiene valores medidos a esa hora en 3 de los 4 días anteriores → «sin datos».
- MITECO rellena huecos con el modelo CAMS (Copernicus). **Nosotros no**: sin dato → «sin datos» + estación de la zona (CLAUDE.md §7.3).
- **Implicación para la ingesta:** con los ficheros horarios (`h01…h24`) hay que calcular las medias móviles de 8 h (O₃) y 24 h (PM). Una hora suelta de O₃ **no** es el ICA.
- Códigos de magnitud (✅ verificado en la [descripción oficial del fichero](https://datos.comunidad.madrid/dataset/3dacd589-ecca-485c-81b9-a61606b7199f/resource/8336936d-6ef7-419e-ad6e-e5e86216bb92/download/descripcion-fichero-datos-de-contaminantes-v2.pdf), tabla 3): **1 = SO₂**, 8 = NO₂, 9 = PM2,5, 10 = PM10, 14 = O₃, todos en µg/m³. Otros que vienen en el fichero y **no** entran en el ICA: 6 CO (mg/m³), 7 NO, 11 PM1, 12 NOx, 20 tolueno, 22 black carbon, 30 benceno, 42/44 hidrocarburos (mg/m³), 431 metaparaxileno.
- Validación (misma fuente): **`T` = dato temporal pendiente de validación**, `V` = válido, `N` = no válido. Para tiempo real hay que aceptar `T` (si no, no habría datos del día).

### 1.3 Colores oficiales (MITECO, RGB)

| Categoría | Color | RGB |
|---|---|---|
| Buena | azul | 56, 162, 206 |
| Razonablemente buena | verde | 50, 161, 94 |
| Regular | amarillo | 241, 229, 73 |
| Desfavorable | rojo | 200, 52, 65 |
| Muy desfavorable | granate | 110, 22, 29 |
| Extremadamente desfavorable | morado | 162, 91, 164 |
| Sin datos | gris oscuro | 85, 89, 93 |

> Accesibilidad (CLAUDE.md §2.10): el color nunca va solo; siempre icono + texto de la categoría. Algunos pares (amarillo sobre blanco, granate y morado) no llegan al contraste 4,5:1 para texto: usarlos como fondo de una pastilla con texto oscuro o claro según el caso, o solo como acento. Lo revisará `a11y-architect`.

### 1.4 Recomendaciones para la salud (literales del BOE)

| Categoría | Mensaje para la salud | Grupos de riesgo y personas sensibles | Población general |
|---|---|---|---|
| Buena | Calidad del aire satisfactoria | Disfruta de tus actividades al aire libre de manera normal. | Disfruta de tus actividades al aire libre de manera normal. |
| Razonablemente buena | Calidad del aire aceptable, la contaminación no supone un riesgo para la salud. | Disfruta de tus actividades al aire libre de manera normal. | Disfruta de tus actividades al aire libre de manera normal. |
| Regular | La calidad del aire probablemente no afecte a la población general pero puede presentar un riesgo moderado para los grupos de riesgo. | Considera reducir las actividades prolongadas y enérgicas al aire libre. Las personas con asma o enfermedades respiratorias deben seguir cuidadosamente su plan de medicación. Las personas con problemas del corazón pueden experimentar palpitaciones, dificultad en la respiración o fatiga inusual. | Disfruta de tus actividades al aire libre de manera normal. Sin embargo, vigila la aparición de síntomas como tos, irritación de garganta, falta de aire, fatiga excesiva o palpitaciones. |
| Desfavorable | Toda la población puede experimentar efectos negativos sobre la salud y los grupos de riesgo efectos mucho más serios. | Considera reducir las actividades al aire libre, y realizarlas en el interior o posponerlas para cuando la calidad del aire sea buena o razonablemente buena. Sigue el plan de tratamiento médico meticulosamente. | Considera reducir las actividades prolongadas y enérgicas al aire libre, especialmente si experimentas tos, falta de aire o irritación de garganta. |
| Muy desfavorable | Condiciones de emergencia para la salud pública, la población entera puede verse seriamente afectada. | Reduce toda actividad al aire libre, y considera realizar las actividades en el interior o posponerlas para cuando la calidad del aire sea buena o razonablemente buena. Sigue el plan de tratamiento médico meticulosamente. | Considera reducir las actividades al aire libre, y realizarlas en el interior o posponerlas para cuando la calidad del aire sea buena o razonablemente buena. |
| Extremadamente desfavorable | Condiciones de emergencia para la salud pública, la población entera puede verse gravemente afectada. | Evita la estancia prolongada al aire libre. Sigue el plan de tratamiento médico, en su caso, meticulosamente, y acude a un servicio de urgencias si tu estado de salud empeora. | Reduce toda actividad al aire libre y considera realizar las actividades en el interior o posponerlas para cuando la calidad del aire sea buena o razonablemente buena. Utiliza la protección adecuada para los trabajos que deban ser realizados al aire libre. |

### 1.5 ⚠ Corrección importante al CLAUDE.md

El CLAUDE.md (§6.2) dice «bandas del ICA **distintas** para población general y sensible». **No es así:** el ICA tiene **una sola tabla de bandas**; lo que cambia por población es la **recomendación** (tabla 1.4). Consecuencia para el motor: el perfil «sensible a la contaminación» no cambia la categoría, sino **a partir de qué categoría se desaconseja la actividad exterior**. Según el texto oficial:

- Población general: la recomendación cambia a partir de **Desfavorable** («considera reducir las actividades prolongadas y enérgicas»).
- Grupos de riesgo: cambia a partir de **Regular** («considera reducir las actividades prolongadas y enérgicas»).

Traducir eso a reglas («a partir de X, proponer cubierto u otra franja») es una **decisión del equipo** → `docs/decisiones-pendientes.md` (D-05).

---

## 2. Calor

**Estado: ✅ umbrales oficiales verificados** contra el PDF del plan de Sanidad 2026 (14/10/2026). La regla que usará el motor está **pendiente de decisión (DEC-06)**: abajo solo hay una propuesta.

**Fuente:** Ministerio de Sanidad — *Plan Nacional de Actuaciones Preventivas de los Efectos del Exceso de Temperaturas sobre la Salud 2026* (aprobado el 28/04/2026). PDF de 55 páginas: <https://www.sanidad.gob.es/areas/sanidadAmbiental/riesgosAmbientales/calorExtremo/publicaciones/docs/planNacionalExcesoTemperaturas_2026.pdf>. Copia local (no versionada): `app/data/raw/calor/plan2026.pdf` y su texto `plan2026.txt` (`pdftotext -layout`). Las páginas citadas son las del PDF, que coinciden con el número impreso al pie.

### 2.1 Umbrales de la Comunidad de Madrid (Anexo I, pág. 41)

Copiados **literalmente** de la tabla «Zonas de Meteosalud. Umbrales de temperatura máxima de impacto en salud. Comunidad de Madrid» (la tabla es una imagen en el PDF; `pdftotext` no la extrae y se leyó sobre la página renderizada a 600 ppp):

| Provincia | Zona meteosalud | UMBRAL TMÁX (°C) | PERCENTIL |
|---|---|---|---|
| Madrid | Sierra de Madrid | 35,8 | 94,8 |
| Madrid | Metropolitana y Henares | 37,4 | 88,9 |
| Madrid | Sur, Vegas y Oeste | 39,2 | 95,4 |

- **Unidad:** °C de **temperatura máxima diaria** (no horaria, no sensación térmica).
- **Códigos de zona** (leyenda del mapa de la misma página): `722801` Sierra de Madrid, `722802` Metropolitana y Henares, `722803` Sur, Vegas y Oeste.
- **Municipio → zona:** el plan solo lo da como **mapa** (código INE de 3 dígitos de cada municipio, coloreado según su zona); no hay lista en texto. Tabla de los 179 municipios en **`docs/assets/heat_zones.csv`** (`ine_code`, `municipality`, `zone_code`; UTF-8). Fuente: *Plan Nacional … 2026*, Anexo I, pág. 41, transcrito del mapa el 14/10/2026.
  - **Cómo:** el mapa es una imagen de 1040 × 720 px dentro del PDF (extraída tal cual con `pdfimages`; renderizar a más ppp no añade detalle). Se georreferenció contra las geometrías de `app/data/raw/municipios/municipios.geojson` (IDEM, EPSG:25830; IoU de la silueta 0,96), se tomó el color dominante dentro de cada municipio (verde = 722801, amarillo = 722802, cian = 722803; mínimo 99,5 % de los píxeles del mismo color, sin ningún municipio dudoso) y se comprobaron sobre recortes ampliados los números del mapa frente a la posición de cada código. Nombres y códigos: `DSMUNICIPIO_ORI` y `CDMUNICIPIO` del mismo fichero.
  - **Comprobaciones:** 179 filas, sin repetidos, el mismo conjunto de códigos que `municipios.geojson` (incluidos 28901, 28902 y 28903); pilotos **28079 Madrid → 722802**, **28065 Getafe → 722802**, **28131 San Lorenzo de El Escorial → 722801**; por zona: 722801 = 75, 722802 = 44, 722803 = 60; ningún municipio tiene una zona distinta de la de todos sus vecinos.
  - **Números poco legibles en el mapa** (la zona sale de la geometría, no del número; confirmado por el equipo el 14/10): 28018 Becerril de la Sierra y 28023 El Boalo (etiquetas superpuestas) y 28126 Robregordo y 28138 La Serna del Monte (tapadas en parte por líneas). Los cuatro quedan en 722801: son verdes al 100 % y están en el interior de la Sierra, lejos de la frontera entre zonas.
- **Periodo de activación** (pág. 11): «Con carácter general, el Plan Nacional se activa el 16 de mayo hasta el 30 de septiembre de cada año», con seguimiento del 1 al 15 de mayo y del 1 al 15 de octubre (criterio de flexibilidad).

### 2.2 Regla oficial de niveles (págs. 22–24)

Texto del plan (pág. 23): el nivel se asigna con un algoritmo de decisión basado en

- «La diferencia de temperatura máxima prevista y la temperatura umbral (solo cuando la temperatura máxima prevista sea mayor a la temperatura umbral establecida), con una persistencia en el tiempo de 3 días.»
- «El valor resultante se multiplicará por un “factor de riesgo” en función de la zona de meteosalud.» Nota al pie 3: «Para este año el factor de riesgo será 1 para todos los días y todas las zonas de meteosalud.»
- «Finalmente se suma el valor resultante de los tres días y el resultado obtenido decidirá el nivel de riesgo.»

Ecuación 1 (pág. 23): Σ (Tmáx Día *i* − Tumbral) × Factor riesgo Día *i*, para *i* = 1, 2, 3 (solo los días con Tmáx > Tumbral).

| Resultado del algoritmo (pág. 23) | Nivel (Tabla 2, pág. 24) | Denominación | Color |
|---|---|---|---|
| 0 | Nivel 0 | Ausencia de riesgo | verde |
| > 0 y ≤ 3,5 | Nivel 1 | Bajo riesgo | amarillo |
| > 3,5 y ≤ 7 | Nivel 2 | Riesgo medio | naranja |
| > 7 | Nivel 3 | Alto riesgo | rojo |

- Los límites 3,5 y 7 son el escenario E4 de la Tabla 1 (pág. 22), «de forma provisional a la espera de establecer los factores de riesgo específicos para cada provincia».
- Tmáx prevista: la de AEMET «en los observatorios de referencia establecidos para cada día y los dos futuros días consecutivos» (pág. 22).

**Interpretación oficial por grupos** (Anexo V, págs. 52–53; extracto literal):
- Amarillo: «riesgo leve para personas mayores de 65 años con otros factores de riesgo».
- Naranja: «riesgo leve en población general sin factores de riesgo»; «riesgo moderado para personas mayores de 65 años o menores de 65 años con múltiples factores de riesgo»; «riesgo elevado para mayores de 65 años con otros factores de riesgo adicionales».
- Rojo: «riesgo moderado en población general sin factores de riesgo»; «riesgo elevado para personas mayores de 65 años y menores de 65 años con algún factor de riesgo»; «riesgo extremo para mayores de 65 años con otros factores de riesgo adicionales».
- Entre los factores de riesgo (pág. 52): «Personales: Lactantes y menores de 4 años, personas mayores de 65 años, mujeres gestantes, personas con enfermedades cardiovasculares, respiratorias o crónicas» y, entre los «Ambientales, laborales o sociales:», la «exposición excesiva al calor por razones laborales, deportivas o de ocio (especialmente entre las 14:00h y las 19:00h)».

### 2.3 Propuesta para DEC-06 (no es decisión)

Datos disponibles de AEMET (esquema real comprobado en Task 4, CLAUDE.md §7.1): predicción **horaria** por municipio con `temperatura` y `sensTermica` (valores en cadena, por hora), ~48 h: hoy desde las 08–09 h, mañana completo y pasado mañana solo hasta las 07 h.

1. **Nivel de calor del día (estimación con la regla oficial, no el nivel oficial):** Tmáx prevista del día = máximo de `temperatura` horaria de ese día; se compara con el umbral de la zona del municipio (§2.1) y se aplica la Ecuación 1 con factor 1. **Limitaciones:** (i) el plan usa la Tmáx prevista por AEMET en los observatorios de referencia de cada zona (pág. 22), no la previsión horaria municipal: el máximo horario puede quedar por debajo de la máxima diaria y dos municipios de la misma zona pueden dar niveles distintos, así que la app debe mostrarlo como «nivel estimado» y nunca como el nivel publicado por Sanidad; (ii) la horaria no cubre el día 3 completo, así que con ella sola el sumatorio es de 2 días (nivel igual o **inferior** al oficial). Opciones: (a) aceptar 2 días y decirlo en la app; (b) usar además la predicción **diaria** por municipio de AEMET (`/prediccion/especifica/municipio/diaria/{ine}`, trae máxima por día) — **sin verificar y sería una petición más por municipio** (cuota), así que exige aprobación del equipo antes de añadirla.
2. **Efecto en la recomendación:** con nivel ≥ 1 (≥ 2 para población general, según la lectura del Anexo V) → proponer instalación cubierta o franja temprana/tardía (RF-09). El perfil «mayor», «Salgo con… niños menores de 4 años» y el perfil «carrito» endurecerían un nivel (el Anexo V cita «personas mayores de 65 años» y «Lactantes y menores de 4 años» como factores de riesgo personales; que «carrito» implique un menor de 4 años es lectura nuestra, no del plan).
3. **Elegir la hora (F2, criterio propio):** dentro del día, preferir la hora con menor `sensTermica` y evitar 14:00–19:00 en días de nivel ≥ 1, citando el Anexo V. El plan **no** da ningún umbral horario ni de sensación térmica: un `max_feels_like_c` en `config/rules.yaml` sería criterio propio (`own_criterion: true`), no oficial.
4. **Encaje con `config/rules.yaml`:** el contrato actual (`heat.max_feels_like_c`) no puede expresar umbrales por zona. Si se acepta la propuesta, `heat` necesitaría los tres umbrales por código de zona, los límites de nivel (3,5 y 7) y la tabla municipio → zona; cambio de contrato a decidir en DEC-06.

**Otras fuentes no usadas (sin localizar o sin verificar):** AEMET Meteoalerta (avisos por zona; documento de umbrales no localizado) y el plan de calor propio de la Comunidad de Madrid (el plan nacional, pág. 11, admite que las comunidades con plan propio usen «otros ámbitos de desagregación»).

---

## 3. Otros umbrales que usará el motor

| Umbral | Estado | Fuente candidata |
|---|---|---|
| Lluvia: probabilidad de precipitación a partir de la cual se propone cubierto | Decisión del equipo (no hay umbral oficial) | AEMET da `probPrecipitacion` por franjas de 6 h y `precipitacion` horaria (comprobado 14/10: franjas `0208`, `0814`, `1420`, `2002`; la regla horaria tendrá que asignar a cada hora la probabilidad de su franja; CLAUDE.md §7.1) |
| Velocidad al caminar o correr para el «tiempo a pie» | Decisión del equipo | Ver D-07 |
| Desnivel máximo para el perfil «carrito» o «mayor» | Fuera del MVP (RF-13 es Should) | IGN MDT05 (sin verificar) |
