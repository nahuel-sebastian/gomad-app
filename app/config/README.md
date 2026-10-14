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
| `indicators.yaml` | Indicadores de la vista de municipio (F5) | DEC-09 |
