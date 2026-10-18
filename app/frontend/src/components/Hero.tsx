import type { ReactNode } from "react";
import type { DestinationSummary } from "../api/types";
import PageHeading from "./PageHeading";

type DestinationType = DestinationSummary["type"];

// La actividad tiene prioridad; si no fija una escena, el nombre la concreta.
export function heroVariantForDestination(
    destination: Pick<DestinationSummary, "name" | "type">,
    activity?: string | null,
): DestinationType {
    if (activity === "swim") return "bathing_area";
    if (activity === "run") return "recreation_area";

    const name = destination.name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();

    // Jardín y Jardines tienen prioridad aunque el nombre incluya Lago o Retiro.
    if (/\bjardin(?:es)?\b/.test(name)) return "trail";
    if (/\b(area recreativa|zona recreativa|merendero|embarcadero|estanque|lago|laguna|retiro)\b/.test(name)) return "recreation_area";
    if (/\b(senda|sendero|ruta|camino|paseo|via verde|via pecuaria|pinar|bosque|rosaleda)\b/.test(name)) return "trail";
    if (/\b(polideportivo|estadio|campo de futbol|pista|pabellon|gimnasio|centro deportivo|cancha|fronton|velodromo)\b/.test(name)) return "facility";

    return destination.type === "bathing_area" ? "facility" : destination.type;
}

type HeroProps = {
    title: string;
    variant?: "home";
    className?: string;
    children?: ReactNode;
} | {
    variant: DestinationType | "municipality";
    className?: string;
    children?: ReactNode;
};

export default function Hero(props: HeroProps) {
    const variant = props.variant ?? "home";
    return (
        <section className={`hero hero--${variant} gomad-component gomad-hero${props.className ? ` ${props.className}` : ""}`}>
            {variant === "home" ? (
            <svg
                className="hero__scene"
                viewBox="0 0 390 230"
                preserveAspectRatio="xMidYMax slice"
                aria-hidden="true">
                <rect width="390" height="230" fill="#cfe6f5" />
                <circle cx="318" cy="90" r="26" fill="#f7c948" />

                <g fill="#a9c6da">
                    {/* Torres KIO (Puerta de Europa) - Mas separadas */}
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

                    {/* El Piruli (Torrespana) */}
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
            ) : variant === "municipality" ? (
                <>
                    <MunicipalityScene />
                </>
            ) : <HeroScene type={variant} />}

            {props.variant && props.variant !== "home" ? props.children : (
                <div className="container hero__content">
                    <PageHeading className="hero__title">{props.title}</PageHeading>
                    {props.children}
                </div>
            )}
        </section>
    );
}

