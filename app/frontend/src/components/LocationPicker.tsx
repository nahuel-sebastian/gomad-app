import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import type { LocationCandidate } from "../api/types";
import { currentLocation, searchLocation } from "../data/location";
import { useAppState } from "../state/context";
import Icon from "./Icon";

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
    const inputRef = useRef<HTMLInputElement>(null);
    const searchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const [locating, setLocating] = useState(false);
    const [locateError, setLocateError] = useState("");

    const cancelScheduledSearch = () => {
        if (searchTimerRef.current !== null) clearTimeout(searchTimerRef.current);
        searchTimerRef.current = null;
    };

    const runSearch = async (query: string, call: number) => {
        setPicked("");
        setLocateError("");
        setSearch({ status: "loading" });
        try {
            const data = await searchLocation(query);
            if (call === statusRef.current) setSearch({ status: "done", candidates: data.candidates });
        } catch {
            if (call === statusRef.current) setSearch({ status: "error" });
        }
    };

    useEffect(() => {
        const query = text.trim();
        if (origin || query.length < 3) return;
        const call = ++statusRef.current;
        searchTimerRef.current = setTimeout(() => {
            searchTimerRef.current = null;
            void runSearch(query, call);
        }, 300);
        return cancelScheduledSearch;
    }, [text, origin]);

    const pick = (candidate: LocationCandidate) => {
        cancelScheduledSearch();
        statusRef.current += 1;
        setOrigin(candidate);
        setSearch({ status: "idle" });
        setText("");
        setPicked(`Ubicación elegida: ${candidate.label}.`);
        requestAnimationFrame(() => inputRef.current?.focus());
        onPicked?.(candidate);
    };

    const clear = () => {
        cancelScheduledSearch();
        statusRef.current += 1;
        setOrigin(null);
        setText("");
        setSearch({ status: "idle" });
        setPicked("");
        setLocateError("");
        inputRef.current?.focus();
    };

    // GPS tras el gesto; la posicion solo se usa para esta busqueda (no se guarda)
    const locate = async () => {
        cancelScheduledSearch();
        const call = ++statusRef.current;
        setSearch({ status: "idle" });
        setLocating(true);
        setLocateError("");
        setPicked("");
        try {
            const candidate = await currentLocation();
            if (call === statusRef.current) pick(candidate);
        } catch (error) {
            if (call === statusRef.current) {
                setLocateError(error instanceof Error ? error.message : "No hemos podido saber dónde estás.");
            }
        } finally {
            setLocating(false);
        }
    };

    const onSubmit = (event: FormEvent) => {
        event.preventDefault();
        cancelScheduledSearch();
        const query = text.trim();
        if (query.length < 3) {
            statusRef.current += 1;
            setSearch({ status: "done", candidates: [] });
            return;
        }
        const call = ++statusRef.current;
        void runSearch(query, call);
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
            className={`location gomad-component gomad-location-picker${highlight ? " location--highlight" : ""}`}
            aria-labelledby="ubicacion-titulo"
            id="ubicacion">
            <h2 className="panel__title" id="ubicacion-titulo">
                ¿Desde dónde sales?
            </h2>

            <form className="location__form" onSubmit={onSubmit} role="search" aria-label="Buscar ubicación">
                <label htmlFor={inputId} className="sr-only">
                    Escribe una dirección o un municipio
                </label>
                <div className="location__search-wrap">
                    <div className="location__search">
                        <input
                            ref={inputRef}
                            id={inputId}
                            className="field__input gomad-field gomad-field-location-search"
                            type="text"
                            autoComplete="off"
                            maxLength={200}
                            placeholder="Escribe una dirección o un municipio"
                            value={origin?.label ?? text}
                            readOnly={Boolean(origin)}
                            onChange={(e) => {
                                statusRef.current += 1;
                                setText(e.target.value);
                                setSearch({ status: "idle" });
                            }}
                        />
                        <button
                            type={origin ? "button" : "submit"}
                            className="button location__search-button gomad-action gomad-action-search-location"
                            aria-label={origin ? "Borrar ubicación" : "Buscar"}
                            onClick={origin ? clear : undefined}>
                            <Icon name={origin ? "close" : "search"} />
                            <span aria-hidden="true">{origin ? "Borrar ubicación" : "Buscar"}</span>
                        </button>
                    </div>
                </div>
                <div className="location__actions">
                    <button
                        type="button"
                        className="button button--primary gomad-action gomad-action-use-location"
                        aria-label={locating ? "Buscando tu ubicación…" : "Usar mi ubicación"}
                        onClick={locate}
                        disabled={locating}>
                        <Icon name="location_on" />
                        <span>{locating ? "Buscando…" : "Usar ubicación"}</span>
                    </button>
                </div>
                {announcement && (
                    <p className={`location__status${picked ? " sr-only" : ""}`} role="status" aria-live="polite">
                        {announcement}
                    </p>
                )}
                {search.status === "done" && search.candidates.length > 0 && (
                    <ul role="list" className="location__candidates" aria-label="Lugares encontrados">
                        {search.candidates.map((c) => (
                            <li key={`${c.ine_code}-${c.label}`}>
                                <button type="button" className="candidate gomad-action gomad-action-select-location" onClick={() => pick(c)}>
                                    {c.label}
                                </button>
                            </li>
                        ))}
                    </ul>
                )}
            </form>
        </section>
    );
}
