import * as Dialog from "@radix-ui/react-dialog";
import { useState } from "react";
import type { Companion, Factor, Profile, Setting } from "../api/types";
import { getActivities } from "../data/activities";
import { useAsync } from "../data/useAsync";
import { COMPANION_LABELS, FACTOR_LABELS, SETTING_LABELS } from "../lib/labels";
import { preferencesSummary } from "../lib/request";
import { useAppState } from "../state/context";
import ErrorMessage from "./ErrorMessage";
import Icon from "./Icon";
import PrefSlider from "./PrefSlider";

const SETTINGS: Setting[] = ["any", "outdoor", "indoor"];
const PROFILES: Exclude<Profile, "general">[] = ["senior", "stroller", "sensitive"];
const PROFILE_OPTION_LABELS: Record<Exclude<Profile, "general">, string> = {
    senior: "Con personas mayores",
    stroller: "Con carrito",
    sensitive: "Sensible a la contaminación",
};
const COMPANIONS: Companion[] = ["dog", "kids"];
const COMPANION_ICONS: Record<Companion, string> = { dog: "pets", kids: "family" };
const PROFILE_ICONS: Record<Exclude<Profile, "general">, string> = {
    senior: "elderly",
    stroller: "family",
    sensitive: "air",
};
// orden de los pesos: los del prototipo y despues la adecuacion (P-11)
const FACTORS: Factor[] = ["proximity", "green", "air", "weather", "suitability"];
const WEIGHT_OPTIONS = [
    { label: "Nada", percent: 0 },
    { label: "Poca", percent: 25 },
    { label: "Neutra", percent: 50 },
    { label: "Algo", percent: 75 },
    { label: "Mucha", percent: 100 },
] as const;

function km(meters: number): string {
    return `${String(meters / 1000).replace(".", ",")} km`;
}

