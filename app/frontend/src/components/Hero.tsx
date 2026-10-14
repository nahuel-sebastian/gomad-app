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
                    <rect x="200" y="110" width="22" height="80" />
                    <rect x="228" y="130" width="18" height="60" />
                    <rect x="252" y="98" width="22" height="92" />
                    <rect x="150" y="138" width="26" height="52" />
                    <rect x="110" y="124" width="20" height="66" />
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
