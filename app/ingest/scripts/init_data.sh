#!/usr/bin/env bash
# Inicializa los datos de un equipo nuevo dentro del contenedor ingest:
# descarga -> normaliza -> gomad.duckdb y realtime.duckdb -> grafo regional.
# Uso (desde app/): docker compose -f deploy/docker-compose.init.yml run --rm ingest [--skip-download] [--skip-graph]
set -uo pipefail

skip_download=0
skip_graph=0
for arg in "$@"; do
    case "$arg" in
        --skip-download) skip_download=1 ;;
        --skip-graph) skip_graph=1 ;;
        *) echo "Opción desconocida: $arg (válidas: --skip-download, --skip-graph)" >&2; exit 2 ;;
    esac
done

failures=0

step() {
    echo
    echo "==> $1"
    shift
    local t0=$SECONDS
    if "$@"; then
        echo "    hecho en $((SECONDS - t0)) s"
    else
        echo "    ⚠ falló (código $?): sigue con el resto" >&2
        failures=$((failures + 1))
    fi
}

if [ "$skip_download" -eq 0 ]; then
    # una fuente rota no para las demas (el script sale con error, pero descarga el resto);
    # la prevision (Open-Meteo, DEC-16) son los 179 municipios en una peticion, sin clave
    step "Descarga de las fuentes (grupo full)" \
        python scripts/download_sources.py --group full
    step "Descarga de las capas pesadas que usa la app" \
        python scripts/download_sources.py --only vpla_redes,ay_bancos,osm,callejero --include-heavy
fi

step "Normalización (app/data/clean)" python -m normalize
# verde de los destinos sin VPLA (Madrid capital...): areas verdes de OSM; si falla, build_db deja green NULL alli
step "Áreas verdes de OSM (clean/osm_green.parquet)" python osm_green.py
step "Mobiliario de OSM (clean/osm_poi.parquet)" python osm_poi.py
step "Bases DuckDB (gomad.duckdb y realtime.duckdb)" python -m build_db all

if [ "$skip_graph" -eq 0 ]; then
    step "Grafo regional de rutas (unos minutos y ~4 GB de RAM)" python graph.py all
fi

echo
if [ "$failures" -eq 0 ]; then
    echo "Datos listos en app/data. Siguiente: docker compose -f deploy/docker-compose.yml up -d --build"
else
    echo "Terminado con $failures paso(s) con fallos (ver arriba). Lo que se haya generado sirve igual."
fi
exit "$failures"
