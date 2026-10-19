import type { SourceInfo } from "../api/types";
import { getSources } from "../data/sources";
import { useAsync } from "../data/useAsync";
import { formatTimeAgo } from "../lib/format";
import ErrorMessage from "./ErrorMessage";
import Icon from "./Icon";
import PageHeading from "./PageHeading";

// Referencias oficiales de umbrales: se citan, no se descargan (app/config/sources.yaml)
const OFFICIAL_REFERENCES = new Set(["boe_ica", "sanidad_calor"]);

function refreshText(source: SourceInfo) {
    if (!source.last_refresh) {
        if (source.id.startsWith("config:")) return "Criterio propio: no se descarga";
        if (OFFICIAL_REFERENCES.has(source.id)) return "Referencia oficial: no se descarga";
        return "Sin descargar todavía";
    }
    return formatTimeAgo(source.last_refresh);
}

function failedAfterRefresh(source: SourceInfo) {
    if (!source.last_failure) return false;
    if (!source.last_refresh) return true;
    return Date.parse(source.last_failure) > Date.parse(source.last_refresh);
}

// Categorias de la pagina de fuentes, por id de app/config/sources.yaml; un id nuevo cae en «Otras fuentes»
const SOURCE_GROUPS: { title: string; ids: string[] }[] = [
    {
        title: "Deporte",
        ids: ["eiel_deporte", "nmc_deporte", "ay_idb", "ay_piscinas", "ay_polideportivos", "destination_activity"],
    },
    {
        title: "Parques y naturaleza",
        ids: ["eiel_parques", "vpla_redes", "areas_recreativas", "vias_pecuarias", "nmc_parques", "ay_parques"],
    },
    {
        title: "Aire y tiempo",
        ids: ["aire_dia", "aire_estaciones", "ay_aire", "ay_aire_estaciones", "open_meteo", "cams_air"],
    },
    {
        title: "Rutas y mobiliario urbano",
        ids: ["osm", "ay_fuentes", "ay_bancos", "ay_areas_caninas", "desfibriladores"],
    },
    {
        title: "Salud, educación y servicios",
        ids: ["sanitarios", "farmacias", "educativos", "atencion_social"],
    },
    {
        title: "Transporte y conectividad",
        ids: ["nmc_busparadas", "nmc_estmetro", "nmc_estcerca", "eiel_nucleos"],
    },
    { title: "Mapa y territorio", ids: ["municipios", "callejero", "padron", "mdt05"] },
    { title: "Umbrales oficiales y criterio propio", ids: ["boe_ica", "sanidad_calor"] },
];
const OTHER_GROUP = "Otras fuentes";
const SOURCE_GROUP_ICONS: Record<string, string> = {
    Deporte: "gym",
    "Parques y naturaleza": "nature",
    "Aire y tiempo": "air",
    "Rutas y mobiliario urbano": "route",
    "Salud, educación y servicios": "hospital",
    "Transporte y conectividad": "bike",
    "Mapa y territorio": "municipality",
    "Umbrales oficiales y criterio propio": "criteria",
    [OTHER_GROUP]: "legend",
};

function groupOf(id: string) {
    if (id.startsWith("config:")) return "Umbrales oficiales y criterio propio";
    return SOURCE_GROUPS.find((g) => g.ids.includes(id))?.title ?? OTHER_GROUP;
}

// Grupos en el orden de SOURCE_GROUPS; dentro, el orden del servidor; sin grupos vacios
function groupSources(sources: SourceInfo[]) {
    const titles = [...SOURCE_GROUPS.map((g) => g.title), OTHER_GROUP];
    return titles
        .map((title) => ({ title, sources: sources.filter((s) => groupOf(s.id) === title) }))
        .filter((g) => g.sources.length > 0);
}

