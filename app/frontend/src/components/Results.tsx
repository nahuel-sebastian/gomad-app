import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import type { Recommendation } from "../api/types";
import { ApiError } from "../data/errors";
import { BROWSER_LOCATION_LABEL, municipalityAt } from "../data/geolocation";
import { distanceM, LIVE_OFFER_DISTANCE_M, useLivePosition } from "../data/livePosition";
import { recommend } from "../data/recommend";
import { useAsync } from "../data/useAsync";
import { formatDistance, formatHour, formatMinutes, formatScore } from "../lib/format";
import { DESTINATION_TYPE_LABELS, verdictFor } from "../lib/labels";
import { buildRecommendRequest, preferencesKey } from "../lib/request";
import { NO_SEARCH_NOTICE } from "../lib/texts";
import { useAppState } from "../state/context";
import Chip, { AqiChip } from "./Chip";
import ErrorMessage from "./ErrorMessage";
import Icon from "./Icon";
import { destinationKind } from "./mapIcons";
import MapView from "./MapView";
import PageHeading from "./PageHeading";
import PreferencesForm from "./PreferencesForm";

function ResultCard({ item, index }: { item: Recommendation; index: number }) {
    const verdict = verdictFor(item.score);
    const now = item.hours[0];
    const green = item.factors.find((f) => f.factor === "green");
    const showBest = item.best_hour !== null && item.best_hour !== now?.hour;

    return (
        <li className="gomad-component gomad-result-card">
            <Link to={`/resultados/${encodeURIComponent(item.destination.id)}`} className="result-card gomad-action gomad-action-open-recommendation">
                <span className="result-card__number" aria-hidden="true">
                    {index + 1}
                </span>

                <span className="result-card__content">
                    <span className="result-card__title">{item.destination.name}</span>
                    <span className="result-card__meta">
                        {DESTINATION_TYPE_LABELS[item.destination.type]} · {formatDistance(item.distance_m)} ·{" "}
                        {formatMinutes(item.duration_min)} a pie
                    </span>

                    {item.indoor_alternative && (
                        <span className="result-card__alt">
                            <strong>Alternativa cubierta</strong>
                            <span>{item.explanation}</span>
                        </span>
                    )}

                    <span className="chips chips--small">
                        {item.destination.covered ? (
                            <Chip tone="info" icon="roofing">
                                Cubierta
                            </Chip>
                        ) : (
                            now && (
                                <Chip tone={now.temperature_c === null ? "nodata" : now.outdoor_ok === false ? "bad" : "good"} icon="thermostat">
                                    {now.temperature_c === null ? "Temperatura: sin datos" : `${now.temperature_c} °C ahora`}
                                </Chip>
                            )
                        )}
                        {now && <AqiChip category={now.aqi_category} />}
                        {green && (
                            // La API incluye el porcentaje en el texto del factor verde.
                            <Chip tone={green.value === null ? "nodata" : "good"} icon="park">
                                {green.value === null
                                    ? "Verde: sin datos"
                                    : green.text.replace(/^Verde:\s*/, "").replace(/\s*%\s+de zona verde alrededor\.?$/, "% zona verde")}
                            </Chip>
                        )}
                    </span>

                    {showBest && <span className="result-card__best">Mejor a las {formatHour(item.best_hour!)}</span>}
                </span>

                <span className="result-card__score-wrap">
                    <span className={`score-badge score-badge--${verdict.tone}`} aria-hidden="true">
                        {formatScore(item.score)}
                    </span>
                    <span className="sr-only">
                        Nota {formatScore(item.score)} sobre 10, {verdict.text.toLowerCase()}
                    </span>
                </span>
                <span className={`score-verdict score-verdict--${verdict.tone}`} aria-hidden="true">
                    {verdict.text}
                </span>
            </Link>
        </li>
    );
}

