interface HomeProps {
    onSelectActivity: (activity: string | null) => void;
}

const ACTIVITIES = [
    { id: "correr", icon: "run", label: "Correr" },
    { id: "caminar", icon: "walk", label: "Caminar" },
    { id: "nadar", icon: "swim", label: "Nadar" },
    { id: "padel", icon: "padel", label: "Pádel" },
    { id: "otra", icon: "plus", label: "Otra" },
];

const PREFERENCES = "45 min · hasta 3 km · interior o exterior";

export default function Home({ onSelectActivity }: HomeProps) {
    return (
        <div className="container home">
            <section className="panel" aria-labelledby="actividades-titulo">
                <h2 className="panel__title" id="actividades-titulo">
                    ¿Qué te apetece hacer?
                </h2>
                <ul className="activities">
                    {ACTIVITIES.map((a) => (
                        <li key={a.id}>
                            {/* Añadimos el onClick aquí */}
                            <button
                                type="button"
                                className="activity"
                                onClick={() => onSelectActivity(a.id)}>
                                <span className="activity__tile"></span>
                                <span>{a.label}</span>
                            </button>
                        </li>
                    ))}
                </ul>
            </section>

            <div className="home__secondary">
                {/* También se lo añadimos al botón Sorpréndeme */}
                <button
                    type="button"
                    className="panel panel--action surprise"
                    onClick={() => onSelectActivity(null)}>
                    <span className="surprise__tile"></span>
                    <span className="surprise__text">
                        <span className="panel__title">Sorpréndeme</span>
                        <span className="muted">
                            Te propongo un plan según tu ubicación y tu tiempo
                            libre.
                        </span>
                    </span>
                </button>

                <section className="panel prefs" aria-label="Tus preferencias">
                    <div className="prefs__text">
                        <span className="muted">Tus preferencias</span>
                        <strong>{PREFERENCES}</strong>
                    </div>
                    <button type="button" className="button">
                        <span>Ajustar</span>
                    </button>
                </section>
            </div>
        </div>
    );
}
