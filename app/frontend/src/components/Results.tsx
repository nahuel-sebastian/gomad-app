import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import type { Recommendation } from "../api/types";
import { ApiError } from "../data/errors";
import { recommend } from "../data/recommend";
import { useAsync } from "../data/useAsync";
import { formatDistance, formatHour, formatMinutes, formatScore } from "../lib/format";
import { DESTINATION_TYPE_LABELS, verdictFor } from "../lib/labels";
import { buildRecommendRequest, preferencesKey } from "../lib/request";
import { NO_SEARCH_NOTICE } from "../lib/texts";
import { useAppState } from "../state/context";
import Chip, { AqiChip } from "./Chip";
import ErrorMessage from "./ErrorMessage";
import MapView from "./MapView";
import PageHeading from "./PageHeading";
import PreferencesDialog from "./PreferencesDialog";

function ResultCard({ item, index }: { item: Recommendation; index: number }) {
    const verdict = verdictFor(item.score);
    const now = item.hours[0];
    const green = item.factors.find((f) => f.factor === "green");
    const showBest = item.best_hour !== null && item.best_hour !== now?.hour;

    return (
        <li>
            <Link to={`/resultados/${encodeURIComponent(item.destination.id)}`} className="result-card">
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
                            // el texto lo manda la API; el front no pone cortes propios sobre el valor
                            <Chip tone={green.value === null ? "nodata" : "info"} icon="park">
                                {green.value === null ? "Verde: sin datos" : green.text}
                            </Chip>
                        )}
                    </span>

                    {showBest && <span className="result-card__best">Mejor a las {formatHour(item.best_hour!)}</span>}
                </span>

                <span className="result-card__score-wrap">
                    <span className={`score-badge score-badge--${verdict.tone}`} aria-hidden="true">
                        {formatScore(item.score)}
                    </span>
                    <span className={`score-verdict score-verdict--${verdict.tone}`} aria-hidden="true">
                        {verdict.text}
                    </span>
                    <span className="sr-only">
                        Nota {formatScore(item.score)} sobre 10, {verdict.text.toLowerCase()}
                    </span>
                </span>
            </Link>
        </li>
    );
}

export default function Results() {
    const navigate = useNavigate();
    const { origin, search, preferences, setResults, setMedicalDisclaimer } = useAppState();
    const [isSheetExpanded, setIsSheetExpanded] = useState(false);
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
    const adjust = (
        <PreferencesDialog
            trigger={
                <button type="button" className="button">
                    Ajustar preferencias
                </button>
            }
        />
    );

    return (
        <section className="results-screen" aria-labelledby="resultados-titulo">
            <div className="results-desktop-toolbar">
                <button className="back-button" type="button" onClick={() => navigate("/")}>
                    <svg
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        aria-hidden="true">
                        <path d="M15 6l-6 6 6 6" />
                    </svg>
                    Volver
                </button>

                <div className="results-filters">
                    <PreferencesDialog
                        trigger={
                            <button className="filter-button" type="button">
                                <svg
                                    width="18"
                                    height="18"
                                    viewBox="0 0 24 24"
                                    fill="none"
                                    stroke="currentColor"
                                    strokeWidth="2"
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    aria-hidden="true">
                                    <path d="M4 5h16M7 12h10M10 19h4" />
                                </svg>
                                Ajustar
                            </button>
                        }
                    />
                </div>
            </div>

            <div className="results-layout">
                <div
                    ref={sheetRef}
                    className={`results-sheet${
                        isSheetExpanded ? " results-sheet--expanded" : ""
                    }`}
                    onFocus={(event) => {
                        // solo al llegar con el foco a un resultado (ni el asa ni el h1)
                        if ((event.target as HTMLElement).closest(".results-list")) {
                            setIsSheetExpanded(true);
                        }
                    }}
                    onPointerDown={(event) => {
                        // BLOQUEO EN DESKTOP: Ignoramos el drag si la pantalla es ancha
                        if (window.innerWidth >= 768) return;

                        // Evitar que al hacer scroll dentro del modal se mueva el contenedor entero
                        const scrollContainer =
                            event.currentTarget.querySelector(
                                ".results-sheet__scroll",
                            );

                        if (
                            scrollContainer instanceof HTMLElement &&
                            scrollContainer.scrollTop > 0
                        ) {
                            return;
                        }

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
                        className="results-sheet__handle"
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
                        <div className="container view-header">
                            <PageHeading className="view-title" id="resultados-titulo">
                                {title}
                            </PageHeading>
                            <p className="view-subtitle">
                                Las mejores opciones cerca de {origin.municipality} · datos de ejemplo
                            </p>
                        </div>

                        <div className="container results-body">
                            <p className="sr-only" role="status" aria-live="polite">
                                {announcement}
                            </p>

                            {first.status === "loading" && !first.data && (
                                <ul className="results-skeleton" aria-hidden="true">
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

                            {first.data && first.data.warnings.length > 0 && (
                                <div className="notice notice--warn" role="note">
                                    <ul>
                                        {first.data.warnings.map((w) => (
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
                                <ol
                                    ref={listRef}
                                    className="results-list"
                                    aria-label="Resultados"
                                    aria-busy={stale ? true : undefined}>
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
                                    className="button button--full"
                                    onClick={() => !loadingMore && loadMore()}
                                    aria-disabled={loadingMore}>
                                    <span>{loadingMore ? "Cargando…" : "Ver más opciones"}</span>
                                </button>
                            )}

                            {first.data && <p className="results-disclaimer">{first.data.medical_disclaimer}</p>}
                        </div>
                    </div>
                </div>

                <MapView
                    className="map-demo"
                    origin={origin.coordinate}
                    markers={items.map((item, i) => ({
                        id: item.destination.id,
                        number: i + 1,
                        name: item.destination.name,
                        coordinate: item.destination.coordinate,
                    }))}
                />
            </div>
        </section>
    );
}
