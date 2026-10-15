const LINKS = [
    { href: "#entorno", label: "Mi entorno" },
    { href: "#municipios", label: "Municipios" },
    { href: "#perfil", label: "Perfil" },
];

export default function Header() {
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

                <nav
                    id="menu-principal"
                    className="nav"
                    aria-label="Navegación principal">
                    {LINKS.map((link, i) => (
                        <a
                            key={link.href}
                            href={link.href}
                            className="nav__link"
                            aria-current={i === 0 ? "page" : undefined}
                            >
                            {link.label}
                        </a>
                    ))}
                </nav>
            </div>
        </header>
    );
}
