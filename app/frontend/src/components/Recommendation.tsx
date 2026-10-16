import { Link, Navigate, useParams } from "react-router";
import type { HourEvaluation, Recommendation as Rec } from "../api/types";
import { formatDistance, formatHour, formatMinutes, formatScore } from "../lib/format";
import { aqiLabel, DESTINATION_TYPE_LABELS, FACTOR_LABELS, verdictFor } from "../lib/labels";
import { FOOTER_DISCLAIMER, NO_SEARCH_NOTICE } from "../lib/texts";
import { useAppState } from "../state/context";
import { AqiChip } from "./Chip";
import PageHeading from "./PageHeading";
import SourceList from "./SourceList";

function outdoorText(h: HourEvaluation) {
    if (h.outdoor_ok === null) return "sin datos";
    return h.outdoor_ok ? "Apta" : "No apta";
}

function bestHourCallout(item: Rec): string {
    const now = item.hours[0];
    if (item.destination.covered) {
        return "A cubierto: puedes ir a cualquier hora, no depende del tiempo.";
    }
    if (!item.best_hour) {
        return "No hay datos suficientes para elegir la mejor hora.";
    }
    const best = formatHour(item.best_hour);
    if (now && now.outdoor_ok === false && item.best_hour !== now.hour) {
        const reason = (now.reasons[0] ?? "").replace(/\.$/, "");
        return `Ahora no: ${reason.charAt(0).toLowerCase()}${reason.slice(1)}. Mejor a las ${best}.`;
    }
    return `La mejor hora para esta actividad es las ${best}.`;
}

