import { useRef, useState } from "react";
import { Link } from "react-router";
import type { LocationCandidate, PoiType, RouteResponse, RouteVariant } from "../api/types";
import { getRoute } from "../data/route";
import { formatDistance, formatMinutes } from "../lib/format";
import { poiCount } from "../lib/labels";
import { useAppState } from "../state/context";
import AddressField from "./AddressField";
import ErrorMessage from "./ErrorMessage";
import Icon from "./Icon";
import MapView from "./MapView";
import PageHeading from "./PageHeading";
import SourceList from "./SourceList";

// Ruta entre dos direcciones escritas (complementaria a /ruta/:id). Las direcciones son
// estado local: no cambian la ubicacion de Inicio. Las coordenadas solo van en el cuerpo
// de POST /route. El resumen copia el de RouteView (sin extraerlo, para no tocarlo).

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

type RouteState =
    | { status: "idle" }
    | { status: "same" }
    | { status: "loading" }
    | { status: "error" }
    | { status: "done"; data: RouteResponse; from: LocationCandidate; to: LocationCandidate };

export default function RouteBetween() {
    const { preferences } = useAppState();
    const [from, setFrom] = useState<LocationCandidate | null>(null);
    const [to, setTo] = useState<LocationCandidate | null>(null);
    const [route, setRoute] = useState<RouteState>({ status: "idle" });
    const [kind, setKind] = useState<"healthy" | "direct">("healthy");
    const [announcement, setAnnouncement] = useState("");
    const [legendSlot, setLegendSlot] = useState<HTMLElement | null>(null);
    const callRef = useRef(0);

    // cambiar una direccion invalida la ruta mostrada
    const change = (setter: (c: LocationCandidate | null) => void) => (c: LocationCandidate | null) => {
        callRef.current += 1;
        setter(c);
        setRoute({ status: "idle" });
        setAnnouncement("");
    };

    const calculate = async () => {
        if (!from || !to) return;
        const call = ++callRef.current;
        setAnnouncement("");
        if (from.coordinate.lat === to.coordinate.lat && from.coordinate.lon === to.coordinate.lon) {
            setRoute({ status: "same" });
            return;
        }
        setRoute({ status: "loading" });
        try {
            const data = await getRoute({
                origin: from.coordinate,
                destination: to.coordinate,
                profile: preferences.profile,
                weights: null,
            });
            if (call !== callRef.current) return;
            setKind("healthy");
            setRoute({ status: "done", data, from, to });
        } catch {
            if (call === callRef.current) setRoute({ status: "error" });
        }
    };

    const data = route.status === "done" ? route.data : null;
    const variant = data ? data[kind] : null;
    const other = data ? data[kind === "healthy" ? "direct" : "healthy"] : null;
    const pois = variant ? poiSummary(variant) : [];

    return (
        <section className={`container page route-page gomad-component gomad-route-between${data && variant ? " route-page--ready" : ""}`} aria-labelledby="trayecto-titulo">
            <Link to="/" className="back-button gomad-action gomad-action-back-to-home">
                <Icon name="arrow_left" />
                Volver
            </Link>

            {route.status === "done" && variant && (
                <>
                    <div className="route-map">
                        <MapView
                            className="map-view--block"
                            explore
                            origin={route.from.coordinate}
                            route={variant.geometry}
                            secondaryRoute={other?.geometry}
                            legendSlot={legendSlot}
                            markers={[
                                {
                                    id: "trayecto-fin",
                                    number: 1,
                                    name: route.to.label,
                                    coordinate: route.to.coordinate,
                                },
                            ]}
                            selectedId="trayecto-fin"
                        />
                    </div>
                    <ul role="list" className="route-legend" aria-label="Leyenda del mapa">
                        <li><span className="route-legend__line" aria-hidden="true" />Ruta seleccionada</li>
                        <li><span className="route-legend__line route-legend__line--secondary" aria-hidden="true" />Ruta alternativa</li>
                    </ul>
                </>
            )}

            <div className="route-heading">
                <PageHeading className="view-title" id="trayecto-titulo">
                    Ruta entre dos direcciones
                </PageHeading>
                <div className="route-legend-slot" ref={setLegendSlot} />
            </div>

            <div className="panel route-between__form">
                <AddressField label="Desde" value={from} onChange={change(setFrom)} allowCurrentLocation />
                <AddressField label="Hasta" value={to} onChange={change(setTo)} />
                <button
                    type="button"
                    className="button button--primary gomad-action gomad-action-calculate-route"
                    disabled={!from || !to || route.status === "loading"}
                    onClick={() => void calculate()}>
                    <Icon name="route" />
                    <span>Calcular ruta</span>
                </button>
            </div>

            {route.status === "same" && (
                <p className="notice notice--warn" role="alert">
                    El inicio y el final son el mismo punto.
                </p>
            )}

            {data && (
                <fieldset className="seg seg--routes">
                    <legend className="sr-only">Variante de ruta</legend>
                    {VARIANTS.map((v) => (
                        <label key={v.kind} className={`seg__option gomad-option gomad-option-route-variant-${v.kind}`}>
                            <input
                                type="radio"
                                className={`gomad-field gomad-field-route-variant-${v.kind}`}
                                name="variante-trayecto"
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
            )}

            <p className="sr-only" role="status" aria-live="polite">
                {route.status === "loading"
                    ? "Calculando la ruta…"
                    : announcement ||
                      (variant
                          ? `Ruta calculada: ${formatDistance(variant.distance_m)}, ${formatMinutes(variant.duration_min)}.`
                          : "")}
            </p>

            {route.status === "loading" && <p className="muted">Calculando la ruta…</p>}
            {route.status === "error" && (
                <ErrorMessage message="No se pudo calcular la ruta." onRetry={() => void calculate()} />
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

                    <section className="route-sources" aria-labelledby="fuentes-trayecto">
                        <h2 className="panel__title" id="fuentes-trayecto">
                            De dónde salen estos datos
                        </h2>
                        <SourceList sources={data.sources} label="Fuentes de la ruta" />
                    </section>
                </>
            )}
        </section>
    );
}
