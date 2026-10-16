# config/

YAML compartidos por los servicios. Se monta **en solo lectura** en `api` e `ingest` (en Docker, `/config`; en local, `app/config` o la variable `GOMAD_CONFIG_DIR`). El código **lee** estos valores; ninguna tarea de código los fija.

**Regla:** cada valor sin fuente oficial lleva `own_criterion: true`, y la app lo dice. Los valores con fuente oficial citan la fuente.

| Fichero | Contenido | Decisión que lo rellena |
|---|---|---|
| `ica_thresholds.yaml` | Bandas del Índice de Calidad del Aire (BOE, verificadas) | Task 12 (copiadas de `docs/assets/umbrales.md`) |
| `rules.yaml` | Filtros duros: `air` (regla por perfil), `rain` (probabilidad de lluvia), `heat` (umbrales de calor) | DEC-05 (`air`), DEC-07b (`rain`), DEC-06 (`heat`) |
| `weights.yaml` | Pesos por defecto de la puntuación y velocidades | DEC-07 |
| `routing.yaml` | Pesos de la ruta saludable (tráfico, verde, sombra, fuentes) | DEC-07 |
| `activities.yaml` | Catálogo de actividades y tabla actividad → destino | DEC-08 |
| `indicators.yaml` | 14 indicadores de la vista de municipio (F5) con su regla «sin filas», y `fit`: qué indicador mira cada perfil y acompañante (RF-18, criterio propio) | DEC-09 (16/10); lo valida `ingest/indicators.py` |
| `recommend.yaml` | Parámetros de `/recommend` sin fuente oficial: rodeo de la línea recta, radio de duplicados, tope de candidatos, alternativa cubierta, validez de la última medición de aire (criterio propio) | V-M1 (16/10) |
| `sources.yaml` | Etiquetas de cada fuente para la persona (`DataSource.label`) | V-M1 (16/10); S-D1 añade licencias |
| `realtime.yaml` | Datos en vivo en memoria: URL, TTL, validez máxima (`max_age_h`) y tiempo de espera de cada fuente; cuota, pilotos y respaldo de AEMET (criterio propio salvo `max_issued_age_h`) | DEC-15 y DEC-13 (16/10); lo valida `api/live/store.py` |
| `forecast_points.csv` | Un punto por municipio (179: `ine_code,name,lat,lon`) para pedir la previsión a Open-Meteo; es lo único que se le envía, nunca la ubicación de la persona. Centroide del contorno o, si cae fuera, un punto interior (misma regla que el geocodificador). Lo genera `ingest/scripts/forecast_points.py` | DEC-16 (16/10) |
