import { useEffect, useRef } from "react";
import { Outlet, useLocation } from "react-router";
import Header from "./Header";

export default function Layout() {
    const { pathname } = useLocation();
    const previousPathname = useRef(pathname);

    // Al cambiar de pantalla: arriba del todo y foco al h1 (no en la primera carga)
    useEffect(() => {
        if (previousPathname.current === pathname) return;
        previousPathname.current = pathname;
        window.scrollTo(0, 0);
        const h1 = document.querySelector<HTMLElement>("#contenido h1");
        h1?.focus();
    }, [pathname]);

    return (
        <>
            <a className="skip-link gomad-action gomad-action-skip-to-content" href="#contenido">
                Saltar al contenido
            </a>
            <Header />
            <main id="contenido" className="app-main gomad-component gomad-layout" tabIndex={-1}>
                <Outlet />
            </main>
        </>
    );
}
