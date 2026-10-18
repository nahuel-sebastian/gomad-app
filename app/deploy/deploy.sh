#!/usr/bin/env bash
# Despliega GoMad en la VM: actualiza el repo, compila y levanta el Compose y comprueba que responde.
# Se ejecuta desde la raiz del repo (~/GoMad en la VM):  app/deploy/deploy.sh [--no-pull]
# No usa sudo, no borra volumenes y nunca imprime el contenido de los .env.
set -euo pipefail

usage() {
    cat <<'TXT'
Uso: app/deploy/deploy.sh [--no-pull]

  --no-pull   no hace «git pull» (útil en local o si ya está actualizado)
  -h, --help  muestra esta ayuda

Variables opcionales:
  GOMAD_URL       URL base para las comprobaciones (por defecto http://localhost)
  GOMAD_WAIT_S    segundos máximos de espera a que responda (por defecto 90)
TXT
}

pull=1
for arg in "$@"; do
    case "$arg" in
        --no-pull) pull=0 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Opción desconocida: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

url="${GOMAD_URL:-http://localhost}"
wait_s="${GOMAD_WAIT_S:-90}"

# raiz del repo a partir de la ubicacion del guion (app/deploy/deploy.sh)
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
app_dir="$repo_dir/app"
compose=(docker compose -f "$app_dir/deploy/docker-compose.yml")

# fallo antes de tocar los contenedores (configuracion, docker, git): sin pista de ps/logs
fail() {
    echo "" >&2
    echo "ERROR: $1" >&2
    exit 1
}

# fallo a partir de «docker compose up»: ahi si sirven ps y logs
fail_compose() {
    echo "" >&2
    echo "ERROR: $1" >&2
    echo "Para ver qué ha pasado:" >&2
    echo "  cd \"$app_dir\" && docker compose -f deploy/docker-compose.yml ps" >&2
    echo "  cd \"$app_dir\" && docker compose -f deploy/docker-compose.yml logs --tail=80" >&2
    exit 1
}

echo "==> Comprobando configuración"
# solo se comprueba que existen; su contenido (claves) no se lee ni se muestra
[[ -f "$app_dir/.env" ]] || fail "falta app/.env (cópialo de app/.env.example y pon las claves)."
[[ -f "$app_dir/deploy/.env" ]] || fail "falta app/deploy/.env (cópialo de app/deploy/.env.example; DOMAIN=:80 sin dominio)."
# la cache de la prevision en vivo se monta con escritura; si no existe, Docker la crearia como root
mkdir -p "$app_dir/data/live"
# credenciales de OCI (fila 13): se montan en /oci:ro; si no existe, Docker la crearia como root y el scp fallaria.
# Misma carpeta que el compose cuando OCI_DIR no esta en app/deploy/.env (aqui solo se mira el entorno)
oci_dir="${OCI_DIR:-$HOME/.oci}"
{ mkdir -p "$oci_dir" && chmod 700 "$oci_dir"; } \
    || fail "no se puede preparar $oci_dir (¿es de root? arréglalo con: sudo chown -R \"\$USER\": \"$oci_dir\")."
command -v docker >/dev/null || fail "no se encuentra docker."
command -v curl >/dev/null || fail "no se encuentra curl."
docker info >/dev/null 2>&1 || fail "docker no responde (¿estás en el grupo docker? abre una sesión nueva)."

if [[ "$pull" -eq 1 ]]; then
    echo "==> Actualizando el repositorio (git pull --ff-only)"
    git -C "$repo_dir" pull --ff-only || fail "git pull no ha podido avanzar sin fusión (¿cambios locales en la VM?)."
else
    echo "==> Sin git pull (--no-pull)"
fi

echo "==> Compilando y levantando los contenedores"
"${compose[@]}" up -d --build || fail_compose "docker compose up ha fallado."

echo "==> Esperando a que responda $url (máximo ${wait_s} s)"
deadline=$((SECONDS + wait_s))
until curl -fsS -o /dev/null "$url/api/health" 2>/dev/null && curl -fsS -o /dev/null "$url/" 2>/dev/null; do
    (( SECONDS < deadline )) || fail_compose "no responde $url/ o $url/api/health tras ${wait_s} s."
    sleep 2
done

echo "==> Comprobando respuestas"
# el index.html del build referencia el JS compilado en /assets/; la pagina de prueba no
# se guarda la respuesta antes del grep: con pipefail, «curl | grep -q» puede fallar por SIGPIPE
home_body="$(curl -fsS "$url/")" || fail_compose "$url/ no responde."
grep -q '/assets/index-' <<<"$home_body" || fail_compose "$url/ no devuelve el index.html del build del front."
health_body="$(curl -fsS "$url/api/health")" || fail_compose "$url/api/health no responde."
grep -q '"status":"ok"' <<<"$health_body" || fail_compose "$url/api/health no devuelve {\"status\":\"ok\"}."

# los dos servicios deben estar en marcha
running="$("${compose[@]}" ps --status running --services)" || fail_compose "no se ha podido consultar el estado de los contenedores."
for service in api frontend; do
    grep -qx "$service" <<<"$running" || fail_compose "el servicio $service no está en marcha."
done

echo ""
echo "Despliegue correcto"
echo "  Commit: $(git -C "$repo_dir" log -1 --format='%h %s (%cd)' --date=format:'%d/%m/%Y %H:%M')"
echo "  Front:  $url/  →  OK"
echo "  API:    $url/api/health  →  OK"
echo "  Contenedores:"
"${compose[@]}" ps --format '{{.Service}}: {{.Status}}' | sed 's/^/    /'
