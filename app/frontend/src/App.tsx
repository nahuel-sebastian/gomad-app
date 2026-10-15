import { useState } from "react";
import Header from "./components/Header";
import Hero from "./components/Hero";
import Home from "./components/Home";
import Results from "./components/Results";

export default function App() {
    // Controlamos si estamos en 'home' o en 'results'
    const [view, setView] = useState<"home" | "results">("home");
    // Guardamos qué actividad se ha seleccionado
    const [activity, setActivity] = useState<string>("");

    // Función para manejar el click en una actividad
    const handleSelectActivity = (act: string) => {
        setActivity(act);
        setView("results");
        window.scrollTo(0, 0); // Subir al inicio de la página al cambiar de vista
    };

    return (
        <>
            <a className="skip-link" href="#contenido">
                Saltar al contenido
            </a>
            <Header />
            <main id="contenido" className="app-main">
                {view === "home" ? (
                    <>
                        <Hero
                            municipality="Getafe"
                            temperature="22 °C"
                            air="Aire bueno"
                        />
                        {/* Pasamos la función al componente Home */}
                        <Home onSelectActivity={handleSelectActivity} />
                    </>
                ) : (
                    /* Pasamos la actividad y la función para volver atrás */
                    <Results
                        activity={activity}
                        onBack={() => setView("home")}
                    />
                )}
            </main>

            {view === "home" && (
                <footer className="footer">
                    <div className="container">
                        <p>
                            Recomendaciones orientativas con datos abiertos
                            (datos de ejemplo). No es consejo médico.
                        </p>
                    </div>
                </footer>
            )}
        </>
    );
}
