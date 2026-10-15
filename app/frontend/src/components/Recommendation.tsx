interface RecommendationProps {
    onBack: () => void;
    onViewRoute: () => void;
}

const factors = [
    {
        label: "Adecuación a tu actividad",
        value: "9,1",
        text: "Espacio amplio y apto para caminar.",
    },
    {
        label: "Zona verde",
        value: "8,8",
        text: "La mayor parte del entorno es arbolado.",
    },
    {
        label: "Calidad del aire",
        value: "8,2",
        text: "Aire razonablemente bueno ahora.",
    },
    {
        label: "Meteorología",
        value: "8,5",
        text: "Temperatura agradable para salir.",
    },
];

const hours = [
    { hour: "18:00", score: "7,8", temp: "24 °C", air: "Buena" },
    { hour: "19:00", score: "8,6", temp: "22 °C", air: "Buena" },
    { hour: "20:00", score: "9,1", temp: "20 °C", air: "Buena", best: true },
    { hour: "21:00", score: "8,4", temp: "19 °C", air: "Buena" },
];

export default function Recommendation({
    onBack,
    onViewRoute,
}: RecommendationProps) {
    return (
        <section className="detail-screen" aria-labelledby="detail-title">
            <div className="detail-dialog">
                <header className="detail-header">
                    <button
                        type="button"
                        className="detail-header__back"
                        onClick={onBack}>
                        Volver a resultados
                    </button>
                    <p className="detail-header__count">Recomendación 1 de 3</p>
                    <button
                        type="button"
                        className="detail-header__close"
                        onClick={onBack}>
                        Cerrar
                    </button>
                </header>

                <div className="detail-media">
                    <span className="detail-media__tag">Parque urbano</span>
                    <span className="detail-media__credit">
                        Imagen de ejemplo
                    </span>
                </div>

                <div className="detail-content">
                    <div className="detail-intro">
                        <div>
                            <p className="detail-kicker">
                                Parques y naturaleza
                            </p>
                            <h1 id="detail-title">Parque de la Alhóndiga</h1>
                            <p className="detail-meta">
                                1,8 km · 22 min a pie · Getafe
                            </p>
                        </div>
                        <div
                            className="detail-score"
                            aria-label="Nota 8,7 sobre 10">
                            <strong>8,7</strong>
                            <span>Muy buena opción</span>
                        </div>
                    </div>

                    <div
                        className="detail-tags"
                        aria-label="Características del lugar">
                        <span>Destacado</span>
                        <span>Exterior</span>
                        <span>Zona verde</span>
                    </div>

                    <div className="detail-moment">
                        <div>
                            <span className="detail-moment__label">Ahora</span>
                            <strong>22 °C</strong>
                            <small>Temperatura agradable</small>
                        </div>
                        <div>
                            <span className="detail-moment__label">Aire</span>
                            <strong>Bueno</strong>
                            <small>Razonablemente bueno</small>
                        </div>
                        <div>
                            <span className="detail-moment__label">
                                Tráfico
                            </span>
                            <strong>Bajo</strong>
                            <small>En el entorno</small>
                        </div>
                    </div>

                    <section className="detail-section">
                        <p className="detail-section__eyebrow">
                            La recomendación
                        </p>
                        <h2>¿Por qué te recomendamos este lugar?</h2>
                        <p className="detail-explanation">
                            Es una opción equilibrada para salir ahora: está
                            cerca, tiene mucho espacio verde y las condiciones
                            del momento son buenas para caminar.
                        </p>
                        <ul className="factor-list">
                            {factors.map((factor) => (
                                <li key={factor.label}>
                                    <div>
                                        <strong>{factor.label}</strong>
                                        <span>{factor.text}</span>
                                    </div>
                                    <b>
                                        {factor.value}
                                        <small>/10</small>
                                    </b>
                                </li>
                            ))}
                        </ul>
                    </section>

                    <section className="detail-section detail-section--hours">
                        <p className="detail-section__eyebrow">
                            Planifica tu salida
                        </p>
                        <h2>Mejor franja horaria</h2>
                        <p className="detail-callout">
                            La mejor hora para esta actividad es{" "}
                            <strong>20:00</strong>.
                        </p>
                        <div className="hours-table-wrap">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Hora</th>
                                        <th>Nota</th>
                                        <th>Temperatura</th>
                                        <th>Aire</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {hours.map((item) => (
                                        <tr
                                            key={item.hour}
                                            className={
                                                item.best ? "is-best" : ""
                                            }>
                                            <th scope="row">
                                                {item.hour}
                                                {item.best && (
                                                    <span>Mejor hora</span>
                                                )}
                                            </th>
                                            <td>{item.score}</td>
                                            <td>{item.temp}</td>
                                            <td>{item.air}</td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </section>

                    <section className="detail-section detail-section--location">
                        <p className="detail-section__eyebrow">
                            Información del lugar
                        </p>
                        <h2>Antes de salir</h2>
                        <p>
                            <strong>Ubicación:</strong> Avenida de las Ciudades,
                            Getafe
                        </p>
                        <p>
                            <strong>Fuente:</strong> Comunidad de Madrid ·
                            actualizado hoy
                        </p>
                    </section>

                    <div className="detail-actions">
                        <button
                            type="button"
                            className="button button--primary"
                            onClick={onViewRoute}>
                            Ver ruta saludable
                        </button>
                        <button
                            type="button"
                            className="button"
                            onClick={onBack}>
                            Ver otras opciones
                        </button>
                    </div>
                    <p className="detail-disclaimer">
                        Recomendación orientativa con datos abiertos. No es
                        consejo médico.
                    </p>
                </div>
            </div>
        </section>
    );
}
