import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import type { Indicator, IndicatorCategory } from "../api/types";
import { ApiError } from "../data/errors";
import { getMunicipality, listMunicipalities } from "../data/municipality";
import { useAsync } from "../data/useAsync";
import { formatNumber } from "../lib/format";
import { CATEGORY_LABELS } from "../lib/labels";
import { useAppState } from "../state/context";
import ErrorMessage from "./ErrorMessage";
import Icon from "./Icon";
import PageHeading from "./PageHeading";

// Orden de las categorias (PDF de interfaz §5; «social» al final, P-10)
const CATEGORY_ORDER: IndicatorCategory[] = [
    "sport",
    "nature",
    "mobility",
    "health",
    "education",
    "connectivity",
    "social",
];

const CATEGORY_ICONS: Record<IndicatorCategory, string> = {
    sport: "sports_soccer",
    nature: "park",
    mobility: "directions_bus",
    health: "local_hospital",
    education: "school",
    connectivity: "signal_cellular_alt",
    social: "diversity_3",
};

function IndicatorValue({ indicator }: { indicator: Indicator }) {
    const meta = [indicator.year, indicator.source.label].filter(Boolean).join(" · ");
    return (
        <dd className="gomad-component gomad-indicator-value">
            {indicator.value === null ? (
                <strong className="indicator__nodata">Sin datos</strong>
            ) : (
                <strong>
                    {formatNumber(indicator.value)} {indicator.unit}
                </strong>
            )}
            <small>{meta}</small>
        </dd>
    );
}

export default function Municipality() {
    const { ine_code = "" } = useParams();
    const navigate = useNavigate();
    const { setOrigin } = useAppState();
    const data = useAsync(() => getMunicipality(ine_code), [ine_code]);
    const [locating, setLocating] = useState(false);
    const [locateFailed, setLocateFailed] = useState(false);
    const notFound = data.error instanceof ApiError && data.error.status === 404;

    if (notFound) {
        return (
            <section className="container page gomad-component gomad-municipality">
                <PageHeading className="view-title">Municipio no encontrado</PageHeading>
                <p className="view-subtitle">No encontramos ese municipio. Comprueba el código o búscalo en la lista.</p>
                <Link to="/municipios" className="button gomad-action gomad-action-view-municipalities">
                    Ver todos los municipios
                </Link>
            </section>
        );
    }

    const m = data.data && data.data.ine_code === ine_code ? data.data : null;

    const searchHere = async () => {
        if (!m) return;
        setLocating(true);
        setLocateFailed(false);
        try {
            const center = (await listMunicipalities()).find((x) => x.ine_code === m.ine_code);
            if (!center) throw new Error("municipio sin centro");
            setOrigin({
                label: m.name,
                municipality: m.name,
                ine_code: m.ine_code,
                coordinate: { lat: center.lat, lon: center.lon },
                precision: "municipality",
            });
            navigate("/");
        } catch {
            setLocateFailed(true);
        } finally {
            setLocating(false);
        }
    };

    return (
        <section className="container page muni gomad-component gomad-municipality" aria-labelledby="municipio-titulo">
            <Link to="/municipios" className="back-button gomad-action gomad-action-view-municipalities">
                <Icon name="arrow_left" />
                Todos los municipios
            </Link>

            <PageHeading className="view-title" id="municipio-titulo" title={m?.name ?? "Municipio"}>
                {m?.name ?? "Municipio"}
            </PageHeading>

            <p className="sr-only" role="status" aria-live="polite">
                {data.status === "loading" && !m ? "Cargando municipio…" : m ? `${m.name}: datos cargados.` : ""}
            </p>
            {data.status === "loading" && !m && <p className="muted">Cargando municipio…</p>}
            {data.status === "error" && (
                <ErrorMessage message="No se pudo cargar el municipio." onRetry={data.reload} />
            )}

            {m && (
                <>
                    <p className="view-subtitle">
                        Lo que ofrece el municipio para tu bienestar ·{" "}
                        {m.population === null
                            ? "Población: sin datos"
                            : `Población: ${formatNumber(m.population)} habitantes`}
                    </p>
                    <p className="notice notice--warn" role="note">
                        Cifras de ejemplo: todavía no son los datos reales de este municipio.
                    </p>

                    <h2 className="muni__heading">¿Qué ofrece este municipio?</h2>
                    <div className="muni__grid">
                        {CATEGORY_ORDER.map((category) => {
                            const items = m.indicators.filter((i) => i.category === category);
                            if (items.length === 0) return null;
                            const headingId = `cat-${category}`;
                            return (
                                <section key={category} className="panel muni__category" aria-labelledby={headingId}>
                                    <h2 className="panel__title" id={headingId}>
                                        <Icon name={CATEGORY_ICONS[category]} />
                                        {CATEGORY_LABELS[category]}
                                    </h2>
                                    <dl className="indicator-list">
                                        {items.map((i) => (
                                            <div key={i.key} className="indicator">
                                                <dt>{i.label}</dt>
                                                <IndicatorValue indicator={i} />
                                            </div>
                                        ))}
                                    </dl>
                                </section>
                            );
                        })}
                    </div>

                    <section className="panel" aria-labelledby="encaje">
                        <h2 className="panel__title" id="encaje">
                            ¿Cómo encaja contigo?
                        </h2>
                        {m.fit.length > 0 ? (
                            <ul role="list" className="fit-list">
                                {m.fit.map((f) => (
                                    <li key={f}>{f}</li>
                                ))}
                            </ul>
                        ) : (
                            <p className="muted">Sin datos para relacionarlo con tus preferencias.</p>
                        )}
                    </section>

                    {locateFailed && (
                        <ErrorMessage message="No se pudo situar el municipio. Inténtalo de nuevo." />
                    )}
                    <button type="button" className="button button--primary gomad-action gomad-action-search-in-municipality" onClick={searchHere} disabled={locating}>
                        Buscar actividad en {m.name}
                    </button>
                </>
            )}
        </section>
    );
}
