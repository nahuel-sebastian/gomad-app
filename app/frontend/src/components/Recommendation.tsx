import { Link, Navigate, useParams } from "react-router";
import type { HourEvaluation, Recommendation as Rec } from "../api/types";
import { formatDestinationName, formatDistance, formatHour, formatMinutes, formatScore } from "../lib/format";
import { aqiLabel, DESTINATION_TYPE_LABELS, FACTOR_LABELS, verdictFor } from "../lib/labels";
import { FOOTER_DISCLAIMER, NO_SEARCH_NOTICE } from "../lib/texts";
import { useAppState } from "../state/context";
import { AqiChip } from "./Chip";
import Hero, { heroVariantForDestination } from "./Hero";
import Icon from "./Icon";
import PageHeading from "./PageHeading";
import SourceList from "./SourceList";

function outdoorText(h: HourEvaluation) {
    if (h.outdoor_ok === null) return "Sin datos";
    return h.outdoor_ok ? "Apta" : "No apta";
}

function hourCallout(item: Rec): string | null {
    const now = item.hours[0];
    if (!item.best_hour) {
        return "No hay datos suficientes para elegir la mejor hora.";
    }
    if (now && now.outdoor_ok === false && !item.destination.covered) {
        const reasons = now.reasons.join(" ").trim();
        return `Ahora no: ${reasons.charAt(0).toLowerCase()}${reasons.slice(1)}`;
    }
    return null;
}

function explanationPoints(explanation: string): string[] {
    const summary = explanation.split(/(?:\.\s*)?Fuentes:\s*/i)[0];
    return summary
        .split(/\.\s+(?=[A-ZÁÉÍÓÚÑ¿])/)
        .map((part) => part.trim().replace(/\.$/, ""))
        .filter((part) => part && !/;\s*nota\s+\d[\d,.]*\s+sobre\s+10/i.test(part))
        .flatMap((part) => {
            const later = part.match(/^Ahora no: mejor a las (\d{1,2}:\d{2}) \((.+)\)$/i);
            if (later) {
                const ownCriterion = /\(umbral de criterio propio\)/i.test(later[2]);
                const reason = later[2]
                    .replace(/\s*\(umbral de criterio propio\)/i, "")
                    .replace(/^lluvia: (\d+) % de probabilidad$/i, "Hay un $1 % de probabilidad de lluvia");
                return [
                    `Ahora conviene esperar. Mejor salir a las ${later[1]}.`,
                    `${reason.charAt(0).toUpperCase()}${reason.slice(1)}.${ownCriterion ? " GoMAD aplica su propio umbral para esta recomendación." : ""}`,
                ];
            }
            return [`${part.replace(/^Destaca por /, "Puntos fuertes: ")}.`];
        });
}

function factorSubtitle(text: string): string {
    const separator = text.indexOf(":");
    const detail = (separator === -1 ? text : text.slice(separator + 1)).trim();
    return detail.charAt(0).toLocaleUpperCase("es-ES") + detail.slice(1);
}

