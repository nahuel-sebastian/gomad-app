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

**Estado: ⏳ PENDIENTE. No hay ningún umbral verificado todavía.** No se han inventado valores.

Fuentes oficiales localizadas:

1. **Ministerio de Sanidad — Plan Nacional de Actuaciones Preventivas de los Efectos del Exceso de Temperaturas sobre la Salud 2026** (aprobado el 28/04/2026; vigente del 16 de mayo al 30 de septiembre, con vigilancia antes y después). PDF de 55 páginas: <https://www.sanidad.gob.es/areas/sanidadAmbiental/riesgosAmbientales/calorExtremo/publicaciones/docs/planNacionalExcesoTemperaturas_2026.pdf>. Según la nota de prensa, **actualiza umbrales** con la mortalidad de 2012–2023, y el nivel de riesgo se calcula con la diferencia entre la máxima prevista y el umbral de la zona meteosalud, con persistencia de 3 días. **No se ha podido leer:** falta `pdftotext` en el equipo (ver PENDIENTES P-03).
2. **AEMET — Meteoalerta** (avisos amarillo, naranja y rojo por temperatura máxima, por zona de aviso). Un aviso CAP oficial de AEMET para la Sierra de Madrid cita «amarillo, máxima 36 ºC», pero **no se ha localizado aún el documento de umbrales por zona**, así que no se usa.
3. **Comunidad de Madrid** tiene su propio plan de calor (activa niveles por zonas). No localizado aún.

**Nota de diseño (para decidir, no decidido):** el plan de Sanidad está pensado para alertas de salud pública por días, no para elegir una franja horaria. Para F2 («mejor hora») probablemente haga falta además la **sensación térmica horaria** de AEMET (`sensTermica`). Ver D-06.

---

## 3. Otros umbrales que usará el motor

| Umbral | Estado | Fuente candidata |
|---|---|---|
| Lluvia: probabilidad de precipitación a partir de la cual se propone cubierto | Decisión del equipo (no hay umbral oficial) | AEMET da `probPrecipitacion` por franjas de 6 h y `precipitacion` horaria (comprobado 14/10: franjas `0208`, `0814`, `1420`, `2002`; la regla horaria tendrá que asignar a cada hora la probabilidad de su franja; CLAUDE.md §7.1) |
| Velocidad al caminar o correr para el «tiempo a pie» | Decisión del equipo | Ver D-07 |
| Desnivel máximo para el perfil «carrito» o «mayor» | Fuera del MVP (RF-13 es Should) | IGN MDT05 (sin verificar) |
