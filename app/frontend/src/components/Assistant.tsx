import { useId, useRef, useState, type Dispatch, type FormEvent, type SetStateAction } from "react";
import { Link } from "react-router";
import type { AssistantParams, AssistantRouteResponse, Avoid, PassBy } from "../api/types";
import { assistantRoute, interpret } from "../data/assistant";
import { ApiError } from "../data/errors";
import { formatDistance, formatMinutes } from "../lib/format";
import { AVOID_LABELS, PASS_BY_LABELS } from "../lib/labels";
import { useAppState } from "../state/context";
import ErrorMessage from "./ErrorMessage";
import Hero from "./Hero";
import Icon from "./Icon";
import LocationPicker from "./LocationPicker";
import MapView from "./MapView";
import PageHeading from "./PageHeading";

const PASS_BY: PassBy[] = ["park", "fountain", "bench", "supermarket", "dog_area", "playground"];
const AVOID: Avoid[] = ["traffic", "hills"];
const PASS_BY_ICONS: Record<PassBy, string> = {
    park: "eco",
    fountain: "water",
    bench: "bench",
    supermarket: "shopping_cart",
    dog_area: "pets",
    playground: "playground",
};
const AVOID_ICONS: Record<Avoid, string> = { traffic: "traffic", hills: "mountain" };
const EXAMPLE = "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado";

function conditionIcon(condition: string): string {
    const label = condition.toLocaleLowerCase("es");
    if (label.startsWith("distancia")) return "route";
    if (label.startsWith("duración")) return "calendar_clock";
    if (label === "solo ida") return "navigation";
    if (label === "ida y vuelta") return "route";
    if (label.startsWith("pasar por:")) {
        const type = PASS_BY.find((p) => label.includes(PASS_BY_LABELS[p].toLocaleLowerCase("es")));
        return type ? PASS_BY_ICONS[type] : "route";
    }
    if (label.startsWith("evitar:")) {
        const type = AVOID.find((a) => label.includes(AVOID_LABELS[a].toLocaleLowerCase("es")));
        return type ? AVOID_ICONS[type] : "criteria";
    }
    if (label.includes("fuentes")) return "water";
    return "criteria";
}

function explanationSentences(explanation: string): string[] {
    return explanation.trim().split(/(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿])/u).filter(Boolean);
}

function RouteExplanation({ explanation, conditions }: Pick<AssistantRouteResponse, "explanation" | "conditions">) {
    const unmet = conditions.filter((condition) => !condition.met);
    return (
        <ul role="list" className="assistant__route-description" aria-label="Resumen de la ruta">
            {explanationSentences(explanation).map((sentence, index) => {
                if (sentence.startsWith("No cumple:") && unmet.length > 0) {
                    return (
                        <li key={index}>
                            <strong>No cumple:</strong>
                            <ul role="list" className="assistant__unmet-list">
                                {unmet.map(({ condition }) => (
                                    <li key={condition}>
                                        <Icon name="close" aria-hidden="true" />
                                        <strong>{condition}</strong>
                                    </li>
                                ))}
                            </ul>
                        </li>
                    );
                }
                const match = sentence.match(/^(Ruta saludable|Cumple \d+ de \d+ condiciones)(.*)$/u);
                return <li key={index}>{match ? <><strong>{match[1]}</strong>{match[2]}</> : sentence}</li>;
            })}
        </ul>
    );
}

function NumberStepper({ id, label, value, setValue, min, max, step, inputMode, className }: {
    id: string;
    label: string;
    value: string;
    setValue: Dispatch<SetStateAction<string>>;
    min: number;
    max: number;
    step: number;
    inputMode: "decimal" | "numeric";
    className: string;
}) {
    const current = value.trim() === "" ? null : Number(value.replace(",", "."));
    const changeBy = (direction: -1 | 1) => {
        const next = current === null || !Number.isFinite(current)
            ? min
            : Math.min(max, Math.max(min, Math.round((current + direction * step) * 10) / 10));
        setValue(String(next));
    };
    return (
        <div>
            <label className="field__label" htmlFor={id}>{label}</label>
            <div className="assistant__stepper">
                <button type="button" className="pref-slider__step" aria-label={`Reducir ${label}`} disabled={current === null || current <= min} onClick={() => changeBy(-1)}>
                    <Icon name="remove" />
                </button>
                <input id={id} className={`field__input gomad-field ${className}`} type="number" inputMode={inputMode} min={min} max={max} step={step} value={value} onChange={(event) => setValue(event.target.value)} />
                <button type="button" className="pref-slider__step" aria-label={`Aumentar ${label}`} disabled={current !== null && current >= max} onClick={() => changeBy(1)}>
                    <Icon name="add" />
                </button>
            </div>
        </div>
    );
}

