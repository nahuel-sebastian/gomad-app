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

# pocos municipios de AEMET por defecto: con todos, la cuota lo alarga casi una hora
aemet="${INIT_AEMET_MUNICIPALITIES:-28065,28079}"
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
    if [ -z "${AEMET_API_KEY:-}" ]; then
        echo "Aviso: sin AEMET_API_KEY en app/.env no habrá previsión del tiempo; el resto sí."
    fi
    # una fuente rota no para las demas (el script sale con error, pero descarga el resto)
    step "Descarga de las fuentes (grupo full)" \
        python scripts/download_sources.py --group full --aemet-municipalities "$aemet"
    step "Descarga de las capas pesadas que usa la app" \
        python scripts/download_sources.py --only vpla_redes,ay_bancos,osm,callejero --include-heavy
fi

step "Normalización (app/data/clean)" python -m normalize
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
