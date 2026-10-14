interface HeroProps {
    municipality: string;
    temperature: string;
    air: string;
}

export default function Hero({ municipality, temperature, air }: HeroProps) {
    const chips = [
        { icon: "pin", label: municipality, tone: "info" },
        { icon: "sun", label: temperature, tone: "good" },
        { icon: "leaf", label: air, tone: "good" },
    ];

    return (
        <section className="hero" id="entorno">
            <svg
                className="hero__scene"
                viewBox="0 0 390 230"
                preserveAspectRatio="xMidYMax slice"
                aria-hidden="true">
                <rect width="390" height="230" fill="#cfe6f5" />
                <circle cx="318" cy="90" r="26" fill="#f7c948" />

                <g fill="#a9c6da">
                    {/* Torres KIO (Puerta de Europa) - Más separadas */}
                    <polygon points="80,180 100,180 120,120 100,120" />
                    <polygon points="150,180 170,180 150,120 130,120" />

                    {/* Cinco Torres Business Area */}
                    {/* Torre Cepsa */}
                    <path d="M190,180 v-80 h16 v80 Z M192,100 v-15 h12 v15 Z" />
                    {/* Torre de Cristal */}
                    <polygon points="215,180 231,180 231,70 215,85" />
                    {/* Torre PwC */}
                    <rect x="240" y="80" width="16" height="100" />
                    {/* Torre Emperador Castellana (Espacio) */}
                    <polygon points="265,180 281,180 275,85 268,85" />
                    {/* Torre Caleido (Quinta torre) */}
                    <path d="M293,180 v-70 h12 v70 Z M289,180 v-25 h20 v25 Z" />

                    {/* El Pirulí (Torrespaña) */}
                    <rect x="335" y="110" width="6" height="70" />
                    <polygon points="330,110 346,110 342,100 334,100" />
                    <polygon points="330,110 334,120 342,120 346,110" />
                    <rect x="337" y="60" width="2" height="40" />
                </g>

                <path
                    d="M0 178 C80 138 170 200 250 168 S350 150 390 174 V230 H0z"
                    fill="#8cc79b"
                />
                <path
                    d="M0 206 C100 172 220 222 390 194 V230 H0z"
                    fill="#5fa777"
                />
                <g fill="#2f7d55">
                    <circle cx="28" cy="174" r="22" />
                    <circle cx="64" cy="186" r="16" />
                    <circle cx="352" cy="170" r="18" />
                </g>
                <g stroke="#5b4636" strokeWidth="4" strokeLinecap="round">
                    <path d="M28 194V218" />
                    <path d="M64 200V220" />
                    <path d="M352 186V206" />
                </g>
                <path
                    d="M150 230 C190 200 250 208 300 230"
                    fill="none"
                    stroke="#f3ebd8"
                    strokeWidth="10"
                />
            </svg>

            <div className="container hero__content">
                <h1 className="hero__title">Hoy es un gran día para moverte</h1>
                <ul className="chips">
                    {chips.map((chip) => (
                        <li
                            key={chip.icon}
                            className={`chip chip--${chip.tone}`}>
                            <span>{chip.label}</span>
                        </li>
                    ))}
                </ul>
            </div>
        </section>
    );
}
