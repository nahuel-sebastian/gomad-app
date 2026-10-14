import { useState } from "react";

// 1. Declaración del Icon integrada en el mismo archivo
interface IconProps {
    name: string;
    className?: string;
}

function Icon({ name, className }: IconProps) {
    const classes = ["gomad-icon", `gomad-icon--${name}`, className]
        .filter(Boolean)
        .join(" ");
    return <span className={classes} aria-hidden="true" />;
}

const LINKS = [
    { href: "#entorno", label: "Mi entorno" },
    { href: "#municipios", label: "Municipios" },
    { href: "#perfil", label: "Perfil" },
];

export default function Header() {
    const [open, setOpen] = useState(false);

    return (
        <header className="header">
            <div className="container header__inner">
                <a
                    href="#entorno"
                    className="logo"
                    aria-label="GoMAD, ir al inicio">
                    {/* 2. Imagen del logo reemplazando al componente Icon */}
                    <img
                        src="/images/logo.png"
                        alt="Logo de GoMAD"
                        className="logo__mark"
                    />
                    <span>
                        <span className="logo__go">Go</span>MAD
                    </span>
                </a>

                <button
                    type="button"
                    className="header__toggle"
                    aria-label={open ? "Cerrar menú" : "Abrir menú"}
                    aria-expanded={open}
                    aria-controls="menu-principal"
                    onClick={() => setOpen((v) => !v)}>
                    {/* El Icon del menú sigue funcionando gracias a que lo hemos incluido arriba */}
                    <Icon name="menu" />
                </button>

                <nav
                    id="menu-principal"
                    className={`nav${open ? " nav--open" : ""}`}
                    aria-label="Navegación principal">
                    {LINKS.map((link, i) => (
                        <a
                            key={link.href}
                            href={link.href}
                            className="nav__link"
                            aria-current={i === 0 ? "page" : undefined}
                            onClick={() => setOpen(false)}>
                            {link.label}
                        </a>
                    ))}
                </nav>
            </div>
        </header>
    );
}