function MunicipalityScene() {
    return (
        <svg className="hero__scene" viewBox="0 0 600 320" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <defs>
                <linearGradient id="municipality-sky" x2="0" y2="1">
                    <stop stopColor="#78b5df" />
                    <stop offset="1" stopColor="#deedf3" />
                </linearGradient>
                <linearGradient id="municipality-road" x2="0" y2="1">
                    <stop stopColor="#89949a" />
                    <stop offset="1" stopColor="#626e75" />
                </linearGradient>
            </defs>
            <rect width="600" height="320" fill="url(#municipality-sky)" />
            <g fill="#f7fbf7" opacity=".55">
                <ellipse cx="76" cy="65" rx="42" ry="10" />
                <ellipse cx="116" cy="62" rx="35" ry="8" />
                <ellipse cx="507" cy="55" rx="50" ry="9" />
            </g>
            {/* Fachadas de Gran Vía, con la cúpula del edificio Metrópolis como centro. */}
            <path d="M0 151 34 137 34 121 86 121 86 142 132 132 132 112 197 112 197 134 248 126 248 223H0Z" fill="#e3d6bc" />
            <path d="M0 162 34 148 86 151 132 142 197 145 248 137" fill="none" stroke="#f9f1df" strokeWidth="7" />
            <path d="M0 200h249M34 122v105M86 122v105M132 113v110M197 113v107" fill="none" stroke="#bba889" strokeWidth="3" />
            <g fill="#4b6d80">
                {[20, 47, 71, 108, 150, 174, 213, 235].map((x) => [163, 188, 213].map((y) => <rect key={`${x}-${y}`} x={x} y={y} width="8" height="13" rx="1" />))}
            </g>
            <path d="M438 129h39v-24h15v20h52v13h56v91H438Z" fill="#e8dbc3" />
            <path d="M430 146h170M444 183h156M444 213h156" stroke="#f9f0dc" strokeWidth="6" />
            <g fill="#5b7480">{[458, 483, 508, 533, 558, 583].map((x) => [159, 192].map((y) => <rect key={`${x}-${y}`} x={x} y={y} width="9" height="15" rx="1" />))}</g>
            <path d="M287 224V118h28V96h15V79h60v17h16v22h27v106Z" fill="#eadcc1" stroke="#c8b392" strokeWidth="3" />
            <path d="M317 96h87M301 119h119M287 174h146M287 208h146" stroke="#faf3e1" strokeWidth="8" />
            <path d="M328 79q3-41 32-47 29 6 32 47Z" fill="#516e83" stroke="#e2cd9e" strokeWidth="4" />
            <path d="M339 70q5-26 21-30 16 4 21 30" fill="none" stroke="#a5bcc0" strokeWidth="3" />
            <path d="M354 31q-5-6-2-9 5 0 8 5 3-5 8-5 3 3-2 9Z" fill="#2d3f48" />
            <g fill="#527182">{[301, 321, 344, 370, 394, 414].map((x) => [132, 154, 187].map((y) => <rect key={`${x}-${y}`} x={x} y={y} width="9" height="13" rx="1" />))}</g>
            <g fill="#f8efdb">{[306, 328, 352, 378, 401].map((x) => <rect key={x} x={x} y="174" width="5" height="34" />)}</g>
            {/* Bandera integrada en la fachada, con el mástil y las siete estrellas. */}
            <g>
                <path d="M386 119v43" stroke="#53594e" strokeWidth="2" />
                <path d="M388 123q10-4 20 0t20 0v22q-10 4-20 0t-20 0Z" fill="#c90825" stroke="#a00821" strokeWidth="1" />
                {[0, 1, 2, 3].map((i) => <path key={`top-${i}`} d="m0-2 .5 1.3H2L.8.2l.5 1.5L0 .9l-1.3.8.5-1.5L-2-.7h1.5Z" fill="#fff" transform={`translate(${394 + i * 9} 130)`} />)}
                {[0, 1, 2].map((i) => <path key={`bottom-${i}`} d="m0-2 .5 1.3H2L.8.2l.5 1.5L0 .9l-1.3.8.5-1.5L-2-.7h1.5Z" fill="#fff" transform={`translate(${398 + i * 9} 138)`} />)}
            </g>
            <path d="M0 231q105-21 248-9 117-7 212 4 84-8 140 0v94H0Z" fill="#7e935e" />
            <g fill="#477c5b">{[38, 83, 133, 183, 236, 470, 522, 573].map((x) => <circle key={x} cx={x} cy={221} r={x % 2 ? 20 : 16} />)}</g>
            <g fill="#6b9b6a">{[38, 83, 133, 183, 236, 470, 522, 573].map((x) => <circle key={x} cx={x - 7} cy={212} r="10" />)}</g>
            <path d="M0 247q159-10 294 0 148-5 306 0v73H0Z" fill="url(#municipality-road)" />
            <path d="M0 252q159-11 294 0 148-6 306 0M0 274q194-12 296-4 133-7 304 3" fill="none" stroke="#ded7c4" strokeWidth="5" />
            <g strokeLinejoin="round">
                <path d="M88 278h8l8-10q2-3 6-3h22q4 0 7 3l7 10h5v8H88Z" fill="#e8f0e9" stroke="#3d5660" strokeWidth="2" />
                <path d="m107 268-5 9h17v-9Zm15 0v9h18l-6-9Z" fill="#91b7c4" stroke="#496b78" strokeWidth="1" />
                <path d="M88 279h7m50 0h6" stroke="#f4d294" strokeWidth="2" />
                <circle cx="104" cy="286" r="5" fill="#263a43" /><circle cx="137" cy="286" r="5" fill="#263a43" />
                <circle cx="104" cy="286" r="2" fill="#aebbc0" /><circle cx="137" cy="286" r="2" fill="#aebbc0" />
                <path d="M448 280h8l9-11q2-3 6-3h22q4 0 7 3l8 11h5v8h-65Z" fill="#dbe8e4" stroke="#3d5660" strokeWidth="2" />
                <path d="m468 269-6 10h18v-10Zm15 0v10h18l-7-10Z" fill="#8fb3c2" stroke="#496b78" strokeWidth="1" />
                <path d="M448 281h7m51 0h7" stroke="#f4d294" strokeWidth="2" />
                <circle cx="465" cy="288" r="5" fill="#263a43" /><circle cx="499" cy="288" r="5" fill="#263a43" />
                <circle cx="465" cy="288" r="2" fill="#aebbc0" /><circle cx="499" cy="288" r="2" fill="#aebbc0" />
            </g>
        </svg>
    );
}

