import { useState } from "react";
import { useNavigate } from "react-router";
import type { SourceInfo } from "../api/types";
import { getActivities } from "../data/activities";
import { listMunicipalities } from "../data/municipality";
import { currentScenario, listScenarios, selectScenario, type ScenarioId } from "../data/scenarios";
import { getSources } from "../data/sources";
import { useAsync } from "../data/useAsync";
import { formatTimeAgo } from "../lib/format";
import { useAppState } from "../state/context";
import ErrorMessage from "./ErrorMessage";
import PageHeading from "./PageHeading";

function refreshText(source: SourceInfo) {
    if (!source.last_refresh) {
        return "Sin descargar todavía";
    }
    return `Actualizado ${formatTimeAgo(source.last_refresh)}`;
}

function failedAfterRefresh(source: SourceInfo) {
    if (!source.last_failure) return false;
    if (!source.last_refresh) return true;
    return Date.parse(source.last_failure) > Date.parse(source.last_refresh);
}

// Selector de escenarios de la demo (solo paso 1; paso 3: quitarlo)
function SampleData() {
    const navigate = useNavigate();
    const { setOrigin, setSearch, updatePreferences } = useAppState();
    const [chosen, setChosen] = useState<ScenarioId>(currentScenario().id);
    const [busy, setBusy] = useState(false);
    const [failed, setFailed] = useState(false);

    const apply = async () => {
        const scenario = listScenarios().find((s) => s.id === chosen)!;
        setBusy(true);
        setFailed(false);
        try {
            selectScenario(scenario.id);
            const [municipalities, activities] = await Promise.all([listMunicipalities(), getActivities()]);
            const m = municipalities.find((x) => x.ine_code === scenario.preset.ine_code)!;
            setOrigin({
                label: `${m.name} (ubicación de ejemplo)`,
                municipality: m.name,
                ine_code: m.ine_code,
                coordinate: { lat: m.lat, lon: m.lon },
                precision: "municipality",
            });
            updatePreferences({ profile: scenario.preset.profile, companions: scenario.preset.companions, weights: null });
            const activity = scenario.preset.activity;
            setSearch({
                activity,
                label: activities.activities.find((a) => a.id === activity)?.label,
            });
            navigate(scenario.preset.path);
        } catch {
            setFailed(true);
        } finally {
            setBusy(false);
        }
    };

    return (
        <section className="panel" aria-labelledby="ejemplo-titulo">
            <h2 className="panel__title" id="ejemplo-titulo">
                Datos de ejemplo
            </h2>
            <p className="muted">
                Esta versión todavía no está conectada a los portales: enseña datos de ejemplo. Elige una de las
                personas de la demo para ver cómo cambia la respuesta.
            </p>
            <fieldset className="prefs-form__group">
                <legend className="sr-only">Datos de ejemplo</legend>
                <div className="option-list">
                    {listScenarios().map((s) => (
                        <label key={s.id} className="option option--stacked">
                            <input
                                type="radio"
                                name="scenario"
                                checked={chosen === s.id}
                                onChange={() => setChosen(s.id)}
                            />
                            <span>
                                <strong>{s.label}</strong>
                                <span className="muted">{s.description}</span>
                            </span>
                        </label>
                    ))}
                </div>
            </fieldset>
            {failed && <ErrorMessage message="No se pudo cargar el ejemplo." onRetry={apply} />}
            <button type="button" className="button button--primary" onClick={apply} disabled={busy}>
                Ver este ejemplo
            </button>
        </section>
    );
}

export default function Sources() {
    const sources = useAsync(() => getSources(), []);

    return (
        <section className="container page" aria-labelledby="fuentes-titulo">
            <PageHeading className="view-title" id="fuentes-titulo">
                Fuentes, licencias y aviso
            </PageHeading>
            <p className="view-subtitle">
                GoMad reúne datos abiertos de la Comunidad de Madrid, el Ayuntamiento de Madrid y otras fuentes
                públicas. Cada dato que ves lleva su fuente y su fecha.
            </p>

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
                    <table className="sources-table" role="table">
                        <caption className="sr-only">Fuentes de datos</caption>
                        <thead role="rowgroup">
                            <tr role="row">
                                <th scope="col" role="columnheader">Fuente</th>
                                <th scope="col" role="columnheader">Publicador</th>
                                <th scope="col" role="columnheader">Licencia</th>
                                <th scope="col" role="columnheader">Actualizado</th>
                            </tr>
                        </thead>
                        <tbody role="rowgroup">
                            {sources.data.sources.map((s) => (
                                <tr key={s.id} role="row">
                                    <td role="cell" data-label="Fuente">
                                        <a href={s.url} className="sources-table__link" rel="noreferrer noopener">
                                            {s.name}
                                        </a>
                                    </td>
                                    <td role="cell" data-label="Publicador">{s.publisher}</td>
                                    <td role="cell" data-label="Licencia">{s.license}</td>
                                    <td role="cell" data-label="Actualizado">
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
                    Aire (BOE-A-2020-10426). El umbral de calor es, por ahora, de criterio propio, a la espera del
                    plan de calor del Ministerio de Sanidad.
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

            <SampleData />
        </section>
    );
}
