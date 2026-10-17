"""Contrato de la API (arquitectura §4.1). Cambiarlo = regenerar openapi.json y los tipos del front."""
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# las horas del contrato son hora local de Madrid sin zona (como la prevision de Open-Meteo y el motor)
LOCAL_TZ = ZoneInfo("Europe/Madrid")
LOCAL_TIME = "Hora local de Madrid sin zona horaria; si llega con zona, se convierte."

Profile = Literal["general", "senior", "stroller", "sensitive"]
Companion = Literal["dog", "kids"]
Setting = Literal["outdoor", "indoor", "any"]
# categorias del ICA (BOE-A-2020-10426): Buena, Razonablemente buena, Regular, Desfavorable,
# Muy desfavorable, Extremadamente desfavorable
AqiCategory = Literal["good", "fair", "moderate", "poor", "very_poor", "extremely_poor"]
Factor = Literal["proximity", "suitability", "green", "air", "weather"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Coordinate(Strict):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)


class DataSource(Strict):
    source: str                       # id de ingest/scripts/download_sources.py, p. ej. "aire_dia"
    label: str                        # texto para la persona, p. ej. "Calidad del aire (Comunidad de Madrid)"
    date: datetime | None             # fecha del dato (no de la descarga) si se conoce
    own_criterion: bool = False       # True si el umbral/valor no tiene fuente oficial (CLAUDE.md §2.9)


class Weights(Strict):
    proximity: float = Field(ge=0, le=1)
    suitability: float = Field(ge=0, le=1)
    green: float = Field(ge=0, le=1)
    air: float = Field(ge=0, le=1)
    weather: float = Field(ge=0, le=1)


class RouteWeights(Strict):
    traffic: float = Field(ge=0, le=1)
    green: float = Field(ge=0, le=1)
    fountains: float = Field(ge=0, le=1)


class Activity(Strict):
    id: str
    label: str
    icon: str                         # nombre de Material Symbols
    outdoor: bool | None              # None = puede ser ambas


class ActivitiesResponse(Strict):
    activities: list[Activity]
    profiles: list[Profile]
    companions: list[Companion]
    default_weights: Weights


class LocationCandidate(Strict):
    label: str
    municipality: str
    ine_code: str = Field(pattern=r"^28\d{3}$")
    coordinate: Coordinate
    precision: Literal["address", "street", "municipality"]


class LocationResponse(Strict):
    candidates: list[LocationCandidate]


class RecommendRequest(Strict):
    origin: Coordinate
    activity: str | None = None       # None = «Sorpréndeme» (RF-03)
    window_start: datetime = Field(description=LOCAL_TIME)
    window_end: datetime = Field(description=LOCAL_TIME)
    duration_min: int = Field(ge=10, le=480)
    max_distance_m: int = Field(ge=200, le=50_000)
    setting: Setting = "any"
    profile: Profile = "general"
    companions: list[Companion] = []
    weights: Weights | None = None    # None = por defecto (config/weights.yaml)
    limit: int = Field(default=3, ge=1, le=20)
    offset: int = Field(default=0, ge=0)   # «Ver más» (RF-05)

    @field_validator("window_start", "window_end")
    @classmethod
    def to_local_time(cls, value: datetime) -> datetime:
        # toISOString() del navegador manda UTC: sin esto, mezclar con hora sin zona daria un 500
        if value.tzinfo is None:
            return value
        return value.astimezone(LOCAL_TZ).replace(tzinfo=None)

    @model_validator(mode="after")
    def check_window(self):
        if self.window_end <= self.window_start:
            raise ValueError("El final de la ventana debe ser posterior al inicio.")
        return self


class DestinationSummary(Strict):
    id: str                           # '{fuente}:{id_origen}'
    name: str
    type: Literal["facility", "park", "recreation_area", "trail", "bathing_area"]
    covered: bool | None
    municipality: str
    ine_code: str
    coordinate: Coordinate
    source: DataSource


class FactorScore(Strict):
    factor: Factor
    value: float | None = Field(ge=0, le=10)   # None = sin datos (no cuenta en la nota)
    weight: float = Field(ge=0, le=1)          # peso efectivo tras renormalizar
    text: str                                  # «Aire: razonablemente bueno»


class HourEvaluation(Strict):
    hour: datetime = Field(description=LOCAL_TIME)
    score: float | None = Field(ge=0, le=10)
    outdoor_ok: bool | None                    # None = sin datos para decidir
    reasons: list[str]
    temperature_c: float | None
    feels_like_c: float | None
    precip_prob: float | None
    aqi_category: AqiCategory | None


