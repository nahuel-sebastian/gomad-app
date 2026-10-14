FROM python:3.12-slim
WORKDIR /srv/api
COPY pyproject.toml ./
RUN pip install --no-cache-dir .
COPY . .
# datos y configuracion compartidos llegan por volumen (docker-compose.yml)
ENV PYTHONPATH=/srv/api PYTHONUNBUFFERED=1 GOMAD_DATA_DIR=/data GOMAD_CONFIG_DIR=/config
EXPOSE 8000
# --no-access-log: el log de acceso escribiria la URL completa (GET /location?text=... = direccion del usuario)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
