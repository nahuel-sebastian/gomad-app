import { useId, useState } from "react";
import { Link } from "react-router";
import { listMunicipalities } from "../data/municipality";
import { useAsync } from "../data/useAsync";
import { normalize } from "../lib/text";
import ErrorMessage from "./ErrorMessage";
import PageHeading from "./PageHeading";

// Selector de municipio (P-09): lista de los 179, sin ningun orden de calidad
export default function Municipalities() {
    const list = useAsync(() => listMunicipalities(), []);
    const [query, setQuery] = useState("");
    const inputId = useId();
    const q = normalize(query);
    const shown = (list.data ?? []).filter((m) => normalize(m.name).includes(q));

    return (
        <section className="container page" aria-labelledby="municipios-titulo">
            <PageHeading className="view-title" id="municipios-titulo">
                Municipios
            </PageHeading>
            <p className="view-subtitle">
                Mira qué ofrece cada uno de los 179 municipios de la Comunidad de Madrid para moverte y
                cuidarte. Sin rankings: cada municipio se ve por sí solo.
            </p>

            <div className="panel">
                <label htmlFor={inputId} className="field__label">
                    Busca un municipio
                </label>
                <input
                    id={inputId}
                    className="field__input"
                    type="search"
                    autoComplete="off"
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                />
                <p className="muted" role="status" aria-live="polite">
                    {list.data
                        ? shown.length === 0
                            ? `Ningún municipio coincide con «${query}».`
                            : `${shown.length} ${shown.length === 1 ? "municipio" : "municipios"}`
                        : ""}
                </p>
            </div>

            {list.status === "loading" && !list.data && <p className="muted">Cargando municipios…</p>}
            {list.status === "error" && (
                <ErrorMessage message="No se pudo cargar la lista de municipios." onRetry={list.reload} />
            )}

            {list.data && (
                <ul className="muni-list" aria-label="Municipios de la Comunidad de Madrid">
                    {shown.map((m) => (
                        <li key={m.ine_code}>
                            <Link to={`/municipios/${m.ine_code}`} className="muni-list__link">
                                {m.name}
                            </Link>
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
}
