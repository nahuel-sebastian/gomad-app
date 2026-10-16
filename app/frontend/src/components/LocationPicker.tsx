import { useId, useRef, useState, type FormEvent } from "react";
import type { LocationCandidate } from "../api/types";
import { currentLocation, isSampleLocation, searchLocation } from "../data/location";
import { useAppState } from "../state/context";

type SearchState =
    | { status: "idle" }
    | { status: "loading" }
    | { status: "done"; candidates: LocationCandidate[] }
    | { status: "error" };

interface LocationPickerProps {
    // se llama al elegir una ubicacion (p. ej. para seguir a resultados)
    onPicked?: (origin: LocationCandidate) => void;
    highlight?: boolean;
}

export default function LocationPicker({ onPicked, highlight }: LocationPickerProps) {
    const { origin, setOrigin } = useAppState();
    const [text, setText] = useState("");
    const [search, setSearch] = useState<SearchState>({ status: "idle" });
    const inputId = useId();
    const statusRef = useRef(0);
    const [picked, setPicked] = useState("");
    const currentRef = useRef<HTMLParagraphElement>(null);
    const [locating, setLocating] = useState(false);
    const [locateError, setLocateError] = useState("");

    const pick = (candidate: LocationCandidate) => {
        setOrigin(candidate);
        setSearch({ status: "idle" });
        setText("");
        setPicked(`Ubicación elegida: ${candidate.label}.`);
        // el candidato pulsado desaparece: el foco va a la ubicacion elegida
        requestAnimationFrame(() => currentRef.current?.focus());
        onPicked?.(candidate);
    };

    // GPS tras el gesto; la posicion solo se usa para esta busqueda (no se guarda)
    const locate = async () => {
        setLocating(true);
        setLocateError("");
        setPicked("");
        try {
            pick(await currentLocation());
        } catch (error) {
            setLocateError(error instanceof Error ? error.message : "No hemos podido saber dónde estás.");
        } finally {
            setLocating(false);
        }
    };

    const onSubmit = async (event: FormEvent) => {
        event.preventDefault();
        if (text.trim().length < 3) {
            setSearch({ status: "done", candidates: [] });
            return;
        }
        const call = ++statusRef.current;
        setPicked("");
        setLocateError("");
        setSearch({ status: "loading" });
        try {
            const data = await searchLocation(text.trim());
            if (call === statusRef.current) {
                setSearch({ status: "done", candidates: data.candidates });
            }
        } catch {
            if (call === statusRef.current) setSearch({ status: "error" });
        }
    };

    let announcement = picked;
    if (locating) announcement = "Buscando tu ubicación…";
    if (locateError) announcement = locateError;
    if (search.status === "loading") announcement = "Buscando…";
    if (search.status === "error") announcement = "No se pudo buscar ahora. Inténtalo de nuevo.";
    if (search.status === "done") {
        const n = search.candidates.length;
        announcement =
            n === 0
                ? text.trim().length < 3
                    ? "Escribe al menos 3 caracteres."
                    : "No encontramos esa dirección. Prueba con el nombre del municipio."
                : `${n} ${n === 1 ? "lugar encontrado" : "lugares encontrados"}.`;
    }

    return (
        <section
            className={`panel location${highlight ? " location--highlight" : ""}`}
            aria-labelledby="ubicacion-titulo"
            id="ubicacion">
            <h2 className="panel__title" id="ubicacion-titulo">
                ¿Desde dónde sales?
            </h2>

            {origin && (
                <p className="location__current" ref={currentRef} tabIndex={-1}>
                    <span className="muted">Ubicación elegida:</span>{" "}
                    <strong>{origin.label}</strong>
                    {origin.precision === "municipality" && (
                        <span className="location__note">
                            Usaremos el centro de {origin.municipality}.
                        </span>
                    )}
                    {isSampleLocation(origin) && (
                        <span className="location__note">
                            Es una ubicación de ejemplo: el GPS no está disponible en este entorno de desarrollo.
                        </span>
                    )}
                </p>
            )}

            <button type="button" className="button button--primary" onClick={locate} disabled={locating}>
                {locating ? "Buscando tu ubicación…" : "Usar mi ubicación"}
            </button>

            <form className="location__form" onSubmit={onSubmit} role="search" aria-label="Buscar ubicación">
                <label htmlFor={inputId} className="field__label">
                    Escribe una dirección o un municipio
                </label>
                <div className="location__row">
                    <input
                        id={inputId}
                        className="field__input"
                        type="text"
                        autoComplete="off"
                        maxLength={200}
                        value={text}
                        onChange={(e) => setText(e.target.value)}
                    />
                    <button type="submit" className="button">
                        Buscar
                    </button>
                </div>
            </form>

            <p className="location__status" role="status" aria-live="polite">
                {announcement}
            </p>

            {search.status === "done" && search.candidates.length > 0 && (
                <ul role="list" className="location__candidates" aria-label="Lugares encontrados">
                    {search.candidates.map((c) => (
                        <li key={`${c.ine_code}-${c.label}`}>
                            <button type="button" className="candidate" onClick={() => pick(c)}>
                                {c.label}
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </section>
    );
}
