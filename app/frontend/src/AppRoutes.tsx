import { Route, Routes } from "react-router";
import ComingSoon from "./components/ComingSoon";
import Home from "./components/Home";
import Layout from "./components/Layout";
import NotFound from "./components/NotFound";
import Recommendation from "./components/Recommendation";
import Results from "./components/Results";

export default function AppRoutes() {
    return (
        <Routes>
            <Route element={<Layout />}>
                <Route index element={<Home />} />
                <Route path="resultados" element={<Results />} />
                <Route path="resultados/:id" element={<Recommendation />} />
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