export default function Recommendation() {
    const { id = "" } = useParams();
    const { results, medicalDisclaimer } = useAppState();
    const index = results.findIndex((r) => r.destination.id === id);
    if (index === -1) {
        return <Navigate to="/" replace state={{ notice: NO_SEARCH_NOTICE }} />;
    }
    const item = results[index];
    const verdict = verdictFor(item.score);
    const now = item.hours[0];
    const bestIndex = item.hours.findIndex((h) => h.hour === item.best_hour);
    const alternative = results.find((r) => r.indoor_alternative && r.destination.id !== id);
    const nowBad = now?.outdoor_ok === false && !item.destination.covered;
    const detailHours = [now, bestIndex > 0 ? item.hours[bestIndex] : undefined].filter(
        (h): h is HourEvaluation => h !== undefined,
    );

    return (
        <section className="detail-screen gomad-component gomad-recommendation" aria-labelledby="detail-title">
            <div className="detail-dialog">
                <header className="detail-header">
                    <Link to="/resultados" className="detail-header__back gomad-action gomad-action-back-to-results">
                        Volver a resultados
                    </Link>
                    <p className="detail-header__count">
                        Recomendación {index + 1} de {results.length}
                    </p>
                    <span />
                </header>

                <div className="detail-media" aria-hidden="true">
                    <span className="detail-media__tag">{DESTINATION_TYPE_LABELS[item.destination.type]}</span>
                    <span className="detail-media__credit">Imagen de ejemplo</span>
                </div>

                <div className="detail-content">
                    <div className="detail-intro">
                        <div>
                            <p className="detail-kicker">{DESTINATION_TYPE_LABELS[item.destination.type]}</p>
                            <PageHeading id="detail-title">{item.destination.name}</PageHeading>
                            <p className="detail-meta">
                                {formatDistance(item.distance_m)} · {formatMinutes(item.duration_min)} a pie ·{" "}
                                {item.destination.municipality}
                            </p>
                        </div>
                        <div className={`detail-score detail-score--${verdict.tone}`}>
                            <strong aria-hidden="true">{formatScore(item.score)}</strong>
                            <span aria-hidden="true">{verdict.text}</span>
                            <span className="sr-only">
                                Nota {formatScore(item.score)} sobre 10, {verdict.text.toLowerCase()}
                            </span>
                        </div>
                    </div>

                    <ul role="list" className="detail-tags" aria-label="Características del lugar">
                        <li>
                            {item.destination.covered === null
                                ? "Cubierta: sin datos"
                                : item.destination.covered
                                  ? "Cubierta"
                                  : "Exterior"}
                        </li>
                        {item.indoor_alternative && <li>Alternativa cubierta</li>}
                        <li>{item.destination.municipality}</li>
                    </ul>

                    {now && (
                        <dl className="detail-moment">
                            <div>
                                <dt className="detail-moment__label">Ahora</dt>
                                <dd>
                                    <strong>{now.temperature_c === null ? "Sin datos" : `${now.temperature_c} °C`}</strong>
                                    <small>
                                        {now.feels_like_c === null
                                            ? "Sensación: sin datos"
                                            : `Sensación ${now.feels_like_c} °C`}
                                    </small>
                                </dd>
                            </div>
                            <div>
                                <dt className="detail-moment__label">Aire</dt>
                                <dd>
                                    <AqiChip category={now.aqi_category} />
                                    <small>Índice oficial (ICA)</small>
                                </dd>
                            </div>
                            <div>
                                <dt className="detail-moment__label">Lluvia</dt>
                                <dd>
                                    <strong>{now.precip_prob === null ? "Sin datos" : `${now.precip_prob} %`}</strong>
                                    <small>Probabilidad</small>
                                </dd>
                            </div>
                        </dl>
                    )}

                    <section className="detail-section" aria-labelledby="por-que">
                        <p className="detail-section__eyebrow">La recomendación</p>
                        <h2 id="por-que">¿Por qué te recomendamos este lugar?</h2>
                        <p className="detail-explanation">{item.explanation}</p>
                        <ul role="list" className="factor-list" aria-label="Nota por factor">
                            {item.factors.map((f) => (
                                <li key={f.factor}>
                                    <div>
                                        <strong>{FACTOR_LABELS[f.factor]}</strong>
                                        <span>{f.text}</span>
                                    </div>
                                    {f.value === null ? (
                                        <b className="factor-list__nodata">sin datos (no cuenta en la nota)</b>
                                    ) : (
                                        <b>
                                            <span aria-hidden="true">
                                                {formatScore(f.value)}
                                                <small>/10</small>
                                            </span>
                                            <span className="sr-only">{formatScore(f.value)} sobre 10</span>
                                        </b>
                                    )}
                                </li>
                            ))}
                        </ul>
                    </section>

                    <section className="detail-section detail-section--hours" aria-labelledby="franja">
                        <p className="detail-section__eyebrow">Planifica tu salida</p>
                        <h2 id="franja">Mejor franja horaria</h2>
                        <p className={`detail-callout${nowBad ? " detail-callout--warn" : ""}`}>
                            {bestHourCallout(item)}
                        </p>
                        {nowBad && alternative && (
                            <p className="detail-alt">
                                <Link to={`/resultados/${encodeURIComponent(alternative.destination.id)}`} className="gomad-action gomad-action-open-covered-alternative">
                                    Alternativa cubierta: {alternative.destination.name}
                                </Link>
                            </p>
                        )}
                        <div className="hours-table-wrap" role="region" aria-label="Tabla de horas" tabIndex={0}>
                            <table>
                                <caption className="sr-only">Nota por hora en tu ventana horaria</caption>
                                <thead>
                                    <tr>
                                        <th scope="col">Hora</th>
                                        <th scope="col">Nota</th>
                                        <th scope="col">Temperatura</th>
                                        <th scope="col">Lluvia</th>
                                        <th scope="col">Aire</th>
                                        <th scope="col">Exterior</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {item.hours.map((h, i) => (
                                        <tr key={h.hour} className={i === bestIndex ? "is-best" : ""}>
                                            <th scope="row">
                                                {formatHour(h.hour)}
                                                {i === bestIndex && <span>Mejor hora</span>}
                                            </th>
                                            <td>{h.score === null ? "sin datos" : formatScore(h.score)}</td>
                                            <td>{h.temperature_c === null ? "sin datos" : `${h.temperature_c} °C`}</td>
                                            <td>{h.precip_prob === null ? "sin datos" : `${h.precip_prob} %`}</td>
                                            <td>{aqiLabel(h.aqi_category)}</td>
                                            <td>{outdoorText(h)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                        <ul role="list" className="detail-reasons" aria-label="Motivos por hora">
                            {detailHours.map((h) => (
                                <li key={h.hour}>
                                    <strong>{h === now ? `Ahora (${formatHour(h.hour)})` : `A las ${formatHour(h.hour)}`}:</strong>{" "}
                                    {h.reasons.join(" ")}
                                </li>
                            ))}
                        </ul>
                    </section>

                    <section className="detail-section detail-section--location" aria-labelledby="fuentes-detalle">
                        <p className="detail-section__eyebrow">Información del lugar</p>
                        <h2 id="fuentes-detalle">De dónde salen estos datos</h2>
                        <SourceList sources={item.sources} label="Fuentes de los datos" />
                    </section>

                    <div className="detail-actions">
                        <Link
                            to={`/ruta/${encodeURIComponent(item.destination.id)}`}
                            className="button button--primary gomad-action gomad-action-view-route">
                            Ver ruta en el mapa
                        </Link>
                        <Link to="/resultados" className="button gomad-action gomad-action-back-to-results">
                            Ver otras opciones
                        </Link>
                    </div>
                    <p className="detail-disclaimer">{medicalDisclaimer ?? FOOTER_DISCLAIMER}</p>
                </div>
            </div>
        </section>
    );
}
