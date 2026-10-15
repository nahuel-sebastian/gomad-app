import { useRef, useState } from "react";

interface ResultsProps {
    activity: string | null;
    onBack: () => void;
    onSelectResult: () => void;
}

export default function Results({
    activity,
    onBack,
    onSelectResult,
}: ResultsProps) {
    const [isSheetExpanded, setIsSheetExpanded] = useState(false);
    const sheetRef = useRef<HTMLDivElement>(null);
    const dragStartY = useRef<number | null>(null);
    const didDrag = useRef(false);

    // Datos extraídos de la imagen de referencia
    const results = [
        {
            id: 1,
            title: "Parque de la Alhóndiga",
            meta: "Parque · 1,8 km · 22 min a pie",
            score: "8,7",
            verdict: "Muy buena opción",
            tone: "good",
            chips: [
                { icon: "sun", label: "22 °C", tone: "good" },
                { icon: "leaf", label: "Aire bueno", tone: "good" },
                { icon: "car", label: "Bajo tráfico", tone: "good" },
            ],
        },
        {
            id: 2,
            title: "Parque de Castilla-La Mancha",
            meta: "Parque · 2,2 km · 26 min a pie",
            score: "8,0",
            verdict: "Buena opción",
            tone: "good",
            chips: [
                { icon: "sun", label: "22 °C", tone: "good" },
                { icon: "leaf", label: "Aire bueno", tone: "good" },
                { icon: "car", label: "Bajo tráfico", tone: "good" },
            ],
        },
        {
            id: 3,
            title: "Parque Lorenzo Azofra",
            meta: "Parque urbano · 1,2 km · 14 min a pie",
            score: "7,3",
            verdict: "Buena opción",
            tone: "warn",
            chips: [
                { icon: "sun", label: "22 °C", tone: "good" },
                { icon: "leaf", label: "Aire aceptable", tone: "warn" },
                { icon: "car", label: "Tráfico medio", tone: "warn" },
            ],
        },
    ];

    const title =
        activity === null ? "Planes para ti hoy" : `${activity} cerca de ti`;

    return (
        <section className="results-screen">
            <div className="results-desktop-toolbar">
                <button className="back-button" type="button" onClick={onBack}>
                    <svg
                        width="18"
                        height="18"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round">
                        <path d="M15 6l-6 6 6 6" />
                    </svg>
                    Volver
                </button>

                <div className="results-filters" aria-label="Filtros">
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
                        Filtros
                    </button>

                    <div className="results-filter-chips">
                        {[
                            "Cerca de ti",
                            "Aire bueno",
                            "Parques",
                            "Apto para caminar",
                            "Con sombra",
                            "Con fuentes",
                            "Sin tráfico",
                        ].map((filter) => (
                            <button
                                className="filter-chip"
                                type="button"
                                key={filter}>
                                {filter}
                            </button>
                        ))}
                    </div>
                </div>
            </div>

            <div className="results-layout">
                <div
                    ref={sheetRef}
                    className={`results-sheet${
                        isSheetExpanded ? " results-sheet--expanded" : ""
                    }`}
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
                        event.currentTarget.setPointerCapture(event.pointerId);
                    }}
                    onPointerMove={(event) => {
                        if (dragStartY.current === null || !sheetRef.current) {
                            return;
                        }

                        const delta = event.clientY - dragStartY.current;

                        if (Math.abs(delta) > 8) {
                            didDrag.current = true;
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
                            <h1 className="view-title">{title}</h1>
                            <p className="view-subtitle">
                                Las 3 mejores opciones en Getafe · datos de
                                ejemplo
                            </p>
                        </div>

                        <div className="container results-list">
                            {results.map((item) => (
                                <button
                                    key={item.id}
                                    type="button"
                                    className="result-card"
                                    onClick={onSelectResult}>
                                    <div className="result-card__number">
                                        {item.id}
                                    </div>

                                    <div className="result-card__content">
                                        <h2 className="result-card__title">
                                            {item.title}
                                        </h2>

                                        <p className="result-card__meta">
                                            {item.meta}
                                        </p>

                                        <div className="chips chips--small">
                                            {item.chips.map((chip, idx) => (
                                                <span
                                                    key={idx}
                                                    className={`chip chip--${chip.tone}`}>
                                                    {chip.label}
                                                </span>
                                            ))}
                                        </div>
                                    </div>

                                    <div className="result-card__score-wrap">
                                        <div
                                            className={`score-badge score-badge--${item.tone}`}>
                                            {item.score}
                                        </div>

                                        <span
                                            className={`score-verdict score-verdict--${item.tone}`}>
                                            {item.verdict}
                                        </span>
                                    </div>
                                </button>
                            ))}

                            <button
                                type="button"
                                className="button button--full">
                                <span>Ver más opciones</span>
                            </button>
                        </div>
                    </div>
                </div>

                <div className="map-demo"></div>
            </div>
        </section>
    );
}
