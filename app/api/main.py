"""API de GoMad. Sin estado: sin sesiones ni registro; la ubicacion nunca se escribe en los logs."""
from fastapi import FastAPI, HTTPException, Query

import schemas as s

app = FastAPI(title="GoMad API", version="0.1.0")


def _not_implemented():
    raise HTTPException(status_code=501, detail="Pendiente de implementar")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/activities", response_model=s.ActivitiesResponse)
def activities():
    _not_implemented()


@app.get("/location", response_model=s.LocationResponse)
def location(text: str = Query(min_length=3, max_length=200)):
    _not_implemented()


@app.post("/recommend", response_model=s.RecommendResponse)
def recommend(request: s.RecommendRequest):
    _not_implemented()


@app.post("/route", response_model=s.RouteResponse)
def route(request: s.RouteRequest):
    _not_implemented()


@app.get("/municipality/{ine_code}", response_model=s.MunicipalityResponse)
def municipality(ine_code: str):
    _not_implemented()


@app.post("/assistant/interpret", response_model=s.InterpretResponse)
def assistant_interpret(request: s.InterpretRequest):
    _not_implemented()


@app.post("/assistant/route", response_model=s.AssistantRouteResponse)
def assistant_route(request: s.AssistantRouteRequest):
    _not_implemented()


@app.get("/sources", response_model=s.SourcesResponse)
def sources():
    _not_implemented()