class Recommendation(Strict):
    destination: DestinationSummary
    distance_m: float
    duration_min: float
    score: float = Field(ge=0, le=10)
    factors: list[FactorScore]
    best_hour: datetime | None = Field(description=LOCAL_TIME)
    hours: list[HourEvaluation]
    indoor_alternative: bool                   # True si se propone por lluvia/calor/aire (RF-09)
    explanation: str                           # lenguaje llano, plantillas (RF-10)
    sources: list[DataSource]


class RecommendResponse(Strict):
    results: list[Recommendation]
    has_more: bool
    warnings: list[str]                        # «Verde: sin datos en este municipio»
    medical_disclaimer: str


class RouteRequest(Strict):
    origin: Coordinate
    destination: Coordinate
    profile: Profile = "general"
    weights: RouteWeights | None = None


class RoutePoi(Strict):
    type: Literal["fountain", "bench", "bin", "toilet", "dog_area", "playground", "aed", "outdoor_gym", "supermarket"]
    coordinate: Coordinate
    source: str


class LineString(Strict):
    """GeoJSON LineString en EPSG:4326: [[lon, lat], ...]."""
    type: Literal["LineString"]
    coordinates: list[list[float]] = Field(min_length=2)


class RouteVariant(Strict):
    kind: Literal["direct", "healthy"]
    geometry: LineString
    distance_m: float
    duration_min: float
    green_pct: float | None = Field(ge=0, le=100)
    traffic_m: float
    pois: list[RoutePoi]
    approximate: bool = False                  # True = linea recta (sin red peatonal)
    description: str                           # «2,4 km, 30 min, 68 % por zona verde, 2 fuentes»


class RouteResponse(Strict):
    direct: RouteVariant
    healthy: RouteVariant
    warnings: list[str]
    sources: list[DataSource]


class Indicator(Strict):
    category: Literal["sport", "nature", "mobility", "health", "education", "connectivity", "social"]
    key: str
    label: str
    value: float | None                        # None = «sin datos» explicito
    unit: str
    year: int | None
    source: DataSource
    extra_sources: list[DataSource] = []       # RF-19: el resto de fuentes del indicador (p. ej. padron en las tasas)


class MunicipalityResponse(Strict):
    ine_code: str
    name: str
    population: int | None
    indicators: list[Indicator]
    fit: list[str]                             # frases sin ranking (RF-18)
    fit_own_criterion: bool = False            # True si hay encaje: es criterio propio y la app lo dice (§2.9)


class AssistantParams(Strict):
    """Esquema cerrado de F6 (RF-21). La interpretacion (OCI Language + diccionario) solo puede rellenar esto."""
    activity: Literal["walk", "run"]
    distance_km: float | None = Field(default=None, gt=0, le=42)
    duration_min: int | None = Field(default=None, gt=0, le=480)
    loop: bool = True
    pass_by: list[Literal["park", "fountain", "bench", "supermarket", "dog_area", "playground"]] = []
    avoid: list[Literal["traffic", "hills"]] = []


class InterpretRequest(Strict):
    text: str = Field(min_length=3, max_length=500)


class InterpretResponse(Strict):
    params: AssistantParams | None
    clarification: str | None                  # RF-24: pregunta si es ambiguo
    rejection: str | None                      # RF-24: fuera de catalogo o consejo medico


class AssistantRouteRequest(Strict):
    origin: Coordinate
    params: AssistantParams


class Condition(Strict):
    condition: str
    met: bool
    detail: str                                # dato del motor, nunca inventado


class AssistantRouteResponse(Strict):
    route: RouteVariant
    conditions: list[Condition]
    explanation: str
    written_by_ai: bool


class SourceInfo(Strict):
    id: str
    name: str
    publisher: str
    license: str
    url: str
    last_refresh: datetime | None
    last_failure: datetime | None


class SourcesResponse(Strict):
    sources: list[SourceInfo]


# --- Mapa explorable (correccion C2, 17/10): GET /map/points ---
# tipos de destino (DestinationSummary.type, mas «pool»: instalacion con la actividad de nadar) y de punto de ruta
MapDestinationKind = Literal["facility", "pool", "park", "recreation_area", "trail", "bathing_area"]
MapPoiKind = Literal["fountain", "bench", "aed", "dog_area", "playground"]
# Literal anidado = la union de los dos (mismo enum en el contrato)
MapPointKind = Literal[MapDestinationKind, MapPoiKind]


class MapPoint(Strict):
    id: str                                    # '{fuente}:{id_origen}'
    kind: MapPointKind
    name: str | None                           # los puntos de ruta no tienen nombre
    coordinate: Coordinate
    working: bool | None                       # False = fuera de servicio (se muestra, no cuenta); None = sin dato
    source: str


class MapPointsResponse(Strict):
    points: list[MapPoint]                     # los mas cercanos al centro de la caja primero
    truncated: bool                            # True = habia mas de max_points: acercar el mapa
    clipped: bool                              # True = la caja era mayor que max_span_deg y se recorto
