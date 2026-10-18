import { useState } from "react";
import { Link, Navigate, useParams } from "react-router";
import type { PoiType, RouteVariant } from "../api/types";
import { BROWSER_LOCATION_LABEL } from "../data/geolocation";
import { useLivePosition } from "../data/livePosition";
import { getRoute } from "../data/route";
import { useAsync } from "../data/useAsync";
import { formatDestinationName, formatDistance, formatMinutes } from "../lib/format";
import { poiCount } from "../lib/labels";
import { NO_SEARCH_NOTICE } from "../lib/texts";
import { useAppState } from "../state/context";
import ErrorMessage from "./ErrorMessage";
import Icon from "./Icon";
import { destinationKind } from "./mapIcons";
import MapView from "./MapView";
import PageHeading from "./PageHeading";
import { useRouteNavigation } from "./RouteNavigation";
import SourceList from "./SourceList";

const VARIANTS = [
    { kind: "healthy", label: "Ruta recomendada", hint: "más verde y menos tráfico" },
    { kind: "direct", label: "Ruta directa", hint: "la más corta" },
] as const;

// PDI que se resumen en la ruta (RF-13), en este orden
const POI_ORDER: PoiType[] = ["fountain", "bench", "aed", "dog_area", "playground", "bin", "toilet", "outdoor_gym", "supermarket"];

const POI_ICONS: Record<PoiType, string> = {
    fountain: "water",
    bench: "bench",
    aed: "ecg",
    dog_area: "pets",
    playground: "playground",
    bin: "recycle",
    toilet: "wc",
    outdoor_gym: "outdoor_gym",
    supermarket: "shopping_cart",
};

function poiSummary(variant: RouteVariant): { type: PoiType; label: string }[] {
    const counts = new Map<PoiType, number>();
    variant.pois.forEach((p) => counts.set(p.type, (counts.get(p.type) ?? 0) + 1));
    return POI_ORDER.filter((t) => counts.has(t)).map((t) => ({ type: t, label: poiCount(t, counts.get(t)!) }));
}

export default function RouteView() {
    const { id = "" } = useParams();
    const { origin, results, preferences } = useAppState();
    // «Estas aqui» en tiempo real mientras se ve la ruta (C2); no recalcula la ruta
    const live = useLivePosition(origin?.label === BROWSER_LOCATION_LABEL);
    const item = results.find((r) => r.destination.id === id);
    const [kind, setKind] = useState<"healthy" | "direct">("healthy");
    const [announcement, setAnnouncement] = useState("");
    const [legendSlot, setLegendSlot] = useState<HTMLElement | null>(null);
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

    // «Seguir mi ubicacion» (navegacion): solo al pulsar; mientras, el «Estas aqui» automatico de arriba
    const nav = useRouteNavigation(route.data ? route.data[kind] : null);

    if (!origin || !item) {
        return <Navigate to="/" replace state={{ notice: NO_SEARCH_NOTICE }} />;
    }

    const data = route.data;
    const variant = data ? data[kind] : null;
    const other = data ? data[kind === "healthy" ? "direct" : "healthy"] : null;
    const pois = variant ? poiSummary(variant) : [];

    return (
        <section className={`container page route-page gomad-component gomad-route-view${data && variant ? " route-page--ready" : ""}`} aria-labelledby="ruta-titulo">
            <Link to={`/resultados/${encodeURIComponent(id)}`} className="back-button gomad-action gomad-action-back-to-recommendation">
                <Icon name="arrow_left" />
                Volver
            </Link>

            {data && variant && (
                <>
                    <div className="route-map">
                        <MapView
                            className="map-view--block"
                            explore
                            live={nav.live ?? live}
                            follow={nav.follow}
                            onUserMove={nav.onUserMove}
                            origin={origin.coordinate}
                            route={variant.geometry}
                            secondaryRoute={other?.geometry}
                            legendSlot={legendSlot}
                            markers={[
                                {
                                    id: item.destination.id,
                                    number: 1,
                                    name: formatDestinationName(item.destination.name),
                                    coordinate: item.destination.coordinate,
                                    kind: destinationKind(item.destination.type),
                                },
                            ]}
                            selectedId={item.destination.id}
                        />
                    </div>
                    <ul role="list" className="route-legend" aria-label="Leyenda del mapa">
                        <li><span className="route-legend__line" aria-hidden="true" />Ruta seleccionada</li>
                        <li><span className="route-legend__line route-legend__line--secondary" aria-hidden="true" />Ruta alternativa</li>
                    </ul>
                    {nav.controls}
                </>
            )}

            <div className="route-heading">
                <PageHeading className="view-title" id="ruta-titulo">
                    {`Ruta a ${formatDestinationName(item.destination.name)}`}
                </PageHeading>
                <div className="route-legend-slot" ref={setLegendSlot} />
            </div>

            <fieldset className="seg seg--routes">
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
                            <strong>{v.label}</strong>
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

                    <div className="route-info">
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
                                    <strong>{variant.green_pct === null ? "Sin datos" : `${Math.round(variant.green_pct)} %`}</strong>
                                </li>
                                <li>
                                    <span className="route-metrics__label"><Icon name="traffic" />Junto a tráfico intenso</span>
                                    <strong>{variant.traffic_m > 0 ? formatDistance(variant.traffic_m) : "Ningún tramo"}</strong>
                                </li>
                                <li>
                                    <span className="route-metrics__label"><Icon name="mountain" />Desnivel</span>
                                    <strong className="route-metrics__nodata">Sin datos de desnivel</strong>
                                </li>
                            </ul>

                            <div className="route-details panel">
                                <section className="route-details__section">
                                    <h2 className="panel__title">En el camino</h2>
                                    <ul role="list" className="route-pois" aria-label="En la ruta">
                                        {pois.length > 0 ? (
                                            pois.map((p) => <li key={p.type}><Icon name={POI_ICONS[p.type]} />{p.label}</li>)
                                        ) : (
                                            <li className="route-pois__empty">Sin fuentes, bancos ni desfibriladores registrados en esta ruta.</li>
                                        )}
                                    </ul>
                                </section>

                                <section className="route-details__section">
                                    <h2 className="panel__title">La ruta en texto</h2>
                                    <p className="route-description">{variant.description}</p>
                                </section>
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