export default function Recommendation() {
    const { id = "" } = useParams();
    const { results, search, medicalDisclaimer } = useAppState();
    const index = results.findIndex((r) => r.destination.id === id);
    if (index === -1) {
        return <Navigate to="/" replace state={{ notice: NO_SEARCH_NOTICE }} />;
    }
    const item = results[index];
    const heroVariant = heroVariantForDestination(item.destination, search?.activity);
    const verdict = verdictFor(item.score);
    const now = item.hours[0];
    const bestIndex = item.hours.findIndex((h) => h.hour === item.best_hour);
    const alternative = results.find((r) => r.indoor_alternative && r.destination.id !== id);
    const nowBad = now?.outdoor_ok === false && !item.destination.covered;
    const callout = hourCallout(item);

    return (
        <section className="detail-screen gomad-component gomad-recommendation" aria-labelledby="detail-title">
            <div className="detail-dialog">
                <Hero variant={heroVariant} className="detail-media">
                    <Link to="/resultados" className="detail-media__back gomad-action gomad-action-back-to-results">
                        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" focusable="false">
                            <path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
                        </svg>
                        Volver
                        <span className="sr-only">
                            {" "}a resultados (recomendación {index + 1} de {results.length})
                        </span>
                    </Link>
                </Hero>

                <div className="detail-content">
                    <div className="detail-intro">
                        <div className="detail-intro__copy">
                            <p className="detail-kicker">{DESTINATION_TYPE_LABELS[item.destination.type]}</p>
                            <PageHeading id="detail-title">{formatDestinationName(item.destination.name)}</PageHeading>
                            <p className="detail-meta">
                                {formatDistance(item.distance_m)} · {formatMinutes(item.duration_min)} a pie ·{" "}
                                {item.destination.municipality}
                            </p>
                        </div>
                        <div className={`detail-score detail-score--${verdict.tone}`}>
                            <strong aria-hidden="true">{formatScore(item.score)}</strong>
                            <span className="sr-only">
                                Nota {formatScore(item.score)} sobre 10, {verdict.text.toLowerCase()}
                            </span>
                        </div>
                    </div>

                    {item.indoor_alternative && (
                        <ul role="list" className="detail-tags" aria-label="Características del lugar">
                            <li>Alternativa cubierta</li>
                        </ul>
                    )}

                    {now && (
                        <dl className="detail-moment">
                            <div>
                                <dt className="detail-moment__label">Ahora</dt>
                                <dd>
                                    <strong className={`chip ${now.temperature_c === null ? "chip--nodata" : "chip--info"} detail-moment__value`}>
                                        <Icon name="temperature" />
                                        {now.temperature_c === null ? "Sin datos" : `${now.temperature_c} °C`}
                                    </strong>
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
                                    <strong className={`chip ${now.precip_prob === null ? "chip--nodata" : "chip--info"} detail-moment__value`}>
                                        {now.precip_prob === null ? "Sin datos" : `${now.precip_prob} %`}
                                    </strong>
                                    <small>Probabilidad</small>
                                </dd>
                            </div>
                        </dl>
                    )}

                    <section className="detail-section" aria-labelledby="por-que">
                        <p className="detail-section__eyebrow">La recomendación</p>
                        <h2 id="por-que">¿Por qué te recomendamos este lugar?</h2>
                        <ul role="list" className="detail-explanation" aria-label="Resumen de la recomendación">
                            {explanationPoints(item.explanation).map((point) => (
                                <li key={point}>{point}</li>
                            ))}
                        </ul>
                        <ul role="list" className="factor-list" aria-label="Nota por factor">
                            {item.factors.map((f) => (
                                <li key={f.factor}>
                                    <div>
                                        <strong>{FACTOR_LABELS[f.factor]}</strong>
                                        <span>{factorSubtitle(f.text)}</span>
                                    </div>
                                    {f.value === null ? (
                                        <b className="factor-list__nodata">Sin datos</b>
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
                        {callout && (
                            <p className={`detail-callout${nowBad ? " detail-callout--warn" : ""}`}>
                                {callout}
                            </p>
                        )}
                        {nowBad && alternative && (
                            <p className="detail-alt">
                                <Link to={`/resultados/${encodeURIComponent(alternative.destination.id)}`} className="gomad-action gomad-action-open-covered-alternative">
                                    Alternativa cubierta: {formatDestinationName(alternative.destination.name)}
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
                                            <td>{h.score === null ? "Sin datos" : formatScore(h.score)}</td>
                                            <td>{h.temperature_c === null ? "Sin datos" : `${h.temperature_c} °C`}</td>
                                            <td>{h.precip_prob === null ? "Sin datos" : `${h.precip_prob} %`}</td>
                                            <td>{aqiLabel(h.aqi_category)}</td>
                                            <td>{outdoorText(h)}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
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