type Interpretation =
    | { status: "idle" }
    | { status: "loading" }
    | { status: "clarification"; text: string }
    | { status: "rejection"; text: string }
    | { status: "understood" }
    | { status: "error" };

type RouteState =
    | { status: "idle" }
    | { status: "loading" }
    | { status: "error"; message: string | null }
    | { status: "done"; data: AssistantRouteResponse };

// Asistente de rutas (F6). Funciona sin IA: el bloque «Lo que he entendido»
// es tambien el formulario. A /assistant/interpret solo va el texto.
export default function Assistant() {
    const { origin } = useAppState();
    const textId = useId();
    const textRef = useRef<HTMLTextAreaElement>(null);
    const [text, setText] = useState("");
    const [interpretation, setInterpretation] = useState<Interpretation>({ status: "idle" });
    const [activity, setActivity] = useState<AssistantParams["activity"]>("walk");
    const [distance, setDistance] = useState("5");
    const [duration, setDuration] = useState("");
    // true si la persona ha escrito distancia o duracion a mano: una aclaracion no se las borra
    const [amountTouched, setAmountTouched] = useState(false);
    const [loop, setLoop] = useState(true);
    const [passBy, setPassBy] = useState<PassBy[]>([]);
    const [avoid, setAvoid] = useState<Avoid[]>([]);
    const [formError, setFormError] = useState<string | null>(null);
    const [needLocation, setNeedLocation] = useState(false);
    const [route, setRoute] = useState<RouteState>({ status: "idle" });
    const lastParams = useRef<AssistantParams | null>(null);

    // partial: respuesta con aclaracion. Suma pasar por y evitar a lo marcado a mano y, sin cantidad, solo vacia
    // la distancia si la persona no la habia escrito (asi el campo vacio casa con «Solo falta la distancia»)
    const applyParams = (p: AssistantParams, partial = false) => {
        setActivity(p.activity);
        if (p.distance_km != null || p.duration_min != null || !(partial && amountTouched)) {
            setDistance(p.distance_km != null ? String(p.distance_km) : "");
            setDuration(p.duration_min != null ? String(p.duration_min) : "");
        }
        setLoop(p.loop ?? true);
        const merge = <T,>(current: T[], next: T[]) => (partial ? [...new Set([...current, ...next])] : next);
        setPassBy((current) => merge(current, p.pass_by ?? []));
        setAvoid((current) => merge(current, p.avoid ?? []));
    };

    const onInterpret = async (event: FormEvent) => {
        event.preventDefault();
        if (text.trim().length < 3) {
            setInterpretation({ status: "clarification", text: "Escribe un poco más. Por ejemplo: «5 km andando por un parque»." });
            return;
        }
        setInterpretation({ status: "loading" });
        try {
            // privacidad: solo el texto, nunca la ubicacion
            const result = await interpret(text.trim());
            if (result.rejection) {
                setInterpretation({ status: "rejection", text: result.rejection });
            } else if (result.clarification) {
                // puede traer tambien lo que si ha entendido: se apunta en el formulario
                if (result.params) applyParams(result.params, true);
                setInterpretation({ status: "clarification", text: result.clarification });
                textRef.current?.focus();
            } else if (result.params) {
                applyParams(result.params);
                setInterpretation({ status: "understood" });
            }
        } catch {
            setInterpretation({ status: "error" });
        }
    };

    const run = async (params: AssistantParams) => {
        if (!origin) return;
        lastParams.current = params;
        setRoute({ status: "loading" });
        try {
            const data = await assistantRoute({ origin: origin.coordinate, params });
            setRoute({ status: "done", data });
        } catch (error) {
            // 422: el servidor explica por que no hay ruta (p. ej. ningun parque cerca)
            const message = error instanceof ApiError && error.status === 422 ? error.message : null;
            setRoute({ status: "error", message });
        }
    };

    const onCalculate = (event: FormEvent) => {
        event.preventDefault();
        const km = distance.trim() === "" ? null : Number(distance.replace(",", "."));
        const min = duration.trim() === "" ? null : Number(duration);
        if (km === null && min === null) {
            setFormError("Indica una distancia o una duración.");
            return;
        }
        if (km !== null && (!(km > 0) || km > 42)) {
            setFormError("La distancia tiene que estar entre 0 y 42 km.");
            return;
        }
        if (km === null && min !== null && (!(min > 0) || min > 480)) {
            setFormError("La duración tiene que estar entre 1 y 480 minutos.");
            return;
        }
        setFormError(null);
        if (!origin) {
            setNeedLocation(true);
            return;
        }
        run({
            activity,
            distance_km: km,
            duration_min: km === null ? min : null,
            loop,
            pass_by: passBy,
            avoid,
        });
    };

    const toggle = <T,>(list: T[], value: T) =>
        list.includes(value) ? list.filter((v) => v !== value) : [...list, value];

    const done = route.status === "done" ? route.data : null;
    const met = done ? done.conditions.filter((c) => c.met).length : 0;
    const announcement =
        route.status === "loading"
            ? "Calculando la ruta…"
            : done
              ? `Ruta calculada: cumple ${met} de ${done.conditions.length} condiciones.`
              : needLocation && !origin
                ? "Antes, dinos dónde estás para calcular la ruta."
                : interpretation.status === "rejection" || interpretation.status === "clarification"
                  ? interpretation.text
                  : interpretation.status === "understood"
                    ? "He rellenado los campos con lo que he entendido. Revísalos y calcula la ruta."
                    : "";

    return (
        <section className="container page assistant gomad-component gomad-assistant" aria-labelledby="asistente-titulo">
            <Hero variant="assistant" className="assistant-hero">
                <Link to="/" className="detail-media__back gomad-action gomad-action-back-to-home">
                    <Icon name="arrow_left" />
                    Volver
                </Link>
            </Hero>
            <PageHeading className="view-title" id="asistente-titulo">
                Asistente de rutas
            </PageHeading>
            <p className="view-subtitle">
                El asistente solo interpreta tu texto y redacta la respuesta con los resultados del motor; la ruta
                la calcula el motor con datos abiertos. También puedes rellenar los campos a mano.
            </p>
            <p className="sr-only" role="status" aria-live="polite">
                {announcement}
            </p>

            <section className="panel assistant__request">
                <form className="assistant__form" onSubmit={onInterpret}>
                    <label htmlFor={textId} className="panel__title assistant__request-label">
                        ¿Qué ruta quieres?
                    </label>
                    <textarea
                        id={textId}
                        ref={textRef}
                        className="field__input gomad-field gomad-field-assistant-request"
                        maxLength={500}
                        placeholder={`Por ejemplo: «${EXAMPLE}»`}
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                    />
                    <button type="submit" className="button button--primary gomad-action gomad-action-interpret-request" disabled={interpretation.status === "loading"}>
                        Interpretar
                    </button>
                </form>
                {interpretation.status === "loading" && <p className="muted">Interpretando…</p>}
                {interpretation.status === "clarification" && (
                    <p className="notice notice--info" role="note">
                        {interpretation.text}
                    </p>
                )}
                {interpretation.status === "rejection" && (
                    <p className="notice notice--warn" role="note">
                        {interpretation.text}
                    </p>
                )}
                {interpretation.status === "error" && (
                    <ErrorMessage message="Ahora no puedo interpretar el texto. Rellena los campos de abajo y pulsa «Calcular ruta»." />
                )}
            </section>

            <section className="panel assistant__understood" aria-labelledby="entendido">
                <h2 className="panel__title" id="entendido">
                    Lo que he entendido
                </h2>
                <form className="prefs-form" onSubmit={onCalculate} noValidate>
                    <fieldset className="prefs-form__group">
                        <legend className="field__label">Actividad</legend>
                        <div className="seg">
                            {(["walk", "run"] as const).map((a) => (
                                <label key={a} className={`seg__option gomad-option gomad-option-assistant-activity-${a}`}>
                                    <input
                                        type="radio"
                                        className={`gomad-field gomad-field-assistant-activity-${a}`}
                                        name="assistant-activity"
                                        checked={activity === a}
                                        onChange={() => setActivity(a)}
                                    />
                                    <span>{a === "walk" ? "Caminar" : "Correr"}</span>
                                </label>
                            ))}
                        </div>
                    </fieldset>

                                        <div className="assistant__measures">
                        <NumberStepper
                            id={`${textId}-km`}
                            label="Distancia (km)"
                            value={distance}
                            setValue={(value) => {
                                setDistance(value);
                                setAmountTouched(true);
                            }}
                            min={0.5}
                            max={42}
                            step={0.5}
                            inputMode="decimal"
                            className="gomad-field-assistant-distance"
                        />
                        <NumberStepper
                            id={`${textId}-min`}
                            label="Duración (min)"
                            value={duration}
                            setValue={(value) => {
                                setDuration(value);
                                setAmountTouched(true);
                            }}
                            min={5}
                            max={480}
                            step={5}
                            inputMode="numeric"
                            className="gomad-field-assistant-duration"
                        />
                    </div>

                    <fieldset className="prefs-form__group">
                        <legend className="field__label">Tipo de ruta</legend>
                        <div className="seg">
                            <label className="seg__option gomad-option gomad-option-route-circular">
                                <input type="radio" className="gomad-field gomad-field-route-circular" name="loop" checked={loop} onChange={() => setLoop(true)} />
                                <span>Ida y vuelta</span>
                            </label>
                            <label className="seg__option gomad-option gomad-option-route-one-way">
                                <input type="radio" className="gomad-field gomad-field-route-one-way" name="loop" checked={!loop} onChange={() => setLoop(false)} />
                                <span>Solo ida</span>
                            </label>
                        </div>
                    </fieldset>

                    <fieldset className="prefs-form__group">
                        <legend className="field__label">Pasar por</legend>
                        <div className="companion-options assistant__option-grid">
                            {PASS_BY.map((p) => (
                                <label key={p} className={`companion-option gomad-option gomad-option-pass-by-${p}`}>
                                    <input
                                        type="checkbox"
                                        className={`gomad-field gomad-field-pass-by-${p}`}
                                        checked={passBy.includes(p)}
                                        onChange={() => setPassBy(toggle(passBy, p))}
                                    />
                                    <span className="companion-option__label">
                                        <Icon name={PASS_BY_ICONS[p]} />
                                        {PASS_BY_LABELS[p]}
                                    </span>
                                </label>
                            ))}
                        </div>
                    </fieldset>

                    <fieldset className="prefs-form__group">
                        <legend className="field__label">Evitar</legend>
                        <div className="companion-options assistant__option-grid">
                            {AVOID.map((a) => (
                                <label key={a} className={`companion-option gomad-option gomad-option-avoid-${a}`}>
                                    <input
                                        type="checkbox"
                                        className={`gomad-field gomad-field-avoid-${a}`}
                                        checked={avoid.includes(a)}
                                        onChange={() => setAvoid(toggle(avoid, a))}
                                    />
                                    <span className="companion-option__label"><Icon name={AVOID_ICONS[a]} />{AVOID_LABELS[a]}</span>
                                </label>
                            ))}
                        </div>
                    </fieldset>

                    {formError && (
                        <p className="notice notice--bad" role="alert">
                            {formError}
                        </p>
                    )}

                    <button type="submit" className="button button--primary gomad-action gomad-action-calculate-route">
                        Calcular ruta
                    </button>
                </form>
            </section>

            {needLocation && !origin && (
                <>
                    <p className="notice notice--info">Antes, dinos dónde estás para calcular la ruta.</p>
                    <LocationPicker onPicked={() => setNeedLocation(false)} />
                </>
            )}

            <section className="panel assistant__proposal" aria-labelledby="propuesta">
                <h2 className="panel__title" id="propuesta">
                    La ruta propuesta
                </h2>
                {route.status === "idle" && (
                    <p className="muted">Cuando calcules la ruta, aquí verás qué condiciones cumple y cuáles no.</p>
                )}
                {route.status === "loading" && <p className="muted">Calculando la ruta…</p>}
                {route.status === "error" && (
                    <ErrorMessage
                        message={route.message ?? "No se pudo calcular la ruta."}
                        onRetry={() => lastParams.current && run(lastParams.current)}
                    />
                )}
                {done && (
                    <>
                        <p className="view-subtitle assistant__route-meta">
                            {formatDistance(done.route.distance_m)} · {formatMinutes(done.route.duration_min)}
                            {done.route.green_pct !== null && ` · ${Math.round(done.route.green_pct)} % por zona verde`}
                        </p>
                        <ul role="list" className="conditions" aria-label="Condiciones">
                            {done.conditions.map((c) => (
                                <li key={c.condition} className={`condition condition--${c.met ? "ok" : "ko"}`}>
                                    <span className="condition__body">
                                        <strong><Icon name={conditionIcon(c.condition)} />{c.condition}</strong>
                                        <span>{c.detail}</span>
                                    </span>
                                    <span className={`chip chip--${c.met ? "good" : "bad"}`}>
                                        {c.met ? "Cumple" : "No cumple"}
                                    </span>
                                </li>
                            ))}
                        </ul>
                        <RouteExplanation explanation={done.explanation} conditions={done.conditions} />
                        {!done.written_by_ai && <p className="muted">Explicación generada sin IA.</p>}
                        {origin && (
                            <MapView
                                className="map-view--block"
                                origin={origin.coordinate}
                                route={done.route.geometry}
                                markers={[]}
                            />
                        )}
                    </>
                )}
            </section>
        </section>
    );
}