// Formulario de preferencias (pantallas §6): se usa en /perfil y en el dialogo.
// compact: el panel «Ajustar» de Resultados; todos los campos, sin guardar ni borrar,
// porque cada cambio recalcula al momento
export default function PreferencesForm({ inPanel = false, compact = false }: { inPanel?: boolean; compact?: boolean }) {
    const { preferences, updatePreferences } = useAppState();
    const [savedPreferences, setSavedPreferences] = useState<typeof preferences | null>(null);
    const [weightsReset, setWeightsReset] = useState(false);
    const [confirmClearOpen, setConfirmClearOpen] = useState(false);
    // modal de confirmacion al guardar (mismo estilo que el de borrar)
    const [savedOpen, setSavedOpen] = useState(false);
    const activities = useAsync(() => getActivities(), []);
    // los pesos por defecto los decide el motor (/activities); sin ellos no se pintan los pesos
    const defaults = activities.data?.default_weights ?? null;
    const weights = defaults ? (preferences.weights ?? defaults) : null;

    const setWeight = (factor: Factor, percent: number) => {
        if (!weights) return;
        setWeightsReset(false);
        updatePreferences({ weights: { ...weights, [factor]: percent / 100 } });
    };

    const toggleCompanion = (c: Companion) =>
        updatePreferences({
            companions: preferences.companions.includes(c)
                ? preferences.companions.filter((x) => x !== c)
                : [...preferences.companions, c],
        });

    const toggleProfile = (profile: Exclude<Profile, "general">) => {
        const selectedProfiles = preferences.selectedProfiles ?? (preferences.profile === "general" ? [] : [preferences.profile]);
        const next = selectedProfiles.includes(profile)
            ? selectedProfiles.filter((item) => item !== profile)
            : [...selectedProfiles, profile];
        updatePreferences({ selectedProfiles: next, profile: next.at(-1) ?? "general" });
    };

    return (
        <div className={`prefs-form${compact ? " prefs-form--compact" : ""}`}>
            <div className={`gomad-component gomad-preferences-form${inPanel ? " panel" : ""}`}>
            <PrefSlider
                label="Tiempo disponible"
                controls
                min={10}
                max={180}
                step={5}
                value={preferences.durationMin}
                format={(v) => `${v} min`}
                ariaFormat={(v) => `${v} minutos`}
                onCommit={(v) => updatePreferences({ durationMin: v })}
            />
            <PrefSlider
                label="Distancia máxima a pie"
                controls
                min={500}
                max={10000}
                step={500}
                value={preferences.maxDistanceM}
                format={km}
                onCommit={(v) => updatePreferences({ maxDistanceM: v })}
            />
            <PrefSlider
                label="Ventana horaria"
                controls
                min={1}
                max={12}
                step={1}
                value={preferences.windowHours}
                format={(v) => `${v}h`}
                ariaFormat={(v) => (v === 1 ? "Próxima 1 hora" : `Próximas ${v} horas`)}
                onCommit={(v) => updatePreferences({ windowHours: v })}
            />

            <fieldset className="prefs-form__group">
                <legend className="field__label">Lugar</legend>
                <div className="seg">
                    {SETTINGS.map((s) => (
                        <label key={s} className={`seg__option gomad-option gomad-option-setting-${s}`}>
                            <input
                                type="radio"
                                className={`gomad-field gomad-field-setting-${s}`}
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
                <div className="companion-options">
                    {COMPANIONS.map((c) => (
                        <label key={c} className={`companion-option gomad-option gomad-option-companion-${c}`}>
                            <input
                                type="checkbox"
                                className={`gomad-field gomad-field-companion-${c}`}
                                checked={preferences.companions.includes(c)}
                                onChange={() => toggleCompanion(c)}
                            />
                            <span className="companion-option__label">
                                <Icon name={COMPANION_ICONS[c]} />
                                {COMPANION_LABELS[c]}
                            </span>
                        </label>
                    ))}
                    {PROFILES.map((p) => (
                        <button
                            key={p}
                            type="button"
                            className={`companion-option gomad-action gomad-option gomad-option-profile-${p}`}
                            aria-pressed={(preferences.selectedProfiles ?? [preferences.profile]).includes(p)}
                            onClick={() => toggleProfile(p)}>
                            <Icon name={PROFILE_ICONS[p]} />
                            {PROFILE_OPTION_LABELS[p]}
                        </button>
                    ))}
                </div>
            </fieldset>

            <fieldset className="prefs-form__group">
                <legend className="field__label">¿A qué le das más importancia?</legend>
                {activities.status === "error" ? (
                    <ErrorMessage message="No se han podido cargar los pesos por defecto." onRetry={activities.reload} />
                ) : !weights ? (
                    <p className="muted">Cargando pesos…</p>
                ) : (
                    <>
                        <ul role="list" className="weight-options">
                            {FACTORS.map((f) => (
                                <li key={f} className="weight-options__item">
                                    <fieldset className="weight-option">
                                        <legend className="field__label">Importancia de {FACTOR_LABELS[f].toLowerCase()}</legend>
                                        <div className="seg seg--weights">
                                            {WEIGHT_OPTIONS.map(({ label, percent }) => (
                                                <label key={percent} className={`seg__option gomad-option gomad-option-weight-${f}-${percent}`}>
                                                    <input
                                                        type="radio"
                                                        className={`gomad-field gomad-field-weight-${f}`}
                                                        name={`weight-${f}`}
                                                        value={percent}
                                                        checked={Math.round(weights[f] * 4) * 25 === percent}
                                                        onChange={() => setWeight(f, percent)}
                                                    />
                                                    <span>{label}</span>
                                                </label>
                                            ))}
                                        </div>
                                    </fieldset>
                                </li>
                            ))}
                        </ul>
                    </>
                )}
            </fieldset>

            </div>
            {!compact && (weightsReset || savedPreferences === preferences) && (
                <p className="prefs-form__saved" role="status">
                    {weightsReset ? "Pesos restablecidos a los valores por defecto." : "Preferencias guardadas durante esta sesión."}
                </p>
            )}
            {!compact && <div className="prefs-form__footer">
                <Dialog.Root open={confirmClearOpen} onOpenChange={setConfirmClearOpen}>
                    <Dialog.Trigger asChild>
                        <button type="button" className="button button--quiet gomad-action gomad-action-reset-weights" aria-label="Borrar todas mis preferencias">
                            <span className="prefs-form__footer-label--full" aria-hidden="true">Borrar todas mis preferencias</span>
                            <span className="prefs-form__footer-label--short" aria-hidden="true">Borrar</span>
                        </button>
                    </Dialog.Trigger>
                    <Dialog.Portal>
                        <Dialog.Overlay className="confirm-overlay" />
                        <Dialog.Content className="confirm-dialog">
                            <Dialog.Title className="sheet__title">¿Restablecer los pesos?</Dialog.Title>
                            <Dialog.Description className="muted">
                                Los pesos de importancia volverán a sus valores por defecto.
                            </Dialog.Description>
                            <div className="confirm-dialog__actions">
                                <Dialog.Close asChild>
                                    <button type="button" className="button button--quiet">Cancelar</button>
                                </Dialog.Close>
                                <button type="button" className="button button--primary" onClick={() => {
                                    updatePreferences({ weights: null });
                                    setWeightsReset(true);
                                    setConfirmClearOpen(false);
                                }}>
                                    Borrar
                                </button>
                            </div>
                        </Dialog.Content>
                    </Dialog.Portal>
                </Dialog.Root>
                <Dialog.Root open={savedOpen} onOpenChange={setSavedOpen}>
                    <Dialog.Trigger asChild>
                        <button type="button" className="button button--primary gomad-action gomad-action-save-preferences" aria-label="Guardar preferencias" onClick={() => {
                            setWeightsReset(false);
                            setSavedPreferences(preferences);
                        }}>
                            <span className="prefs-form__footer-label--full" aria-hidden="true">Guardar preferencias</span>
                            <span className="prefs-form__footer-label--short" aria-hidden="true">Guardar</span>
                        </button>
                    </Dialog.Trigger>
                    <Dialog.Portal>
                        <Dialog.Overlay className="confirm-overlay" />
                        <Dialog.Content className="confirm-dialog">
                            <Dialog.Title className="sheet__title">Preferencias guardadas</Dialog.Title>
                            <Dialog.Description className="muted">
                                Las usaremos en tus próximas búsquedas mientras tengas la página abierta.
                            </Dialog.Description>
                            <p className="confirm-dialog__summary">{preferencesSummary(preferences)}</p>
                            <div className="confirm-dialog__actions">
                                <Dialog.Close asChild>
                                    <button type="button" className="button button--primary">Entendido</button>
                                </Dialog.Close>
                            </div>
                        </Dialog.Content>
                    </Dialog.Portal>
                </Dialog.Root>
            </div>}
        </div>
    );
}
