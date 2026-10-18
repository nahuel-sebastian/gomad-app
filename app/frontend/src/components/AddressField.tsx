import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import type { LocationCandidate } from "../api/types";
import { currentLocation, searchLocation } from "../data/location";
import Icon from "./Icon";

// Campo de direccion controlado por props (ruta entre dos direcciones). No toca el estado
// global: la direccion elegida solo la conoce quien lo usa. Busqueda como LocationPicker.

type SearchState =
    | { status: "idle" }
    | { status: "loading" }
    | { status: "done"; candidates: LocationCandidate[] }
    | { status: "error" };

interface AddressFieldProps {
    label: string;
    value: LocationCandidate | null;
    onChange: (candidate: LocationCandidate | null) => void;
    // ofrece «Usar mi ubicacion» (solo en el campo de inicio)
    allowCurrentLocation?: boolean;
}

export default function AddressField({ label, value, onChange, allowCurrentLocation = false }: AddressFieldProps) {
    const [text, setText] = useState("");
    const [search, setSearch] = useState<SearchState>({ status: "idle" });
    const [locating, setLocating] = useState(false);
    const [locateError, setLocateError] = useState("");
    const inputId = useId();
    const callRef = useRef(0);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const changeRef = useRef<HTMLButtonElement>(null);

    const cancelScheduledSearch = () => {
        if (timerRef.current !== null) clearTimeout(timerRef.current);
        timerRef.current = null;
    };

    const runSearch = async (query: string, call: number) => {
        setLocateError("");
        setSearch({ status: "loading" });
        try {
            const data = await searchLocation(query);
            if (call === callRef.current) setSearch({ status: "done", candidates: data.candidates });
        } catch {
            if (call === callRef.current) setSearch({ status: "error" });
        }
    };

    // busqueda con espera mientras se escribe (3+ caracteres)
    useEffect(() => {
        const query = text.trim();
        if (value || query.length < 3) return;
        const call = ++callRef.current;
        timerRef.current = setTimeout(() => {
            timerRef.current = null;
            void runSearch(query, call);
        }, 300);
        return cancelScheduledSearch;
    }, [text, value]);

    const pick = (candidate: LocationCandidate) => {
        cancelScheduledSearch();
        callRef.current += 1;
        setSearch({ status: "idle" });
        setText("");
        setLocateError("");
        onChange(candidate);
        requestAnimationFrame(() => changeRef.current?.focus());
    };

    const clear = () => {
        cancelScheduledSearch();
        callRef.current += 1;
        setSearch({ status: "idle" });
        setText("");
        onChange(null);
        requestAnimationFrame(() => inputRef.current?.focus());
    };

    // GPS tras el gesto; la posicion solo se usa para esta ruta (no se guarda)
    const locate = async () => {
        cancelScheduledSearch();
        const call = ++callRef.current;
        setSearch({ status: "idle" });
        setLocating(true);
        setLocateError("");
        try {
            const candidate = await currentLocation();
            if (call === callRef.current) pick(candidate);
        } catch (error) {
            if (call === callRef.current) {
                setLocateError(error instanceof Error ? error.message : "No hemos podido saber dónde estás.");
            }
        } finally {
            setLocating(false);
        }
    };

    // Intro busca sin esperar
    const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        cancelScheduledSearch();
        const query = text.trim();
        if (query.length < 3) {
            callRef.current += 1;
            setSearch({ status: "done", candidates: [] });
            return;
        }
        void runSearch(query, ++callRef.current);
    };

    if (value) {
        return (
            <div className="address-field gomad-component gomad-address-field">
                <div className="location__search">
                    <p className="address-field__value">
                        <span className="field__label">{label}</span> <strong>{value.label}</strong>
                    </p>
                    <button ref={changeRef} type="button" className="button gomad-action gomad-action-change-address" onClick={clear}>
                        <Icon name="close" />
                        <span>Cambiar<span className="sr-only"> {label.toLowerCase()}</span></span>
                    </button>
                </div>
            </div>
        );
    }

    let announcement = "";
    if (locating) announcement = "Buscando tu ubicación…";
    if (locateError) announcement = locateError;
    if (search.status === "loading") announcement = "Buscando…";
    if (search.status === "error") announcement = "No se pudo buscar la dirección.";
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
        <div className="address-field gomad-component gomad-address-field">
            <label htmlFor={inputId} className="field__label">
                {label}
            </label>
            <input
                ref={inputRef}
                id={inputId}
                className="field__input gomad-field gomad-field-address"
                type="text"
                autoComplete="off"
                maxLength={200}
                placeholder="Escribe una dirección o un municipio"
                value={text}
                onKeyDown={onKeyDown}
                onChange={(e) => {
                    callRef.current += 1;
                    setText(e.target.value);
                    setSearch({ status: "idle" });
                }}
            />
            {allowCurrentLocation && (
                <div className="location__actions">
                    <button
                        type="button"
                        className="button gomad-action gomad-action-use-location"
                        onClick={locate}
                        disabled={locating}>
                        <Icon name="location_on" />
                        <span>{locating ? "Buscando…" : "Usar mi ubicación"}</span>
                    </button>
                </div>
            )}
            {announcement && (
                <p className="location__status" role="status" aria-live="polite">
                    {announcement}
                </p>
            )}
            {search.status === "done" && search.candidates.length > 0 && (
                <ul role="list" className="location__candidates" aria-label={`Lugares encontrados para «${label}»`}>
                    {search.candidates.map((c) => (
                        <li key={`${c.ine_code}-${c.label}`}>
                            <button type="button" className="candidate gomad-action gomad-action-select-address" onClick={() => pick(c)}>
                                {c.label}
                            </button>
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
}
