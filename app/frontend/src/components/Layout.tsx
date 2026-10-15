import { useEffect, useRef } from "react";
import { Link, Outlet, useLocation } from "react-router";
import { FOOTER_DISCLAIMER } from "../lib/texts";
import Header from "./Header";

export default function Layout() {
    const { pathname } = useLocation();
    const firstRender = useRef(true);

    // Al cambiar de pantalla: arriba del todo y foco al h1 (no en la primera carga)
    useEffect(() => {
        if (firstRender.current) {
            firstRender.current = false;
            return;
        }
        window.scrollTo(0, 0);
        const h1 = document.querySelector<HTMLElement>("#contenido h1");
        h1?.focus();
    }, [pathname]);

    return (
        <>
            <a className="skip-link" href="#contenido">
                Saltar al contenido
            </a>
            <Header />
            <main id="contenido" className="app-main">
                <Outlet />
            </main>
            <footer className="footer">
                <div className="container footer__inner">
                    <p>{FOOTER_DISCLAIMER}</p>
                    <Link to="/fuentes" className="footer__link">
                        Fuentes y aviso
                    </Link>
                </div>
            </footer>
        </>
    );
}
