import { BrowserRouter } from "react-router";
import AppRoutes from "./AppRoutes";
import { AppStateProvider } from "./state/AppState";

export default function App() {
    return (
        <BrowserRouter>
            <AppStateProvider>
                <AppRoutes />
            </AppStateProvider>
        </BrowserRouter>
    );
}
