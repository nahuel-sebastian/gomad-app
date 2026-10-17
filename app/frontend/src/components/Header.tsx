import { Link, useLocation } from "react-router";
import Icon from "./Icon";

const LINKS = [
    { to: "/", label: "Mi entorno", icon: "near_me" },
    { to: "/municipios", label: "Municipios", icon: "location_city" },
    { to: "/perfil", label: "Preferencias", icon: "menu" },
    { to: "/fuentes", label: "Fuentes", icon: "info" },
];

// Seccion de la barra a la que pertenece cada ruta: "page" en la ruta exacta, "true" en sus subpantallas
function sectionOf(pathname: string): string {
    if (pathname.startsWith("/municipios")) return "/municipios";
    if (pathname.startsWith("/perfil")) return "/perfil";
    if (pathname.startsWith("/fuentes")) return "/fuentes";
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
                                    aria-label={link.label}
                                    aria-current={
                                        pathname === link.to ? "page" : current === link.to ? "true" : undefined
                                    }>
                                    {link.icon === "info" ? (
                                        <svg className="nav__icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                            <circle cx="12" cy="12" r="9" />
                                            <path d="M12 11v5M12 8h.01" />
                                        </svg>
                                    ) : <Icon name={link.icon} />}
                                    <span className="nav__label" aria-hidden="true">{link.label}</span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                </nav>
            </div>
        </header>
    );
}
