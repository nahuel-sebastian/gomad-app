import { Link, useLocation } from "react-router";
import Icon from "./Icon";

const LINKS = [
    { to: "/", label: "Mi entorno", icon: "near_me" },
    { to: "/municipios", label: "Municipios", icon: "location_city" },
    { to: "/perfil", label: "Preferencias", icon: "menu" },
];

// Seccion de la barra a la que pertenece cada ruta: "page" en la ruta exacta, "true" en sus subpantallas
function sectionOf(pathname: string): string {
    if (pathname.startsWith("/municipios")) return "/municipios";
    if (pathname.startsWith("/perfil")) return "/perfil";
    if (
        pathname === "/" ||
        pathname.startsWith("/resultados") ||
        pathname.startsWith("/ruta") ||
        pathname.startsWith("/asistente")
    ) {
        return "/";
    }
    return "";
}

export default function Header() {
    const { pathname } = useLocation();
    const current = sectionOf(pathname);

    return (
        <header className="header gomad-component gomad-header">
            <div className="container header__inner">
                <Link to="/" className="logo gomad-action gomad-action-go-home" aria-label="GoMad, ir al inicio">
                    <img
                        src="/images/logo.png"
                        alt=""
                        width="40"
                        height="40"
                        className="logo__mark"
                    />
                    <span aria-hidden="true">
                        <span className="logo__go">Go</span>Mad
                    </span>
                </Link>

                {/* En movil es la barra inferior (fija); en >= 768 px va aqui arriba */}
                <nav className="nav" aria-label="Principal">
                    <ul role="list" className="nav__list">
                        {LINKS.map((link) => (
                            <li key={link.to}>
                                <Link
                                    to={link.to}
                                    className={`nav__link gomad-action gomad-action-navigate gomad-action-navigate-${link.to === "/" ? "home" : link.to.slice(1)}`}
                                    aria-current={
                                        pathname === link.to ? "page" : current === link.to ? "true" : undefined
                                    }>
                                    <Icon name={link.icon} />
                                    {link.label}
                                </Link>
                            </li>
                        ))}
                    </ul>
                </nav>
            </div>
        </header>
    );
}
