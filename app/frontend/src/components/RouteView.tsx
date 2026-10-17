import { useState } from "react";
import { Link, Navigate, useParams } from "react-router";
import type { PoiType, RouteVariant } from "../api/types";
import { getRoute } from "../data/route";
import { useAsync } from "../data/useAsync";
import { formatDistance, formatMinutes } from "../lib/format";
import { poiCount } from "../lib/labels";
import { NO_SEARCH_NOTICE } from "../lib/texts";
import { useAppState } from "../state/context";
import ErrorMessage from "./ErrorMessage";
import Icon from "./Icon";
import { destinationKind } from "./mapIcons";
import MapView from "./MapView";
import PageHeading from "./PageHeading";
import SourceList from "./SourceList";

const VARIANTS = [
    { kind: "healthy", label: "Ruta recomendada", hint: "más verde y menos tráfico" },
    { kind: "direct", label: "Ruta directa", hint: "la más corta" },
] as const;

// PDI que se resumen en la ruta (RF-13), en este orden
const POI_ORDER: PoiType[] = ["fountain", "bench", "aed", "dog_area", "playground", "bin", "toilet", "outdoor_gym", "supermarket"];

function poiSummary(variant: RouteVariant): string[] {
    const counts = new Map<PoiType, number>();
    variant.pois.forEach((p) => counts.set(p.type, (counts.get(p.type) ?? 0) + 1));
    return POI_ORDER.filter((t) => counts.has(t)).map((t) => poiCount(t, counts.get(t)!));
}

export default function RouteView() {
    const { id = "" } = useParams();
    const { origin, results, preferences, search } = useAppState();
    const item = results.find((r) => r.destination.id === id);
    const [kind, setKind] = useState<"healthy" | "direct">("healthy");
    const [announcement, setAnnouncement] = useState("");
    const route = useAsync(
        () =>
            origin && item
                ? getRoute({
                      origin: origin.coordinate,
                      destination: item.destination.coordinate,
                      profile: preferences.profile,
                      weights: null,
                  })
                : Promise.resolve(null),
        [id, origin?.coordinate.lat, origin?.coordinate.lon, preferences.profile],
    );

    if (!origin || !item) {
        return <Navigate to="/" replace state={{ notice: NO_SEARCH_NOTICE }} />;
    }

    const data = route.data;
    const variant = data ? data[kind] : null;
    const other = data ? data[kind === "healthy" ? "direct" : "healthy"] : null;
    const pois = variant ? poiSummary(variant) : [];

    return (
        <section className="container page route-page gomad-component gomad-route-view" aria-labelledby="ruta-titulo">
            <Link to={`/resultados/${encodeURIComponent(id)}`} className="back-button gomad-action gomad-action-back-to-recommendation">
                <Icon name="arrow_left" />
                Volver al detalle
            </Link>

            <PageHeading className="view-title" id="ruta-titulo">
                {`Ruta a ${item.destination.name}`}
            </PageHeading>

            <fieldset className="seg">
                <legend className="sr-only">Variante de ruta</legend>
                {VARIANTS.map((v) => (
                    <label key={v.kind} className={`seg__option gomad-option gomad-option-route-variant-${v.kind}`}>
                        <input
                            type="radio"
                            className={`gomad-field gomad-field-route-variant-${v.kind}`}
                            name="variante"
                            value={v.kind}
                            checked={kind === v.kind}
                            onChange={() => {
                                setKind(v.kind);
                                setAnnouncement(`Mostrando la ${v.label.toLowerCase()}`);
                            }}
                        />
                        <span>
                            {v.label}
                            <small>{v.hint}</small>
                        </span>
                    </label>
                ))}
            </fieldset>

            <p className="sr-only" role="status" aria-live="polite">
                {route.status === "loading"
                    ? "Calculando la ruta…"
                    : announcement ||
                      (variant
                          ? `Ruta calculada: ${formatDistance(variant.distance_m)}, ${formatMinutes(variant.duration_min)}.`
                          : "")}
            </p>

            {route.status === "loading" && !data && <p className="muted">Calculando la ruta…</p>}
            {route.status === "error" && (
                <ErrorMessage message="No se pudo calcular la ruta." onRetry={route.reload} />
            )}

            {data && variant && (
                <>
                    {variant.approximate && (
                        <p className="notice notice--warn" role="note">
                            Ruta aproximada en línea recta: no hay red peatonal en esta zona.
                        </p>
                    )}
                    {data.warnings.length > 0 && (
                        <div className="notice notice--info" role="note">
                            <ul role="list">
                                {data.warnings.map((w) => (
                                    <li key={w}>{w}</li>
                                ))}
                            </ul>
                        </div>
                    )}

                    <div className="route-layout">
                        <div className="route-map">
                            <MapView
                                className="map-view--block"
                                explore
                                origin={origin.coordinate}
                                route={variant.geometry}
                                secondaryRoute={other?.geometry}
                                markers={[
                                    {
                                        id: item.destination.id,
                                        number: 1,
                                        name: item.destination.name,
                                        coordinate: item.destination.coordinate,
                                        kind: destinationKind(item.destination.type, search?.activity),
                                    },
                                ]}
                                selectedId={item.destination.id}
                            />
                            <ul role="list" className="route-legend" aria-label="Leyenda del mapa">
                                <li>
                                    <span className="route-legend__line" aria-hidden="true" />
                                    Ruta elegida
                                </li>
                                <li>
                                    <span className="route-legend__line route-legend__line--secondary" aria-hidden="true" />
                                    La otra ruta
                                </li>
                            </ul>
                        </div>

                        <div className="route-info panel">
                            <ul role="list" className="route-metrics" aria-label="Resumen de la ruta">
                                <li>
                                    <span className="route-metrics__label"><Icon name="route" />Distancia</span>
                                    <strong>{formatDistance(variant.distance_m)}</strong>
                                </li>
                                <li>
                                    <span className="route-metrics__label"><Icon name="calendar_clock" />Tiempo estimado</span>
                                    <strong>{formatMinutes(variant.duration_min)}</strong>
                                </li>
                                <li>
                                    <span className="route-metrics__label"><Icon name="eco" />Zonas verdes</span>
                                    <strong>{variant.green_pct === null ? "sin datos" : `${Math.round(variant.green_pct)} %`}</strong>
                                </li>
                                <li>
                                    <span>Junto a tráfico intenso</span>
                                    <strong>{variant.traffic_m > 0 ? formatDistance(variant.traffic_m) : "Ningún tramo"}</strong>
                                </li>
                                <li>
                                    <span className="route-metrics__label"><Icon name="mountain" />Desnivel</span>
                                    <strong className="route-metrics__nodata">sin datos de desnivel</strong>
                                </li>
                            </ul>

                            <h2 className="panel__title">En el camino</h2>
                            <ul role="list" className="route-pois" aria-label="En la ruta">
                                {pois.length > 0 ? (
                                    pois.map((p) => <li key={p}>{p}</li>)
                                ) : (
                                    <li>Sin fuentes, bancos ni desfibriladores registrados en esta ruta.</li>
                                )}
                            </ul>

                            <h2 className="panel__title">La ruta en texto</h2>
                            <p className="route-description">{variant.description}</p>
                        </div>
                    </div>

                    <section className="route-sources" aria-labelledby="fuentes-ruta">
                        <h2 className="panel__title" id="fuentes-ruta">
                            De dónde salen estos datos
                        </h2>
                        <SourceList sources={data.sources} label="Fuentes de la ruta" />
                    </section>
                </>
            )}
        </section>
    );
}
