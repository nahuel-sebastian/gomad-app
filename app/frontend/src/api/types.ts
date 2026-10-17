// Alias de los tipos del contrato (generados en schema.d.ts con `npm run contract`).
// No editar schema.d.ts a mano: sale de openapi.json, que versiona Motor.
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Activity = Schemas["Activity"];
export type ActivitiesResponse = Schemas["ActivitiesResponse"];
export type AssistantParams = Schemas["AssistantParams"];
export type AssistantRouteRequest = Schemas["AssistantRouteRequest"];
export type AssistantRouteResponse = Schemas["AssistantRouteResponse"];
export type Condition = Schemas["Condition"];
export type Coordinate = Schemas["Coordinate"];
export type DataSource = Schemas["DataSource"];
export type DestinationSummary = Schemas["DestinationSummary"];
export type FactorScore = Schemas["FactorScore"];
export type HourEvaluation = Schemas["HourEvaluation"];
export type Indicator = Schemas["Indicator"];
export type InterpretResponse = Schemas["InterpretResponse"];
export type LocationCandidate = Schemas["LocationCandidate"];
export type LocationResponse = Schemas["LocationResponse"];
export type MapPoint = Schemas["MapPoint"];
export type MapPointsResponse = Schemas["MapPointsResponse"];
export type MunicipalityResponse = Schemas["MunicipalityResponse"];
export type RecommendRequest = Schemas["RecommendRequest"];
export type RecommendResponse = Schemas["RecommendResponse"];
export type Recommendation = Schemas["Recommendation"];
export type RoutePoi = Schemas["RoutePoi"];
export type RouteRequest = Schemas["RouteRequest"];
export type RouteResponse = Schemas["RouteResponse"];
export type RouteVariant = Schemas["RouteVariant"];
export type RouteWeights = Schemas["RouteWeights"];
export type SourceInfo = Schemas["SourceInfo"];
export type SourcesResponse = Schemas["SourcesResponse"];
export type Weights = Schemas["Weights"];

export type AqiCategory = NonNullable<HourEvaluation["aqi_category"]>;
export type Profile = NonNullable<RecommendRequest["profile"]>;
export type Companion = NonNullable<RecommendRequest["companions"]>[number];
export type Setting = NonNullable<RecommendRequest["setting"]>;
export type Factor = FactorScore["factor"];
export type PoiType = RoutePoi["type"];
export type MapPointKind = MapPoint["kind"];
export type IndicatorCategory = Indicator["category"];
export type PassBy = NonNullable<AssistantParams["pass_by"]>[number];
export type Avoid = NonNullable<AssistantParams["avoid"]>[number];
