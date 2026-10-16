"""API de GoMad. Sin estado: sin sesiones ni registro; la ubicacion nunca se escribe en los logs."""
import logging
import time
from contextlib import asynccontextmanager
from typing import get_args

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query, Request

import schemas as s
import settings
from engine.rules import validate_rules
from engine.scoring import validate_weights
from geocoding import Geocoder
from repository import DataUnavailable, Repository
from routing.store import GraphStore
from services import municipality as municipality_service
from services import recommend as recommend_service
from services import route as route_service

log = logging.getLogger("gomad.api")
if not log.handlers:
    # uvicorn no configura este logger: sin handler propio, los INFO se perderian
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # un error de configuracion para el arranque, no sale como 500 en una peticion
    validate_rules(settings.load("rules"))
    validate_weights(settings.load("weights")["defaults"])
    app.state.repo = Repository(settings.DATA_DIR)
    t0 = time.perf_counter()
    app.state.graphs = GraphStore.load(settings.DATA_DIR / "graph")
    log.info("grafos cargados: %s en %.1f s", [z.name for z in app.state.graphs.zones], time.perf_counter() - t0)
    app.state.geocoder = Geocoder(settings.DATA_DIR, httpx.Client())
    yield
    app.state.geocoder.client.close()


app = FastAPI(title="GoMad API", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    # solo metodo, ruta, codigo y milisegundos: ni cuerpo ni query (la query de /location es una direccion)
    t0 = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log.info("%s %s %d %.0f ms", request.method, request.url.path, status, (time.perf_counter() - t0) * 1000)


def get_repo(request: Request) -> Repository:
    return getattr(request.app.state, "repo", None) or Repository(settings.DATA_DIR)


def get_graphs(request: Request) -> GraphStore:
    return getattr(request.app.state, "graphs", None) or GraphStore()


def _not_implemented():
    raise HTTPException(status_code=501, detail="Pendiente de implementar")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/activities", response_model=s.ActivitiesResponse)
def activities():
    catalog = settings.load("activities")["activities"]
    return s.ActivitiesResponse(
        activities=[s.Activity(id=a["id"], label=a["label"], icon=a["icon"], outdoor=a.get("outdoor")) for a in catalog],
        profiles=list(get_args(s.Profile)), companions=list(get_args(s.Companion)),
        default_weights=s.Weights(**settings.load("weights")["defaults"]))


@app.post("/recommend", response_model=s.RecommendResponse)
def recommend(request: s.RecommendRequest, repo: Repository = Depends(get_repo),
              graphs: GraphStore = Depends(get_graphs)):
    try:
        return recommend_service.recommend(request, repo, graphs)
    except recommend_service.UnknownActivity as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DataUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


def get_geocoder(request: Request) -> Geocoder:
    return getattr(request.app.state, "geocoder", None) or Geocoder(settings.DATA_DIR)


@app.get("/location", response_model=s.LocationResponse)
def location(text: str = Query(min_length=3, max_length=200), geocoder: Geocoder = Depends(get_geocoder)):
    try:
        return s.LocationResponse(candidates=[s.LocationCandidate(**c) for c in geocoder.search(text)])
    except DataUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/route", response_model=s.RouteResponse)
def route(request: s.RouteRequest, repo: Repository = Depends(get_repo), graphs: GraphStore = Depends(get_graphs)):
    try:
        return route_service.route(request, repo, graphs)
    except DataUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/municipality/{ine_code}", response_model=s.MunicipalityResponse)
def municipality(ine_code: str,
                 activities: list[str] = Query(default=[], description="Actividades del catálogo para el encaje (RF-18)"),
                 profile: s.Profile = "general", companions: list[s.Companion] = Query(default=[]),
                 repo: Repository = Depends(get_repo)):
    try:
        return municipality_service.municipality(ine_code, repo, activities, profile, companions)
    except municipality_service.UnknownActivity as e:
        raise HTTPException(status_code=422, detail=str(e))
    except municipality_service.UnknownMunicipality as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DataUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.post("/assistant/interpret", response_model=s.InterpretResponse)
def assistant_interpret(request: s.InterpretRequest):
    _not_implemented()


@app.post("/assistant/route", response_model=s.AssistantRouteResponse)
def assistant_route(request: s.AssistantRouteRequest):
    _not_implemented()


@app.get("/sources", response_model=s.SourcesResponse)
def sources():
    _not_implemented()
