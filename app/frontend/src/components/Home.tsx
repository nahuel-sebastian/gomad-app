import { useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router";
import type { Activity, HourEvaluation } from "../api/types";
import { getActivities } from "../data/activities";
import { recommend } from "../data/recommend";
import { useAsync } from "../data/useAsync";
import { aqiLabel } from "../lib/labels";
import { buildRecommendRequest, preferencesKey, preferencesSummary } from "../lib/request";
import { useAppState } from "../state/context";
import Chip, { AqiChip } from "./Chip";
import ErrorMessage from "./ErrorMessage";
import Hero from "./Hero";
import Icon from "./Icon";
import LocationPicker from "./LocationPicker";
import PreferencesDialog from "./PreferencesDialog";

type MomentHour = HourEvaluation | undefined;

// Estado del momento (P-01): primera hora de la recomendacion de la zona
function useMoment() {
    const { origin, preferences } = useAppState();
    const moment = useAsync(
        () =>
            origin
                ? recommend(buildRecommendRequest(origin.coordinate, null, preferences, { limit: 1 }))
                : Promise.resolve(null),
        [preferencesKey(null, preferences, origin?.coordinate ?? null)],
    );
    return { failed: moment.status === "error", hour: moment.data?.results[0]?.hours[0] as MomentHour };
}

// Texto para la region viva: lo mismo que dicen las pastillas
function momentText(municipality: string, hour: MomentHour): string {
    if (!hour) return "";
    const temp = hour.temperature_c === null ? "temperatura sin datos" : `${hour.temperature_c} °C`;
    return `Ahora en ${municipality}: ${temp}, aire ${aqiLabel(hour.aqi_category).toLowerCase()}.`;
}

function MomentChips({ hour, failed }: { hour: MomentHour; failed: boolean }) {
    const { origin } = useAppState();

    return (
        <ul role="list" className="chips" aria-label="Ahora en tu zona">
            <li>
                <Chip tone="info" icon="location_on">
                    {origin ? origin.municipality : "Sin ubicación todavía"}
                </Chip>
            </li>
            {origin && failed && (
                <li>
                    <Chip tone="nodata" icon="cloud_off">
                        Tiempo y aire: sin datos
                    </Chip>
                </li>
            )}
            {origin && !failed && hour && (
                <>
                    <li>
                        <Chip tone={hour.temperature_c === null ? "nodata" : "info"} icon="thermostat">
                            {hour.temperature_c === null ? "Temperatura: sin datos" : `${hour.temperature_c} °C`}
                        </Chip>
                    </li>
                    <li>
                        <AqiChip category={hour.aqi_category} />
                    </li>
                </>
            )}
        </ul>
    );
}

export default function Home() {
    const navigate = useNavigate();
    const location = useLocation();
    const { origin, setSearch, preferences } = useAppState();
    const activities = useAsync(() => getActivities(), []);
    const [pending, setPending] = useState<{ activity: string | null; label?: string } | null>(null);
    const askRef = useRef<HTMLParagraphElement>(null);
    const notice = (location.state as { notice?: string } | null)?.notice;
    const moment = useMoment();
    const live = [
        activities.status === "loading" && !activities.data
            ? "Cargando actividades…"
            : activities.data
              ? "Actividades cargadas."
              : "",
        origin && !moment.failed ? momentText(origin.municipality, moment.hour) : "",
    ]
        .filter(Boolean)
        .join(" ");

    const go = (activity: string | null, label?: string) => {
        if (!origin) {
            setPending({ activity, label });
            // el foco va al aviso, junto a la ubicacion
            requestAnimationFrame(() => askRef.current?.focus());
            return;
        }
        setSearch({ activity, label });
        navigate("/resultados");
    };

    return (
        <>
            <Hero title="¿Qué te apetece hacer hoy?">
                <MomentChips hour={moment.hour} failed={moment.failed} />
            </Hero>

            <div className="container home">
                <p className="sr-only" role="status" aria-live="polite">
                    {live}
                </p>
                {notice && (
                    <p className="notice notice--info" role="note">
                        {notice}
                    </p>
                )}

                {pending && !origin && (
                    <p className="notice notice--info" ref={askRef} tabIndex={-1}>
                        Antes, dinos dónde estás para buscar{" "}
                        {pending.activity === null ? "un plan" : `«${pending.label}»`}.
                    </p>
                )}

                <LocationPicker
                    highlight={pending !== null && !origin}
                    onPicked={() => {
                        if (pending) {
                            setSearch(pending);
                            setPending(null);
                            navigate("/resultados");
                        }
                    }}
                />

                <section className="panel" aria-labelledby="actividades-titulo">
                    <h2 className="panel__title" id="actividades-titulo">
                        Elige una actividad
                    </h2>
                    {activities.status === "loading" && !activities.data && (
                        <p className="muted">
                            Cargando actividades…
                        </p>
                    )}
                    {activities.status === "error" && (
                        <ErrorMessage
                            message="No se pudieron cargar las actividades."
                            onRetry={activities.reload}
                        />
                    )}
                    {activities.data && (
                        <ul role="list" className="activities" aria-label="Actividades">
                            {activities.data.activities.map((a: Activity) => (
                                <li key={a.id}>
                                    <button type="button" className="activity" onClick={() => go(a.id, a.label)}>
                                        <span className="activity__tile" aria-hidden="true">
                                            <Icon name={a.icon} />
                                        </span>
                                        <span>{a.label}</span>
                                    </button>
                                </li>
                            ))}
                        </ul>
                    )}
                </section>

                <div className="home__secondary">
                    <button type="button" className="panel panel--action surprise" onClick={() => go(null)}>
                        <span className="surprise__tile" aria-hidden="true">
                            <Icon name="auto_awesome" />
                        </span>
                        <span className="surprise__text">
                            <span className="panel__title">Sorpréndeme</span>
                            <span className="muted">
                                Te propongo un plan según tu ubicación y tu tiempo libre.
                            </span>
                        </span>
                    </button>

                    <section className="panel prefs" aria-labelledby="prefs-titulo">
                        <div className="prefs__text">
                            <h2 className="muted prefs__title" id="prefs-titulo">
                                Tus preferencias
                            </h2>
                            <strong>{preferencesSummary(preferences)}</strong>
                        </div>
                        <PreferencesDialog
                            trigger={
                                <button type="button" className="button" aria-label="Ajustar preferencias">
                                    <span>Ajustar</span>
                                </button>
                            }
                        />
                    </section>
                </div>

                <Link to="/asistente" className="panel panel--action assistant-link">
                    <span className="panel__title">Asistente de rutas</span>
                    <span className="muted">
                        Escribe lo que quieres («5 km andando, con fuentes y bancos») y te propongo una ruta.
                    </span>
                </Link>
            </div>
        </>
    );
}
