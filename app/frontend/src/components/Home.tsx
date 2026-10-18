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
import Icon, { hasIcon } from "./Icon";
import LocationPicker from "./LocationPicker";

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
        <ul role="list" className="chips gomad-component gomad-moment-chips" aria-label="Ahora en tu zona">
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
    const notice = (location.state as { notice?: string } | null)?.notice;
    const moment = useMoment();
    const live = [
        !origin ? "" : activities.status === "loading" && !activities.data
            ? "Cargando actividades…"
            : activities.data
              ? "Actividades cargadas."
              : "",
        origin && !moment.failed ? momentText(origin.municipality, moment.hour) : "",
    ]
        .filter(Boolean)
        .join(" ");

    const go = (activity: string | null, label?: string) => {
        if (!origin) return;
        setSearch({ activity, label });
        navigate("/resultados");
    };

    return (
        <>
            <Hero title="¿Qué te apetece hacer hoy?">
                <MomentChips hour={moment.hour} failed={moment.failed} />
            </Hero>

            <div className="container home gomad-component gomad-home">
                <p className="sr-only" role="status" aria-live="polite">
                    {live}
                </p>
                {notice && (
                    <p className="notice notice--info" role="note">
                        {notice}
                    </p>
                )}

                <LocationPicker highlight={!origin} />

                {origin && (
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
                                        <button type="button" className="activity gomad-action gomad-action-select-activity" onClick={() => go(a.id, a.label)}>
                                            <span className="activity__icon" aria-hidden="true" data-icon={a.icon}>
                                                {hasIcon(a.icon) && <Icon name={a.icon} />}
                                            </span>
                                            <span>{a.label}</span>
                                        </button>
                                    </li>
                                ))}
                            </ul>
                        )}
                    </section>
                )}

                <div className={`home__secondary${origin ? "" : " home__secondary--single"}`}>
                    {origin && (
                        <button type="button" className="panel panel--action surprise gomad-action gomad-action-surprise" onClick={() => go(null)}>
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
                    )}

                    <Link
                        to="/perfil"
                        className={`panel panel--action prefs${origin ? "" : " prefs--compact"} gomad-action gomad-action-adjust-preferences`}>
                        <span className="surprise__tile" aria-hidden="true">
                            <Icon name="settings" />
                        </span>
                        <span className="surprise__text">
                            <span className="panel__title" id="prefs-titulo">Tus preferencias</span>
                            <span className="muted">{preferencesSummary(preferences)}</span>
                        </span>
                    </Link>

                    {origin && (
                        <Link to="/asistente" className="panel panel--action surprise assistant-link gomad-action gomad-action-open-assistant">
                            <span className="surprise__tile" aria-hidden="true">
                                <Icon name="navigation" />
                            </span>
                            <span className="surprise__text">
                                <span className="panel__title">Asistente de rutas</span>
                                <span className="muted">
                                    Escribe lo que quieres y te propongo una ruta.
                                </span>
                            </span>
                        </Link>
                    )}
                </div>
            </div>
        </>
    );
}
