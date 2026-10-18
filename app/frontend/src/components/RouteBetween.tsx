import { useEffect, useRef, useState, type FocusEvent, type PointerEvent } from "react";
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
import { useRouteNavigation } from "./RouteNavigation";
import SourceList from "./SourceList";

// Ruta entre dos direcciones escritas (complementaria a /ruta/:id). Las direcciones son
// estado local: no cambian la ubicacion de Inicio. Las coordenadas solo van en el cuerpo
// de POST /route. El resumen copia el de RouteView (sin extraerlo, para no tocarlo).
// Con la ruta calculada, la pantalla es como Resultados: mapa a pantalla completa y los
// detalles en una hoja que se sube y se baja (mismas clases; Results.tsx no se toca).

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

// alto de la hoja recogida que sigue a la vista al arrastrar (como Resultados)
const SHEET_PEEK_PX = 164;

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

// Hoja inferior arrastrable en movil: mismo gesto que la de Resultados (copiado, no extraido)
function useSheet() {
    const [expanded, setExpanded] = useState(false);
    const sheetRef = useRef<HTMLDivElement>(null);
    const dragStartY = useRef<number | null>(null);
    const didDrag = useRef(false);

    const reset = () => {
        dragStartY.current = null;
        if (sheetRef.current) sheetRef.current.style.transform = "";
    };

    return {
        expanded,
        setExpanded,
        sheetRef,
        onFocus: (event: FocusEvent<HTMLDivElement>) => {
            // al llegar con el foco al contenido (no al asa ni al h1), la hoja se abre
            if ((event.target as HTMLElement).closest(".results-body")) setExpanded(true);
        },
        onPointerDown: (event: PointerEvent<HTMLDivElement>) => {
            if (window.innerWidth >= 768) return;
            if (!(event.target as HTMLElement).closest(".results-sheet__handle")) return;
            dragStartY.current = event.clientY;
            didDrag.current = false;
        },
        onPointerMove: (event: PointerEvent<HTMLDivElement>) => {
            if (dragStartY.current === null || !sheetRef.current) return;
            const delta = event.clientY - dragStartY.current;
            // la captura solo empieza al arrastrar: un toque sigue siendo un clic en el asa
            if (Math.abs(delta) > 8 && !didDrag.current) {
                didDrag.current = true;
                event.currentTarget.setPointerCapture(event.pointerId);
            }
            const maxOffset = Math.max(sheetRef.current.offsetHeight - SHEET_PEEK_PX, 0);
            const offset = Math.min(maxOffset, Math.max(0, (expanded ? 0 : maxOffset) + delta));
            sheetRef.current.style.transform = `translateY(${offset}px)`;
        },
        onPointerUp: (event: PointerEvent<HTMLDivElement>) => {
            if (dragStartY.current !== null) {
                const delta = event.clientY - dragStartY.current;
                if (Math.abs(delta) > 40) setExpanded(delta < 0);
            }
            reset();
        },
        onPointerCancel: reset,
        toggle: () => {
            if (didDrag.current) {
                didDrag.current = false;
                return;
            }
            setExpanded((value) => !value);
        },
    };
}

