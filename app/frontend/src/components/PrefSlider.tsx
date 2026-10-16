import * as Slider from "@radix-ui/react-slider";
import { useRef, useState } from "react";

interface PrefSliderProps {
    label: string;
    min: number;
    max: number;
    step: number;
    value: number;
    // texto del valor en palabras (aria-valuetext y texto visible)
    format: (value: number) => string;
    controls?: boolean;
    // se llama al soltar (o con cada tecla): una sola peticion por cambio
    onCommit: (value: number) => void;
}

// Deslizador accesible (Radix Slider) que recalcula al soltar (RF-16)
export default function PrefSlider({ label, min, max, step, value, format, controls = false, onCommit }: PrefSliderProps) {
    // valor mientras se arrastra; null = el de las preferencias
    const [draft, setDraft] = useState<number | null>(null);
    const local = draft ?? value;
    // con teclado, Radix avisa del commit antes que del cambio: se ignora ese cambio
    const justCommitted = useRef<number | null>(null);
    const changeBy = (amount: number) => {
        justCommitted.current = null;
        setDraft(null);
        onCommit(Math.max(min, Math.min(max, local + amount)));
    };

    return (
        <div className={`pref-slider gomad-component gomad-pref-slider${controls ? " pref-slider--card" : ""}`}>
            <div className="pref-slider__head">
                <span className="field__label" aria-hidden="true">
                    {label}
                </span>
                <span className="pref-slider__value" aria-hidden="true">
                    {format(local)}
                </span>
            </div>
            <div className={controls ? "pref-slider__scale" : undefined}>
                {controls && (
                    <button
                        type="button"
                        className="pref-slider__step gomad-action gomad-action-decrease-filter"
                        aria-label={`Disminuir ${label.toLowerCase()}`}
                        disabled={local <= min}
                        onClick={() => changeBy(-step)}>
                        <span aria-hidden="true">−</span>
                    </button>
                )}
                <Slider.Root
                    className="slider"
                    min={min}
                    max={max}
                    step={step}
                    value={[local]}
                    onValueChange={([v]) => {
                        if (justCommitted.current === v) {
                            justCommitted.current = null;
                            return;
                        }
                        setDraft(v);
                    }}
                    onValueCommit={([v]) => {
                        justCommitted.current = v;
                        setDraft(null);
                        onCommit(v);
                    }}>
                    <Slider.Track className="slider__track">
                        <Slider.Range className="slider__range" />
                    </Slider.Track>
                    <Slider.Thumb className="slider__thumb gomad-field gomad-field-filter-slider" aria-label={label} aria-valuetext={format(local)} />
                </Slider.Root>
                {controls && (
                    <button
                        type="button"
                        className="pref-slider__step gomad-action gomad-action-increase-filter"
                        aria-label={`Aumentar ${label.toLowerCase()}`}
                        disabled={local >= max}
                        onClick={() => changeBy(step)}>
                        <span aria-hidden="true">+</span>
                    </button>
                )}
            </div>
            {controls && (
                <div className="pref-slider__limits" aria-hidden="true">
                    <span>{format(min)}</span>
                    <span>{format(max)}</span>
                </div>
            )}
        </div>
    );
}