export default function Results() {
    const navigate = useNavigate();
    const { origin, search, preferences, setResults, setMedicalDisclaimer, setOrigin } = useAppState();
    // «Estas aqui» en tiempo real (C2): solo si la ubicacion vino del GPS o el permiso ya estaba dado
    const live = useLivePosition(origin?.label === BROWSER_LOCATION_LABEL);
    const movedM = live && origin ? distanceM(live, origin.coordinate) : 0;
    // no se recalcula solo: se ofrece buscar desde la nueva posicion
    const searchFromHere = async () => {
        if (!live || !origin) return;
        const place = await municipalityAt(live.lat, live.lon);
        setOrigin({
            label: BROWSER_LOCATION_LABEL,
            municipality: place?.name ?? origin.municipality,
            ine_code: place?.ine_code ?? origin.ine_code,
            coordinate: live,
            precision: "address",
        });
    };
    const [isSheetExpanded, setIsSheetExpanded] = useState(false);
    const [isAdjusting, setIsAdjusting] = useState(false);
    const sheetRef = useRef<HTMLDivElement>(null);
    const dragStartY = useRef<number | null>(null);
    const didDrag = useRef(false);

    const activity = search?.activity ?? null;
    const key = preferencesKey(activity, preferences, origin?.coordinate ?? null);
    const first = useAsync(
        () =>
            origin && search
                ? recommend(buildRecommendRequest(origin.coordinate, activity, preferences))
                : Promise.resolve(null),
        [key],
    );
    const warnings = first.data?.warnings.some((warning) =>
        warning.startsWith("Ahora no se recomienda actividad al aire libre en la ventana elegida"),
    )
        ? ["Ahora no se recomienda actividad al aire libre en la ventana elegida. Prueba otra franja."]
        : first.data?.warnings ?? [];
    // paginas de «Ver mas opciones», se vacian al cambiar la peticion
    const [more, setMore] = useState<{ key: string; items: Recommendation[]; hasMore: boolean } | null>(null);
    const [loadingMore, setLoadingMore] = useState(false);
    const [moreFailed, setMoreFailed] = useState(false);
    // tras «Ver mas», el foco va al primer resultado nuevo
    const [focusIndex, setFocusIndex] = useState<number | null>(null);
    const listRef = useRef<HTMLOListElement>(null);

    useEffect(() => {
        if (focusIndex === null) return;
        listRef.current?.querySelectorAll<HTMLAnchorElement>("a")[focusIndex]?.focus();
        setFocusIndex(null);
    }, [focusIndex]);
    const extra = more?.key === key ? more : null;

    const items = [...(first.data?.results ?? []), ...(extra?.items ?? [])];
    const hasMore = extra ? extra.hasMore : (first.data?.has_more ?? false);
    // destino resaltado en el mapa: el de la tarjeta con foco o bajo el puntero (RF-11)
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const cardIndex = (target: EventTarget) =>
        [...(listRef.current?.children ?? [])].findIndex((li) => li.contains(target as Node));
    const selectCard = (target: EventTarget) => {
        const id = items[cardIndex(target)]?.destination.id;
        if (id && id !== selectedId) setSelectedId(id);
    };
    // pulsar un marcador lo selecciona y lleva el foco a su tarjeta
    const focusCard = (id: string) => {
        setSelectedId(id);
        const link = listRef.current?.children[items.findIndex((i) => i.destination.id === id)]?.querySelector("a");
        link?.scrollIntoView({ block: "nearest" });
        link?.focus();
    };

    useEffect(() => {
        if (first.data) {
            setResults(items);
            setMedicalDisclaimer(first.data.medical_disclaimer);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [first.data, extra]);

    if (!origin || !search) {
        return <Navigate to="/" replace state={{ notice: NO_SEARCH_NOTICE }} />;
    }

    const loadMore = async () => {
        setLoadingMore(true);
        setMoreFailed(false);
        try {
            const page = await recommend(
                buildRecommendRequest(origin.coordinate, activity, preferences, { offset: items.length }),
            );
            setMore({ key, items: [...(extra?.items ?? []), ...page.results], hasMore: page.has_more });
            if (page.results.length > 0) setFocusIndex(items.length);
        } catch {
            setMoreFailed(true);
        } finally {
            setLoadingMore(false);
        }
    };

    const title = activity === null ? "Planes para ti hoy" : `${search.label ?? "Actividad"} cerca de ti`;
    const invalid = first.error instanceof ApiError && first.error.status === 422;
    let announcement = "";
    if (first.status === "loading" || loadingMore) announcement = "Buscando los mejores sitios…";
    else if (first.data) announcement = items.length === 0 ? "Ningún resultado." : `${items.length} resultados actualizados`;
    const stale = first.status === "loading" && first.data;
    const openPreferences = () => {
        setIsSheetExpanded(true);
        setIsAdjusting(true);
        const scroll = sheetRef.current?.querySelector(".results-sheet__scroll");
        if (scroll instanceof HTMLElement) scroll.scrollTop = 0;
    };
    const adjust = <button type="button" className="button gomad-action gomad-action-adjust-preferences" onClick={openPreferences}>Ajustar preferencias</button>;

    return (
        <section className="results-screen gomad-component gomad-results" aria-labelledby="resultados-titulo">
            <div className="results-desktop-toolbar">
                <button className="back-button gomad-action gomad-action-go-home" type="button" onClick={() => navigate("/")}>
                    <Icon name="arrow_left" />
                    Volver
                </button>

            </div>

            <div className="results-layout">
                <div
                    ref={sheetRef}
                    className={`results-sheet${
                        isSheetExpanded ? " results-sheet--expanded" : ""
                    }${isAdjusting ? " results-sheet--adjusting" : ""}`}
                    onFocus={(event) => {
                        // solo al llegar con el foco a un resultado (ni el asa ni el h1)
                        if ((event.target as HTMLElement).closest(".results-list")) {
                            setIsSheetExpanded(true);
                        }
                    }}
                    onPointerDown={(event) => {
                        if (window.innerWidth >= 768) return;
                        if (!(event.target as HTMLElement).closest(".results-sheet__handle")) return;

                        dragStartY.current = event.clientY;
                        didDrag.current = false;
                    }}
                    onPointerMove={(event) => {
                        if (dragStartY.current === null || !sheetRef.current) {
                            return;
                        }

                        const delta = event.clientY - dragStartY.current;

                        // la captura solo empieza al arrastrar: un toque sigue siendo un clic en el enlace
                        if (Math.abs(delta) > 8 && !didDrag.current) {
                            didDrag.current = true;
                            event.currentTarget.setPointerCapture(event.pointerId);
                        }

                        const sheetHeight = sheetRef.current.offsetHeight;
                        const maxOffset = Math.max(sheetHeight - 164, 0);
                        const baseOffset = isSheetExpanded ? 0 : maxOffset;

                        const offset = Math.min(
                            maxOffset,
                            Math.max(0, baseOffset + delta),
                        );

                        sheetRef.current.style.transform = `translateY(${offset}px)`;
                    }}
                    onPointerUp={(event) => {
                        if (dragStartY.current !== null) {
                            const delta = event.clientY - dragStartY.current;

                            if (Math.abs(delta) > 40) {
                                setIsSheetExpanded(delta < 0);
                            }
                        }

                        dragStartY.current = null;

                        if (sheetRef.current) {
                            sheetRef.current.style.transform = "";
                        }
                    }}
                    onPointerCancel={() => {
                        dragStartY.current = null;

                        if (sheetRef.current) {
                            sheetRef.current.style.transform = "";
                        }
                    }}>
                    <button
                        className="results-sheet__handle gomad-action gomad-action-toggle-results-sheet"
                        type="button"
                        aria-label={
                            isSheetExpanded
                                ? "Ocultar resultados"
                                : "Mostrar resultados"
                        }
                        aria-expanded={isSheetExpanded}
                        onClick={() => {
                            if (didDrag.current) {
                                didDrag.current = false;
                                return;
                            }

                            setIsSheetExpanded((expanded) => !expanded);
                        }}>
                        <span aria-hidden="true" />
                    </button>

                    <div className="results-sheet__scroll">
                        {isAdjusting ? (
                            <div className="container results-preferences">
                                <div className="results-preferences__header">
                                    <div className="results-heading-copy">
                                        <PageHeading className="view-title" id="resultados-titulo">Tus preferencias</PageHeading>
                                        <p className="view-subtitle">Los cambios se aplican al momento; los resultados se recalculan solos.</p>
                                    </div>
                                    <button type="button" className="button button--primary gomad-action gomad-action-close-preferences" onClick={() => setIsAdjusting(false)}>Listo</button>
                                </div>
                                <PreferencesForm weightsOnly />
                            </div>
                        ) : (
                        <>
                        <div className="container view-header">
                            <div className="results-heading-copy">
                                <PageHeading className="view-title" id="resultados-titulo">
                                    {title}
                                </PageHeading>
                                <p className="view-subtitle">
                                    Las mejores opciones cerca de {origin.municipality}
                                </p>
                            </div>
                            <button className="filter-button results-mobile-adjust gomad-action gomad-action-adjust-preferences" type="button" aria-label="Ajustar preferencias" onClick={openPreferences}>
                                <Icon name="settings" />
                            </button>
                        </div>

                        <div className="container results-body">
                            <p className="sr-only" role="status" aria-live="polite">
                                {announcement}
                            </p>

                            {first.status === "loading" && !first.data && (
                                <ul role="list" className="results-skeleton" aria-hidden="true">
                                    <li />
                                    <li />
                                    <li />
                                </ul>
                            )}

                            {first.status === "error" &&
                                (invalid ? (
                                    <ErrorMessage message="Tus preferencias no son válidas para buscar. Revísalas e inténtalo de nuevo.">
                                        {adjust}
                                    </ErrorMessage>
                                ) : (
                                    <ErrorMessage
                                        message="No se pudieron cargar las recomendaciones."
                                        onRetry={first.reload}
                                    />
                                ))}

                            {warnings.length > 0 && (
                                <div className="notice notice--warn" role="note">
                                    <ul role="list">
                                        {warnings.map((w) => (
                                            <li key={w}>{w}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {first.data && items.length === 0 && (
                                <div className="notice notice--info">
                                    <p>
                                        Ningún destino encaja con tus preferencias. Prueba a ampliar la distancia
                                        máxima o a cambiar entre interior y exterior.
                                    </p>
                                    <div className="notice__actions">{adjust}</div>
                                </div>
                            )}

                            {stale && items.length > 0 && <p className="results-updating">Actualizando…</p>}

                            {items.length > 0 && (
                                <ol role="list"
                                    ref={listRef}
                                    className="results-list"
                                    aria-label="Resultados"
                                    aria-busy={stale ? true : undefined}
                                    onFocus={(e) => selectCard(e.target)}
                                    onMouseOver={(e) => selectCard(e.target)}>
                                    {items.map((item, i) => (
                                        <ResultCard key={item.destination.id} item={item} index={i} />
                                    ))}
                                </ol>
                            )}

                            {moreFailed && (
                                <ErrorMessage message="No se pudieron cargar más opciones." onRetry={loadMore} />
                            )}

                            {hasMore && first.status === "success" && !moreFailed && (
                                <button
                                    type="button"
                                    className="button button--full gomad-action gomad-action-show-more-results"
                                    onClick={() => !loadingMore && loadMore()}
                                    aria-disabled={loadingMore}>
                                    <span>{loadingMore ? "Cargando…" : "Ver más opciones"}</span>
                                </button>
                            )}

                            {first.data && <p className="results-disclaimer">{first.data.medical_disclaimer}</p>}
                        </div>
                        </>
                        )}
                    </div>
                </div>

                <MapView
                    className="map-demo"
                    explore
                    live={live}
                    overlay={
                        movedM >= LIVE_OFFER_DISTANCE_M && (
                            <div className="map-live-offer" role="status">
                                <button type="button" className="button button--primary" onClick={searchFromHere}>
                                    {`Te has alejado ${formatDistance(movedM)}: buscar desde aquí`}
                                </button>
                            </div>
                        )
                    }
                    origin={origin.coordinate}
                    selectedId={selectedId}
                    onSelect={focusCard}
                    markers={items.map((item, i) => ({
                        id: item.destination.id,
                        number: i + 1,
                        name: item.destination.name,
                        coordinate: item.destination.coordinate,
                        kind: destinationKind(item.destination.type, activity),
                    }))}
                />
            </div>
        </section>
    );
}
