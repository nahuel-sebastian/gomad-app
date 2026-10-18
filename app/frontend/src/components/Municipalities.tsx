import { useId, useState } from "react";
import { Link, useNavigate } from "react-router";
import { distanceM } from "../data/livePosition";
import { listMunicipalities, type MunicipalityItem } from "../data/municipality";
import { useAsync } from "../data/useAsync";
import { formatDistance } from "../lib/format";
import { normalize } from "../lib/text";
import { useAppState } from "../state/context";
import ErrorMessage from "./ErrorMessage";
import PageHeading from "./PageHeading";

// cuantos municipios cercanos se ensenan (por distancia, no por calidad: no es un ranking)
const NEARBY_COUNT = 4;

// letra del indice: la inicial sin tilde («Ávila» va en la A)
function initial(name: string): string {
    return normalize(name).charAt(0).toUpperCase();
}

function groupByInitial(items: MunicipalityItem[]): [string, MunicipalityItem[]][] {
    const groups = new Map<string, MunicipalityItem[]>();
    for (const m of [...items].sort((a, b) => a.name.localeCompare(b.name, "es"))) {
        const letter = initial(m.name);
        groups.set(letter, [...(groups.get(letter) ?? []), m]);
    }
    return [...groups.entries()];
}

// Selector de municipio (P-09): los 179 agrupados por letra con indice A-Z, buscador fijo
// y, si hay ubicacion, los mas cercanos. Sin ningun orden de calidad
export default function Municipalities() {
    const list = useAsync(() => listMunicipalities(), []);
    const { origin } = useAppState();
    const navigate = useNavigate();
    const [query, setQuery] = useState("");
    const inputId = useId();
    const headingPrefix = useId();
    const q = normalize(query);
    const shown = (list.data ?? []).filter((m) => normalize(m.name).includes(q));
    const groups = groupByInitial(shown);
    // el municipio de la ubicacion primero (d = null): el centro de otro puede quedar mas cerca
    const nearby =
        origin && list.data
            ? list.data
                  .map((m) => ({
                      m,
                      d: m.ine_code === origin.ine_code ? null : distanceM(origin.coordinate, { lat: m.lat, lon: m.lon }),
                  }))
                  .sort((a, b) => (a.d ?? -1) - (b.d ?? -1))
                  .slice(0, NEARBY_COUNT)
            : [];
    const letterId = (letter: string) => `${headingPrefix}-${letter}`;

    const goToLetter = (letter: string) => {
        const heading = document.getElementById(letterId(letter));
        heading?.scrollIntoView?.({ block: "start" });
        heading?.focus();
    };

    return (
        <section className="container page gomad-component gomad-municipalities" aria-labelledby="municipios-titulo">
            <PageHeading className="view-title" id="municipios-titulo">
                Municipios
            </PageHeading>
            <p className="view-subtitle">
                Mira qué ofrece cada uno de los 179 municipios de la Comunidad de Madrid para moverte y
                cuidarte. Sin rankings: cada municipio se ve por sí solo.
            </p>

            <div className="muni-finder">
                <form
                    className="panel muni-finder__search"
                    role="search"
                    onSubmit={(e) => {
                        e.preventDefault();
                        // con un solo resultado, Enter lo abre
                        if (shown.length === 1) navigate(`/municipios/${shown[0].ine_code}`);
                    }}>
                    <label htmlFor={inputId} className="field__label">
                        Busca un municipio
                    </label>
                    <input
                        id={inputId}
                        className="field__input gomad-field gomad-field-municipality-search"
                        type="search"
                        autoComplete="off"
                        value={query}
                        onChange={(e) => setQuery(e.target.value)}
                    />
                </form>

                {groups.length > 0 && (
                    <nav className="muni-index" aria-label="Índice alfabético">
                        <ul role="list" className="muni-index__list">
                            {groups.map(([letter]) => (
                                <li key={letter}>
                                    <button
                                        type="button"
                                        className="muni-index__letter gomad-action gomad-action-jump-to-letter"
                                        aria-label={`Ir a la ${letter}`}
                                        onClick={() => goToLetter(letter)}>
                                        {letter}
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </nav>
                )}
            </div>

            <p className="muted muni-list__count" role="status" aria-live="polite">
                {list.data
                    ? shown.length === 0
                        ? `Ningún municipio coincide con «${query}».`
                        : `${shown.length} ${shown.length === 1 ? "municipio" : "municipios"}`
                    : ""}
            </p>

            {list.status === "loading" && !list.data && <p className="muted">Cargando municipios…</p>}
            {list.status === "error" && (
                <ErrorMessage message="No se pudo cargar la lista de municipios." onRetry={list.reload} />
            )}

            {nearby.length > 0 && !q && (
                <section className="muni-nearby" aria-labelledby={`${headingPrefix}-near`}>
                    <h2 className="muni-section__title" id={`${headingPrefix}-near`}>
                        Cerca de ti
                    </h2>
                    <ul role="list" className="muni-nearby__list">
                        {nearby.map(({ m, d }) => (
                            <li key={m.ine_code}>
                                <Link
                                    to={`/municipios/${m.ine_code}`}
                                    className="muni-nearby__link gomad-action gomad-action-open-municipality">
                                    <span className="muni-list__name">{m.name}</span>
                                    <span className="muni-nearby__distance">{d === null ? "Estás aquí" : formatDistance(d)}</span>
                                </Link>
                            </li>
                        ))}
                    </ul>
                </section>
            )}

            {list.data && shown.length > 0 && (
                <section className="muni-all" aria-label="Todos los municipios">
                    {groups.map(([letter, items]) => (
                        <section key={letter} className="muni-group" aria-labelledby={letterId(letter)}>
                            <h2 className="muni-group__letter" id={letterId(letter)} tabIndex={-1}>
                                {letter}
                            </h2>
                            <ul role="list" className="muni-list">
                                {items.map((m) => (
                                    <li key={m.ine_code}>
                                        <Link
                                            to={`/municipios/${m.ine_code}`}
                                            className="muni-list__link gomad-action gomad-action-open-municipality">
                                            <span className="muni-list__name">{m.name}</span>
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </section>
                    ))}
                </section>
            )}
        </section>
    );
}
