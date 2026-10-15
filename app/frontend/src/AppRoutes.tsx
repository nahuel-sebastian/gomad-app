import { Route, Routes } from "react-router";
import ComingSoon from "./components/ComingSoon";
import Home from "./components/Home";
import Layout from "./components/Layout";
import Municipalities from "./components/Municipalities";
import Municipality from "./components/Municipality";
import NotFound from "./components/NotFound";
import Profile from "./components/Profile";
import Recommendation from "./components/Recommendation";
import Results from "./components/Results";
import RouteView from "./components/RouteView";

export default function AppRoutes() {
    return (
        <Routes>
            <Route element={<Layout />}>
                <Route index element={<Home />} />
                <Route path="resultados" element={<Results />} />
                <Route path="resultados/:id" element={<Recommendation />} />
                <Route path="ruta/:id" element={<RouteView />} />
                <Route path="municipios" element={<Municipalities />} />
                <Route path="municipios/:ine_code" element={<Municipality />} />
                <Route path="perfil" element={<Profile />} />
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
