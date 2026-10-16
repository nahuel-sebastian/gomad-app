# Ingesta de GoMad: descarga, normalizacion, bases DuckDB y grafo de rutas.
# Por ahora solo se usa para inicializar los datos de un equipo nuevo (deploy/docker-compose.init.yml).
FROM python:3.12.7-slim

WORKDIR /srv/ingest
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp \
    GOMAD_DATA_DIR=/data \
    GOMAD_CONFIG_DIR=/config

# osmium (grafo de rutas) necesita libexpat, que la imagen slim no trae
RUN apt-get update && apt-get install -y --no-install-recommends libexpat1 && rm -rf /var/lib/apt/lists/*

# dependencias primero, para aprovechar la cache de capas
COPY pyproject.toml ./
# pyproject.toml no empaqueta modulos (packages = []): solo instala las dependencias
RUN pip install --no-cache-dir ".[routing]" && rm -rf build

COPY . .
RUN chmod +x scripts/init_data.sh

ENTRYPOINT ["scripts/init_data.sh"]
