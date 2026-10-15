interface IconProps {
    // nombre de Material Symbols (p. ej. "directions_run")
    name: string;
}

// Hueco para los iconos (aplazados): hoy no pinta nada visible.
// Cuando llegue la fuente propia, basta con poner {name} como texto (ligadura)
// y la clase de icons.css; las pantallas no cambian.
export default function Icon({ name }: IconProps) {
    return <span className="icon" aria-hidden="true" data-icon={name} />;
}
