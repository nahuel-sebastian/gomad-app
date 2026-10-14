"""API de GoMad. Sin estado: sin sesiones ni registro; la ubicacion nunca se escribe en los logs."""
from fastapi import FastAPI

app = FastAPI(title="GoMad API", version="0.1.0")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
