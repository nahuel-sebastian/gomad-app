import type { Companion, Factor, Profile, Setting, Weights } from "../api/types";
import { getActivities } from "../data/activities";
import { useAsync } from "../data/useAsync";
import { COMPANION_LABELS, FACTOR_LABELS, PROFILE_LABELS, SETTING_LABELS } from "../lib/labels";
import { useAppState } from "../state/context";
import PrefSlider from "./PrefSlider";

const SETTINGS: Setting[] = ["any", "outdoor", "indoor"];
const PROFILES: Profile[] = ["general", "senior", "stroller", "sensitive"];
const COMPANIONS: Companion[] = ["dog", "kids"];
// orden de los pesos: los del prototipo y despues la adecuacion (P-11)
const FACTORS: Factor[] = ["proximity", "green", "air", "weather", "suitability"];

// Pesos por defecto mientras carga /activities (los de weights.yaml)
const FALLBACK_WEIGHTS: Weights = { proximity: 0.3, suitability: 0.25, green: 0.2, air: 0.15, weather: 0.1 };

function importance(percent: number): string {
    if (percent === 0) return "ninguna";
    if (percent <= 20) return "baja";
    if (percent <= 40) return "media";
    if (percent <= 70) return "alta";
    return "máxima";
}

function km(meters: number): string {
    return `${String(meters / 1000).replace(".", ",")} km`;
}

// Formulario de preferencias (pantallas §6): se usa en /perfil y en el dialogo
export default function PreferencesForm() {
    const { preferences, updatePreferences, resetPreferences } = useAppState();
    const activities = useAsync(() => getActivities(), []);
    const defaults = activities.data?.default_weights ?? FALLBACK_WEIGHTS;
    const weights = preferences.weights ?? defaults;

    const setWeight = (factor: Factor, percent: number) =>
        updatePreferences({ weights: { ...weights, [factor]: percent / 100 } });

    const toggleCompanion = (c: Companion) =>
        updatePreferences({
            companions: preferences.companions.includes(c)
                ? preferences.companions.filter((x) => x !== c)
                : [...preferences.companions, c],
        });

    return (
        <div className="prefs-form">
            <PrefSlider
                label="Tiempo disponible"
                min={10}
                max={180}
                step={5}
                value={preferences.durationMin}
                format={(v) => `${v} minutos`}
                onCommit={(v) => updatePreferences({ durationMin: v })}
            />
            <PrefSlider
                label="Distancia máxima a pie"
                min={500}
                max={10000}
                step={500}
                value={preferences.maxDistanceM}
                format={km}
                onCommit={(v) => updatePreferences({ maxDistanceM: v })}
            />
            <PrefSlider
                label="Ventana horaria"
                min={1}
                max={12}
                step={1}
                value={preferences.windowHours}
                format={(v) => (v === 1 ? "Próxima 1 hora" : `Próximas ${v} horas`)}
                onCommit={(v) => updatePreferences({ windowHours: v })}
            />

            <fieldset className="prefs-form__group">
                <legend className="field__label">Lugar</legend>
                <div className="seg">
                    {SETTINGS.map((s) => (
                        <label key={s} className="seg__option">
                            <input
                                type="radio"
                                name="setting"
                                checked={preferences.setting === s}
                                onChange={() => updatePreferences({ setting: s })}
                            />
                            <span>{SETTING_LABELS[s]}</span>
                        </label>
                    ))}
                </div>
            </fieldset>

            <fieldset className="prefs-form__group">
                <legend className="field__label">Perfil (opcional)</legend>
                <div className="option-list">
                    {PROFILES.map((p) => (
                        <label key={p} className="option">
                            <input
                                type="radio"
                                name="profile"
                                checked={preferences.profile === p}
                                onChange={() => updatePreferences({ profile: p })}
                            />
                            <span>{PROFILE_LABELS[p]}</span>
                        </label>
                    ))}
                </div>
            </fieldset>

            <fieldset className="prefs-form__group">
                <legend className="field__label">Salgo con…</legend>
                <div className="option-list">
                    {COMPANIONS.map((c) => (
                        <label key={c} className="option">
                            <input
                                type="checkbox"
                                checked={preferences.companions.includes(c)}
                                onChange={() => toggleCompanion(c)}
                            />
                            <span>{COMPANION_LABELS[c]}</span>
                        </label>
                    ))}
                </div>
            </fieldset>

            <fieldset className="prefs-form__group">
                <legend className="field__label">¿A qué le das más importancia?</legend>
                <p className="muted">
                    Pesos de la nota (criterio propio). Si los pones todos a 0, se usan los de por defecto.
                </p>
                {FACTORS.map((f) => (
                    <PrefSlider
                        key={f}
                        label={`Importancia de ${FACTOR_LABELS[f].toLowerCase()}`}
                        min={0}
                        max={100}
                        step={5}
                        value={Math.round(weights[f] * 100)}
                        format={(v) => `${v} %, importancia ${importance(v)}`}
                        onCommit={(v) => setWeight(f, v)}
                    />
                ))}
                <button type="button" className="button" onClick={() => updatePreferences({ weights: null })}>
                    Restablecer valores por defecto
                </button>
            </fieldset>

            <button type="button" className="button button--quiet" onClick={resetPreferences}>
                Borrar todas mis preferencias
            </button>
        </div>
    );
}
