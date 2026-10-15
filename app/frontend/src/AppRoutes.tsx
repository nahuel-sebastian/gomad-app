import { Route, Routes, useNavigate } from "react-router";
import ComingSoon from "./components/ComingSoon";
import Hero from "./components/Hero";
import Home from "./components/Home";
import Layout from "./components/Layout";
import NotFound from "./components/NotFound";
import Recommendation from "./components/Recommendation";
import Results from "./components/Results";
import { useAppState } from "./state/context";

function HomeScreen() {
    const navigate = useNavigate();
    const { setSearch } = useAppState();
    return (
        <>
            <Hero municipality="Getafe" temperature="22 °C" air="Aire bueno" />
            <Home
                onSelectActivity={(activity) => {
                    setSearch({ activity });
                    navigate("/resultados");
                }}
            />
        </>
    );
}

function ResultsScreen() {
    const navigate = useNavigate();
    const { search } = useAppState();
    return (
        <Results
            activity={search?.activity ?? null}
            onBack={() => navigate("/")}
            onSelectResult={() => navigate("/resultados/ejemplo")}
        />
    );
}

function DetailScreen() {
    const navigate = useNavigate();
    return (
        <Recommendation
            onBack={() => navigate("/resultados")}
            onViewRoute={() => navigate("/ruta/ejemplo")}
        />
    );
}

export default function AppRoutes() {
    return (
        <Routes>
            <Route element={<Layout />}>
                <Route index element={<HomeScreen />} />
                <Route path="resultados" element={<ResultsScreen />} />
                <Route path="resultados/:id" element={<DetailScreen />} />
                <Route
                    path="ruta/:id"
                    element={<ComingSoon title="Ruta saludable" />}
                />
                <Route
                    path="municipios"
                    element={<ComingSoon title="Municipios" />}
                />
                <Route
                    path="municipios/:ine_code"
                    element={<ComingSoon title="Municipio" />}
                />
                <Route
                    path="perfil"
                    element={<ComingSoon title="Tus preferencias" />}
                />
                <Route
                    path="asistente"
                    element={<ComingSoon title="Asistente de rutas" />}
                />
                <Route
                    path="fuentes"
                    element={<ComingSoon title="Fuentes, licencias y aviso" />}
                />
                <Route path="*" element={<NotFound />} />
            </Route>
        </Routes>
    );
}