function SourcesTable({ title, sources }: { title: string; sources: SourceInfo[] }) {
    return (
        <table className="sources-table" role="table">
            <caption className="sr-only">{title}</caption>
            <thead role="rowgroup">
                <tr role="row">
                    <th scope="col" role="columnheader">Fuente</th>
                    <th scope="col" role="columnheader">Publicador</th>
                    <th scope="col" role="columnheader">Licencia</th>
                    <th scope="col" role="columnheader">Última actualización</th>
                </tr>
            </thead>
            <tbody role="rowgroup">
                {sources.map((s) => (
                    <tr key={s.id} role="row">
                        <td role="cell" data-label="Fuente">
                            <a
                                href={s.url}
                                className="sources-table__link gomad-sources__link gomad-action gomad-action-open-source"
                                target="_blank"
                                rel="noreferrer noopener"
                            >
                                {s.name}
                                <span className="sr-only"> (se abre en una pestaña nueva)</span>
                            </a>
                        </td>
                        <td role="cell" data-label="Publicador">{s.publisher}</td>
                        <td role="cell" data-label="Licencia">{s.license}</td>
                        <td role="cell" data-label="Última actualización">
                            {refreshText(s)}
                            {failedAfterRefresh(s) && (
                                <span className="sources-table__failure">
                                    Última recarga fallida: se muestra el dato anterior.
                                </span>
                            )}
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

export default function Sources() {
    const sources = useAsync(() => getSources(), []);

    return (
        <section className="container page gomad-component gomad-sources" aria-labelledby="fuentes-titulo">
            <PageHeading className="view-title" id="fuentes-titulo">
                Fuentes, licencias y aviso
            </PageHeading>
            <p className="view-subtitle">
                GoMad reúne datos abiertos de la Comunidad de Madrid, el Ayuntamiento de Madrid y otras fuentes
                públicas. Cada dato que ves lleva su fuente y su fecha.
            </p>

            <section className="panel about gomad-component gomad-about" aria-labelledby="quienes-somos">
                <h2 className="panel__title" id="quienes-somos">
                    Quiénes somos
                </h2>
                <p className="about__lead">
                    Dinos qué te apetece hacer y te decimos <strong>dónde, cuándo y por qué camino</strong>.
                </p>
                <p>
                    Somos un equipo del MAD Open Data Challenge 2026. Buscamos que moverse por la
                    Comunidad de Madrid sea más fácil y más sano, con datos públicos al servicio de cualquier persona.
                </p>
                <ol role="list" className="about__steps">
                    <li>
                        <span className="about__icon">
                            <Icon name="running" />
                        </span>
                        <span>
                            <strong>Elige qué hacer:</strong> caminar, correr, nadar, pádel… o «Sorpréndeme».
                        </span>
                    </li>
                    <li>
                        <span className="about__icon">
                            <Icon name="air" />
                        </span>
                        <span>
                            <strong>Te decimos dónde y cuándo:</strong> cruzamos tiempo, aire y zonas verdes para darte
                            la mejor hora.
                        </span>
                    </li>
                    <li>
                        <span className="about__icon">
                            <Icon name="route" />
                        </span>
                        <span>
                            <strong>Te llevamos por la ruta más sana:</strong> más verde, menos tráfico, con fuentes y
                            bancos.
                        </span>
                    </li>
                </ol>
                <p className="muted">Gratis, sin registro y para los 179 municipios.</p>
            </section>

            <section className="panel" aria-labelledby="tabla-fuentes">
                <h2 className="panel__title" id="tabla-fuentes">
                    De dónde salen los datos
                </h2>
                <p className="sr-only" role="status" aria-live="polite">
                    {sources.status === "loading" && !sources.data
                        ? "Cargando fuentes…"
                        : sources.data
                          ? "Fuentes cargadas."
                          : ""}
                </p>
                {sources.status === "loading" && !sources.data && <p className="muted">Cargando fuentes…</p>}
                {sources.status === "error" && (
                    <ErrorMessage message="No se pudieron cargar las fuentes." onRetry={sources.reload} />
                )}
                {sources.data && (
                    <>
                        <p className="muted">Pulsa una categoría para ver sus fuentes.</p>
                        <div className="sources-groups">
                            {groupSources(sources.data.sources).map((g) => {
                                const failures = g.sources.filter(failedAfterRefresh).length;
                                return (
                                    <details key={g.title} className="sources-group gomad-component gomad-sources-group">
                                        <summary className="sources-group__summary gomad-action gomad-action-toggle-source-group">
                                            <Icon name={SOURCE_GROUP_ICONS[g.title]} />
                                            <span className="sources-group__title">{g.title}</span>
                                            <span className="sources-group__meta">
                                                {g.sources.length} {g.sources.length === 1 ? "fuente" : "fuentes"}
                                                {failures > 0 && (
                                                    <span className="sources-group__warning"> · {failures} con aviso</span>
                                                )}
                                            </span>
                                        </summary>
                                        <div className="sources-group__body">
                                            <SourcesTable title={g.title} sources={g.sources} />
                                        </div>
                                    </details>
                                );
                            })}
                        </div>
                    </>
                )}
            </section>

            <section className="panel" aria-labelledby="aviso-medico">
                <h2 className="panel__title" id="aviso-medico">
                    No es consejo médico
                </h2>
                <p>
                    GoMad da recomendaciones orientativas a partir de datos abiertos. No es consejo médico. Si
                    tienes una enfermedad o dudas sobre tu salud, consulta a tu centro de salud.
                </p>
                <p className="muted">
                    Las categorías y recomendaciones de calidad del aire son las del Índice Nacional de Calidad del
                    Aire (BOE-A-2020-10426). Todavía no hay un umbral oficial de calor cargado: no se evalúa el calor
                    hasta tener el del plan de calor del Ministerio de Sanidad.
                </p>
            </section>

            <section className="panel" aria-labelledby="privacidad">
                <h2 className="panel__title" id="privacidad">
                    Privacidad
                </h2>
                <ul role="list" className="fit-list">
                    <li>Sin registro: no te pedimos ningún dato personal ni de salud.</li>
                    <li>
                        Tu ubicación solo se usa para la consulta: no se guarda, no va en la dirección de la página y no
                        se escribe en los registros.
                    </li>
                    <li>
                        Tus preferencias se guardan solo mientras tienes la página abierta; puedes borrarlas en Perfil.
                    </li>
                    <li>
                        Asistente de rutas. Para interpretar tu texto solo se envía el texto; tu ubicación solo se usa
                        para calcular la ruta y no se guarda.
                    </li>
                    <li>
                        Si no encontramos la dirección que escribes en nuestro callejero, la consultamos en el buscador
                        público de Nomecalles (Comunidad de Madrid): solo se envía el texto que escribes (en minúsculas y
                        sin tildes), nunca tu ubicación. El servidor guarda esa respuesta como mucho 1 hora en memoria
                        para no repetir la consulta; no se escribe en disco ni en los registros.
                    </li>
                    <li>Las fuentes tipográficas se sirven desde nuestro servidor, sin terceros.</li>
                    <li>
                        Mapa base: en esta versión el mapa es de ejemplo y no pide teselas a nadie. Cuando llegue, se
                        indicará aquí quién las sirve, con la atribución © OpenStreetMap en el propio mapa.
                    </li>
                </ul>
            </section>

            <section className="panel" aria-labelledby="nuestros-datos">
                <h2 className="panel__title" id="nuestros-datos">
                    Nuestros datos
                </h2>
                <p>
                    Los conjuntos de datos que publiquemos (como el catálogo unificado de destinos) llevarán licencia
                    CC BY 4.0, con la atribución de las fuentes originales.
                </p>
            </section>

        </section>
    );
}