const trees = [26, 72, 112, 155, 432, 478, 525, 573];

function HeroScene({ type }: { type: DestinationType }) {
    if (type === "park") {
        return (
            <svg className="hero__scene" viewBox="0 0 390 150" preserveAspectRatio="xMaxYMid slice" aria-hidden="true">
                <rect width="390" height="150" fill="#dcefe6" />
                <circle cx="328" cy="36" r="24" fill="#f7c948" />
                <path d="M0 112 Q90 68 180 108 T390 92 V150 H0Z" fill="#a6d5b1" />
                <path d="M0 135 Q110 100 220 130 T390 111 V150 H0Z" fill="#78b98b" />
                <path d="M255 150 Q285 113 390 119" fill="none" stroke="#f5edda" strokeWidth="12" />
                <path d="M0 124Q100 105 203 128T390 111" fill="none" stroke="#91c8a0" strokeWidth="2" opacity=".8" />
                <g fill="#357b55"><circle cx="300" cy="99" r="15" /><circle cx="344" cy="103" r="19" /></g>
                <g fill="#4b986b"><circle cx="294" cy="93" r="7" /><circle cx="337" cy="96" r="9" /></g>
                <g stroke="#5b4636" strokeWidth="4"><path d="M300 111v22" /><path d="M344 119v22" /></g>
            </svg>
        );
    }

    if (type === "trail") {
        return (
            <svg className="hero__scene" viewBox="0 0 600 320" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                <rect width="600" height="320" fill="#d7e9da" />
                <path d="M0 0h600v145Q455 112 350 147T0 138Z" fill="#326b49" />
                <path d="M0 97Q125 40 227 119T430 91Q520 38 600 91v124H0Z" fill="#225b3e" />
                <path d="M0 127Q115 76 217 136T415 111Q507 71 600 124v47H0Z" fill="#347049" opacity=".65" />
                {trees.map((x, i) => <g key={x}>
                    <path d={`M${x} 128v110`} stroke="#4d4937" strokeWidth={i % 2 ? 9 : 7} />
                    <circle cx={x} cy={82 + (i % 3) * 13} r={40 + (i % 2) * 9} fill={i % 2 ? "#40794b" : "#5c944f"} />
                    <circle cx={x + 18} cy={99 + (i % 3) * 13} r="25" fill="#76a85b" />
                    <circle cx={x - 14} cy={68 + (i % 3) * 13} r="17" fill="#78a75b" opacity=".65" />
                </g>)}
                <path d="M0 217Q90 192 169 227T355 214Q476 185 600 220v100H0Z" fill="#83a950" />
                <path d="M0 259Q103 232 220 274L190 320H0Z" fill="#5e953e" />
                <path d="M470 260Q545 235 600 257v63H440Z" fill="#568b43" />
                <path
                    d="M189 320C238 280 282 259 312 238C328 226 338 218 348 216Q354 218 358 224C347 237 341 250 331 264C310 291 299 307 291 320Z"
                    fill="#f4e7cb"
                    stroke="#d8c69f"
                    strokeWidth="4"
                    strokeLinejoin="round"
                />
                <path d="M0 272Q75 246 157 275m304 12q73-38 139-20" fill="none" stroke="#a7bd5e" strokeWidth="10" />
                <g fill="#a06d4b">{[24, 51, 92, 137, 177, 458, 493, 544, 578].map((x) => <circle key={x} cx={x} cy={270 + x % 24} r="3" />)}</g>
                <g fill="none" stroke="#8460a4" strokeWidth="3" strokeLinecap="round">{[66, 80, 105, 475, 502, 521].map((x) => <path key={x} d={`M${x} 305v-20m-4 7 4-8 4 8`} />)}</g>
                <g fill="#d78058">{[51, 121, 147, 486, 551].map((x) => <circle key={x} cx={x} cy={281 + x % 12} r="3" />)}</g>
                <path d="M173 185h57l16 53h-89Z" fill="#66854c" />
                <path d="M173 185h57l16 53h-89Z" fill="none" stroke="#47713d" strokeWidth="3" />
                <path d="M187 179h27v-5h-27Z" fill="#dadbd0" />
                <path d="M195 171q-7-17 2-22 4-3 2-10 15 4 8 19l9 13Z" fill="#e8e7db" />
                <circle cx="202" cy="135" r="8" fill="#e8e7db" />
                <path d="m202 148-13 22m17-18 13 16" fill="none" stroke="#c5c9bd" strokeWidth="2" />
            </svg>
        );
    }

    if (type === "recreation_area") {
        return (
            <svg className="hero__scene" viewBox="0 0 600 320" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                <rect width="600" height="320" fill="#287be5" />
                <g fill="#f6f9f5" opacity=".85"><ellipse cx="103" cy="58" rx="34" ry="9" /><ellipse cx="472" cy="76" rx="44" ry="11" /></g>
                <path d="M0 146Q62 90 133 137T265 127Q335 94 400 138T600 127v95H0Z" fill="#487d40" />
                <g fill="#397343">{trees.map((x) => <circle key={x} cx={x} cy="154" r={x % 2 ? 39 : 31} />)}</g>
                <g fill="#63934b">{trees.map((x) => <circle key={`light-${x}`} cx={x - 12} cy="139" r="14" />)}</g>
                <path d="M92 206Q173 189 206 202L269 210V104h62v106l65-8q55-14 112-3v32H92Z" fill="#eee6cf" />
                <path d="M123 202v-53q61 18 106 14v39m142 0v-39q49 5 105-14v53" fill="none" stroke="#d1c5aa" strokeWidth="8" />
                <g fill="#faf6e8">{[137, 154, 171, 188, 205, 222, 384, 401, 418, 435, 452, 469].map((x) => <rect key={x} x={x} y="160" width="7" height="46" />)}</g>
                <path d="M115 147Q171 171 234 156m132 0q62 14 119-9" fill="none" stroke="#faf6e8" strokeWidth="5" />
                <path d="M101 204h160m78 0h160" stroke="#b7a989" strokeWidth="5" />
                <path d="M275 105h50l-7-15h-36Zm-14 105h78v14h-78Z" fill="#d7c9aa" />
                <path d="M290 88h20V59h-20Zm-7-29h34l-17-17Z" fill="#efe8d9" />
                <circle cx="300" cy="37" r="6" fill="#393e3f" />
                <path d="M300 43v12m-7-10 14 7" fill="none" stroke="#393e3f" strokeWidth="3" />
                <path d="M268 223h64l-8 10h-48Z" fill="#c2b393" />
                <path d="M0 225Q300 207 600 225v95H0Z" fill="#6b9ba2" />
                <path d="M0 240Q300 226 600 239M0 269Q300 256 600 268M0 296Q300 285 600 297" fill="none" stroke="#a6c0af" strokeWidth="2" opacity=".7" />
                <g fill="#1e71b4"><path d="m173 261 40 0-8 7h-24ZM363 278h46l-8 8h-31Z" /></g>
                <g fill="#d4e2d5" opacity=".55"><path d="m279 251 33-2-12 3Zm-58 36 42-3-16 4Zm191 20 35-2-10 3Z" /></g>
                <path d="M0 219h600" stroke="#e4d9bb" strokeWidth="10" />
            </svg>
        );
    }

    if (type === "facility") {
        const buildings = [
            { x: 0, y: 37, width: 49, color: "#e4dfd2" },
            { x: 51, y: 55, width: 38, color: "#b49486" },
            { x: 92, y: 42, width: 53, color: "#e8e4da" },
            { x: 149, y: 69, width: 42, color: "#bc9e8d" },
            { x: 419, y: 58, width: 43, color: "#e9e5dc" },
            { x: 466, y: 40, width: 54, color: "#b49386" },
            { x: 524, y: 52, width: 42, color: "#e7e3d9" },
            { x: 569, y: 30, width: 31, color: "#b49282" },
        ];
        const roofRibs = [
            [95, 181, 195], [125, 159, 173], [159, 145, 159], [196, 137, 151],
            [237, 132, 146], [279, 130, 144], [321, 130, 144], [363, 132, 146],
            [404, 138, 152], [441, 149, 163], [475, 169, 183], [501, 190, 204],
        ];
        return (
            <svg className="hero__scene" viewBox="0 0 600 320" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
                <rect width="600" height="320" fill="#b9d5dc" />
                {buildings.map(({ x, y, width, color }) => (
                    <g key={x}>
                        <rect x={x} y={y} width={width} height={151 - y} fill={color} />
                        <path d={`M${x} ${y}h${width}`} stroke="#f2eee4" strokeWidth="3" />
                        {[0, 1, 2].map((row) => [0, 1].map((column) => (
                            <rect key={`${row}-${column}`} x={x + 10 + column * 17} y={y + 17 + row * 22} width="5" height="9" fill="#5e7880" />
                        )))}
                    </g>
                ))}
                <path d="M190 132 299 99l120 33" fill="#dce2df" />
                <path d="M0 155 199 108 600 161v159H0Z" fill="#687e70" />
                <path d="M0 170 205 116 600 176" fill="none" stroke="#496a58" strokeWidth="24" />
                <path d="M0 188 205 132 600 191" fill="none" stroke="#8faa7b" strokeWidth="8" strokeDasharray="15 13" />
                <path d="M60 230Q74 154 184 139L397 130Q511 149 540 230l-19 59Q411 316 303 316T79 290Z" fill="#e9ece5" stroke="#819493" strokeWidth="8" />
                <path d="M100 225Q111 168 195 161L393 153Q477 165 499 225l-16 43Q390 289 303 289T116 266Z" fill="#194f76" />
                <path d="M119 223Q130 178 202 174L390 165Q463 176 478 222l-11 35Q390 276 303 276T132 255Z" fill="#4e9cc3" />
                <path d="M123 229Q132 182 206 176L390 168Q458 179 474 224m-348 13q84 38 173 38t176-36" fill="none" stroke="#91c9dd" strokeWidth="3" strokeDasharray="5 4" />
                <path d="M174 216 231 184h143l55 32-38 44H210Z" fill="#5d873e" stroke="#f1ebcd" strokeWidth="4" />
                <path d="M215 220 237 188h132l21 32-18 34H230Z" fill="#69994b" opacity=".65" />
                <path d="M302 185v74m-110-43h220m-201 0q14 13 0 27m181-27q-14 13 0 27" fill="none" stroke="#e4e6d5" strokeWidth="2" />
                <path d="M60 230Q74 154 184 139L397 130Q511 149 540 230" fill="none" stroke="#f6f7ee" strokeWidth="22" />
                <g stroke="#cbd6d3" strokeWidth="2.5" strokeLinecap="round">{roofRibs.map(([x, y1, y2]) => <path key={x} d={`M${x} ${y1}v${y2 - y1}`} />)}</g>
                <path d="M0 307 94 288m412 0 94 19" stroke="#454e4c" strokeWidth="18" />
            </svg>
        );
    }

    const laneEdges = [[142, -32], [188, 62], [234, 154], [280, 248], [326, 342], [372, 436], [418, 528], [464, 632]];
    const laneRopes = [[165, 15], [211, 108], [257, 201], [303, 295], [349, 389], [395, 482], [441, 575]];

    return (
        <svg className="hero__scene" viewBox="0 0 600 320" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <rect width="600" height="320" fill="#aedbe7" />
            <path d="M0 103h600v38H0Z" fill="#8babb0" />
            <path d="M0 119h600v15H0Z" fill="#344d59" />
            <path d="M0 133h600v187H0Z" fill="#12a8c8" />
            <path d="M0 133h600v14H0Z" fill="#2587a3" opacity=".6" />
            <path d="M0 152h600M0 192h600M0 244h600M0 300h600" stroke="#59c9dd" strokeWidth="4" opacity=".7" />
            <path d="M0 169q42 7 83 0t83 0 83 0 83 0 83 0 83 0 83 0M0 220q50 9 100 0t100 0 100 0 100 0 100 0 100 0" fill="none" stroke="#8ce1e7" strokeWidth="2" opacity=".6" />
            <g fill="none" stroke="#e8f2ea" strokeWidth="2" opacity=".8">
                {laneEdges.map(([far, near]) => <path key={far} d={`M${far} 145 ${near} 320`} />)}
            </g>
            {laneRopes.map(([far, near], index) => (
                <path
                    key={far}
                    d={`M${far} 145 ${near} 320`}
                    fill="none"
                    stroke={index % 2 === 0 ? "#2457a5" : "#e45c55"}
                    strokeWidth="5"
                    strokeDasharray="9 8"
                />
            ))}
            <g fill="#d9e5df"><rect x="12" y="55" width="95" height="47" /><rect x="487" y="77" width="85" height="26" /><rect x="548" y="33" width="5" height="70" /><rect x="541" y="33" width="19" height="5" /></g>
            <path d="M0 91h600" stroke="#6b8791" strokeWidth="2" />
            <g fill="#f0e8d1">{[438, 457, 476, 495].map((x) => <path key={x} d={`M${x} 65l9-21 9 21Z`} />)}</g>
            <path d="M0 103h600" stroke="#f1e6ce" strokeWidth="8" />
        </svg>
    );
}