export default function RouteBetween() {
    const { preferences } = useAppState();
    const [from, setFrom] = useState<LocationCandidate | null>(null);
    const [to, setTo] = useState<LocationCandidate | null>(null);
    const [route, setRoute] = useState<RouteState>({ status: "idle" });
    const [kind, setKind] = useState<"healthy" | "direct">("healthy");
    const [announcement, setAnnouncement] = useState("");
    // cada intento con el mismo punto vuelve a montar el aviso para que se anuncie otra vez
    const [sameTry, setSameTry] = useState(0);
    const callRef = useRef(0);
    const headingRef = useRef<HTMLDivElement>(null);
    const { expanded: sheetExpanded, setExpanded: setSheetExpanded, sheetRef, toggle: toggleSheet, ...sheetEvents } = useSheet();

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
            setSameTry((n) => n + 1);
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
            // la hoja empieza recogida: primero se ve la ruta en el mapa
            setSheetExpanded(false);
            setRoute({ status: "done", data, from, to });
        } catch {
            if (call === callRef.current) setRoute({ status: "error" });
        }
    };

    // volver al formulario conservando las direcciones
    const edit = () => {
        callRef.current += 1;
        setRoute({ status: "idle" });
        setAnnouncement("");
    };

    const done = route.status === "done" ? route : null;
    const showingRoute = done !== null;
    // el boton «Calcular ruta» o «Cambiar direcciones» desaparece al cambiar de vista: el foco va al h1
    useEffect(() => {
        headingRef.current?.querySelector("h1")?.focus();
    }, [showingRoute]);

    const data = done ? done.data : null;
    const variant = data ? data[kind] : null;
    const other = data ? data[kind === "healthy" ? "direct" : "healthy"] : null;
    const pois = variant ? poiSummary(variant) : [];
    // «Seguir mi ubicacion»: al empezar se recoge la hoja para ver el mapa
    const nav = useRouteNavigation(done ? variant : null, { onStart: () => setSheetExpanded(false) });

    const status = (
        <p className="sr-only" role="status" aria-live="polite">
            {route.status === "loading"
                ? "Calculando la ruta…"
                : announcement ||
                  (variant
                      ? `Ruta calculada: ${formatDistance(variant.distance_m)}, ${formatMinutes(variant.duration_min)}.`
                      : "")}
        </p>
    );

    const back = (
        <Link to="/" className="back-button gomad-action gomad-action-back-to-home">
            <Icon name="arrow_left" />
            Volver
        </Link>
    );

    if (!done || !data || !variant) {
        return (
            <>
                {status}
                <section className="container page route-page gomad-component gomad-route-between" aria-labelledby="trayecto-titulo">
                    {back}

                    <div className="route-heading" ref={headingRef}>
                        <PageHeading className="view-title" id="trayecto-titulo">
                            Ruta entre dos direcciones
                        </PageHeading>
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
                        <p key={sameTry} className="notice notice--warn" role="alert">
                            El inicio y el final son el mismo punto.
                        </p>
                    )}

                    {route.status === "loading" && <p className="muted">Calculando la ruta…</p>}
                    {route.status === "error" && (
                        <ErrorMessage message="No se pudo calcular la ruta." onRetry={() => void calculate()} />
                    )}
                </section>
            </>
        );
    }

    return (
        <>
            {status}
            <section className="results-screen gomad-results gomad-component gomad-route-between gomad-route-between--map" aria-labelledby="trayecto-titulo">
                <div className="results-desktop-toolbar">{back}</div>

                <div className="results-layout">
                    <div
                        ref={sheetRef}
                        className={`results-sheet${sheetExpanded ? " results-sheet--expanded" : ""}`}
                        onFocus={sheetEvents.onFocus}
                        onPointerDown={sheetEvents.onPointerDown}
                        onPointerMove={sheetEvents.onPointerMove}
                        onPointerUp={sheetEvents.onPointerUp}
                        onPointerCancel={sheetEvents.onPointerCancel}>
                        <button
                            className="results-sheet__handle gomad-action gomad-action-toggle-route-sheet"
                            type="button"
                            aria-label={sheetExpanded ? "Ocultar detalles de la ruta" : "Mostrar detalles de la ruta"}
                            aria-expanded={sheetExpanded}
                            onClick={toggleSheet}>
                            <span aria-hidden="true" />
                        </button>

                        <div className="results-sheet__scroll">
                            {/* al principio de la hoja: visible con la hoja recogida */}
                            <div className="container route-between__nav">{nav.controls}</div>
                            <div className="container view-header">
                                <div className="results-heading-copy" ref={headingRef}>
                                    <PageHeading className="view-title" id="trayecto-titulo">
                                        Ruta entre dos direcciones
                                    </PageHeading>
                                    <p className="view-subtitle">{`${done.from.label} → ${done.to.label}`}</p>
                                </div>
                            </div>

                            <div className="container results-body route-between__body">
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

                                <ul role="list" className="route-legend" aria-label="Leyenda del mapa">
                                    <li><span className="route-legend__line" aria-hidden="true" />Ruta seleccionada</li>
                                    <li><span className="route-legend__line route-legend__line--secondary" aria-hidden="true" />Ruta alternativa</li>
                                </ul>

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

                                <button type="button" className="button gomad-action gomad-action-edit-route-between" onClick={edit}>
                                    <Icon name="location_on" />
                                    <span>Cambiar direcciones</span>
                                </button>
                            </div>
                        </div>
                    </div>

                    <MapView
                        className="map-demo"
                        explore
                        live={nav.live}
                        follow={nav.follow}
                        onUserMove={nav.onUserMove}
                        origin={done.from.coordinate}
                        route={variant.geometry}
                        secondaryRoute={other?.geometry}
                        // sin boton de leyenda en esta pantalla (null = no se pinta)
                        legendSlot={null}
                        markers={[
                            {
                                id: "trayecto-fin",
                                number: 1,
                                name: done.to.label,
                                coordinate: done.to.coordinate,
                            },
                        ]}
                        selectedId="trayecto-fin"
                    />
                </div>
            </section>
        </>
    );
}
