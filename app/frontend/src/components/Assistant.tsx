import { useId, useRef, useState, type FormEvent } from "react";
import type { AssistantParams, AssistantRouteResponse, Avoid, PassBy } from "../api/types";
import { assistantRoute, interpret } from "../data/assistant";
import { ApiError } from "../data/errors";
import { formatDistance, formatMinutes } from "../lib/format";
import { AVOID_LABELS, PASS_BY_LABELS } from "../lib/labels";
import { useAppState } from "../state/context";
import ErrorMessage from "./ErrorMessage";
import Icon from "./Icon";
import LocationPicker from "./LocationPicker";
import MapView from "./MapView";
import PageHeading from "./PageHeading";

const PASS_BY: PassBy[] = ["park", "fountain", "bench", "supermarket", "dog_area", "playground"];
const AVOID: Avoid[] = ["traffic", "hills"];
const EXAMPLE = "15 km andando, por un parque, con fuentes y bancos y que pase por un supermercado";

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

            <section className="panel" aria-labelledby="peticion">
                <h2 className="panel__title" id="peticion">
                    Tu petición
                </h2>
                <form className="assistant__form" onSubmit={onInterpret}>
                    <label htmlFor={textId} className="field__label">
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

            <section className="panel" aria-labelledby="entendido">
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
                        <div>
                            <label className="field__label" htmlFor={`${textId}-km`}>
                                Distancia (km)
                            </label>
                            <input
                                id={`${textId}-km`}
                                className="field__input gomad-field gomad-field-assistant-distance"
                                type="number"
                                inputMode="decimal"
                                min={0.5}
                                max={42}
                                step={0.5}
                                value={distance}
                                onChange={(e) => {
                                    setDistance(e.target.value);
                                    setAmountTouched(true);
                                }}
                            />
                        </div>
                        <div>
                            <label className="field__label" htmlFor={`${textId}-min`}>
                                o duración (min)
                            </label>
                            <input
                                id={`${textId}-min`}
                                className="field__input gomad-field gomad-field-assistant-duration"
                                type="number"
                                inputMode="numeric"
                                min={5}
                                max={480}
                                step={5}
                                value={duration}
                                onChange={(e) => {
                                    setDuration(e.target.value);
                                    setAmountTouched(true);
                                }}
                            />
                        </div>
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
                        <div className="option-grid">
                            {PASS_BY.map((p) => (
                                <label key={p} className={`option gomad-option gomad-option-pass-by-${p}`}>
                                    <input
                                        type="checkbox"
                                        className={`gomad-field gomad-field-pass-by-${p}`}
                                        checked={passBy.includes(p)}
                                        onChange={() => setPassBy(toggle(passBy, p))}
                                    />
                                    <span className="option__label">
                                        {p === "supermarket" && <Icon name="shopping_cart" />}
                                        {PASS_BY_LABELS[p]}
                                    </span>
                                </label>
                            ))}
                        </div>
                    </fieldset>

                    <fieldset className="prefs-form__group">
                        <legend className="field__label">Evitar</legend>
                        <div className="option-grid">
                            {AVOID.map((a) => (
                                <label key={a} className={`option gomad-option gomad-option-avoid-${a}`}>
                                    <input
                                        type="checkbox"
                                        className={`gomad-field gomad-field-avoid-${a}`}
                                        checked={avoid.includes(a)}
                                        onChange={() => setAvoid(toggle(avoid, a))}
                                    />
                                    <span>{AVOID_LABELS[a]}</span>
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

            <section className="panel" aria-labelledby="propuesta">
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
                        <p>
                            <strong>
                                {formatDistance(done.route.distance_m)} · {formatMinutes(done.route.duration_min)}
                                {done.route.green_pct !== null && ` · ${Math.round(done.route.green_pct)} % por zona verde`}
                            </strong>
                        </p>
                        <ul role="list" className="conditions" aria-label="Condiciones">
                            {done.conditions.map((c) => (
                                <li key={c.condition} className={`condition condition--${c.met ? "ok" : "ko"}`}>
                                    <span className={`chip chip--${c.met ? "good" : "bad"}`}>
                                        {c.met ? "Cumple" : "No cumple"}
                                    </span>
                                    <span>
                                        <strong>{c.condition}</strong> {c.detail}
                                    </span>
                                </li>
                            ))}
                        </ul>
                        <p>{done.explanation}</p>
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
