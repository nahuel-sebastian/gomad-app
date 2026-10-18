"""API de GoMad. Sin estado: sin sesiones ni registro; la ubicacion nunca se escribe en los logs."""
import logging
import os
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
from live import build_live
from live.store import validate_realtime
from repository import DataUnavailable, Repository
from routing.store import GraphStore
from services import assistant as assistant_service
from services import map_points as map_points_service
from services import municipality as municipality_service
from services import recommend as recommend_service
from services import route as route_service
from services import sources as sources_service

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
    validate_rules(settings.load("rules"), config_dir=settings.CONFIG_DIR)
    validate_weights(settings.load("weights")["defaults"])
    municipality_service.validate_fit(settings.load("indicators"),
                                      [a["id"] for a in settings.load("activities")["activities"]])
    map_points_service.validate_map_config(settings.load("map"))
    realtime = settings.load("realtime")
    validate_realtime(realtime)
    app.state.assistant = assistant_service.make_provider(os.environ)   # F6: valida assistant.yaml; OCI si hay claves
    t0 = time.perf_counter()
    app.state.graphs = GraphStore.load(settings.DATA_DIR / "graph")
    log.info("grafos cargados: %s en %.1f s", [z.name for z in app.state.graphs.zones], time.perf_counter() - t0)
    app.state.geocoder = Geocoder(settings.DATA_DIR, httpx.Client())
    # datos en vivo en memoria (DEC-15); GOMAD_LIVE=off (pruebas) deja la lectura de realtime.duckdb
    live = None if os.environ.get("GOMAD_LIVE") == "off" else build_live(
        realtime, httpx.Client(), snapshot_dir=os.environ.get("GOMAD_LIVE_SNAPSHOT") or None,
        cache_path=settings.DATA_DIR / "live" / "forecast.json",
        air_seed_dir=settings.DATA_DIR / "clean" / "air_reading")
    app.state.live = live
    app.state.repo = Repository(settings.DATA_DIR, live=live)
    if live is not None:
        live.start()
    yield
    if live is not None:
        if live.stop():          # si una descarga sigue colgada, el hilo (daemon) muere con el proceso
            live.client.close()
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


def get_assistant(request: Request):
    # sin lifespan (pruebas), se crea una vez; a OCI solo ira el texto de /assistant/interpret
    if getattr(request.app.state, "assistant", None) is None:
        request.app.state.assistant = assistant_service.make_provider(os.environ)
    return request.app.state.assistant


@app.post("/assistant/interpret", response_model=s.InterpretResponse)
def assistant_interpret(request: s.InterpretRequest, assistant=Depends(get_assistant)):
    return assistant.interpret(request.text)


@app.post("/assistant/route", response_model=s.AssistantRouteResponse)
def assistant_route(request: s.AssistantRouteRequest, repo: Repository = Depends(get_repo),
                    graphs: GraphStore = Depends(get_graphs), assistant=Depends(get_assistant)):
    try:
        return assistant_service.assistant_route(request, repo, graphs, assistant)
    except assistant_service.NoDestination as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DataUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/sources", response_model=s.SourcesResponse)
def sources(repo: Repository = Depends(get_repo)):
    return sources_service.sources(repo, repo.main.parent)


def get_map_config() -> dict:
    return settings.load("map")


@app.get("/map/points", response_model=s.MapPointsResponse)
def map_points(bbox: str = Query(max_length=200, description="Caja visible del mapa: oeste,sur,este,norte (EPSG:4326)"),
               kinds: list[s.MapPointKind] = Query(default=list(get_args(s.MapDestinationKind)),
                                                   description="Tipos de punto; por defecto, los de destino"),
               repo: Repository = Depends(get_repo), cfg: dict = Depends(get_map_config)):
    # la caja es la de la vista del mapa, no la ubicacion de la persona; aun asi no se escribe en los logs
    try:
        return map_points_service.map_points(bbox, kinds, repo, cfg)
    except map_points_service.InvalidBbox as e:
        raise HTTPException(status_code=422, detail=str(e))
    except DataUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))
