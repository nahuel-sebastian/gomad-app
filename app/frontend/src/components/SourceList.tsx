import type { DataSource } from "../api/types";
import { formatSourceDate } from "../lib/format";

function capitalize(text: string): string {
    return text.charAt(0).toLocaleUpperCase("es-ES") + text.slice(1);
}

// Fuente y fecha de cada dato (RF-19); «criterio propio» si own_criterion
export default function SourceList({ sources, label }: { sources: DataSource[]; label: string }) {
    return (
        <ul role="list" className="source-list gomad-component gomad-source-list" aria-label={label}>
            {sources.map((s) => {
                const [name, ...details] = s.label.split(/\s*·\s*/).map((part) => part.trim()).filter(Boolean);
                const data = [...details.map(capitalize), s.date ? formatSourceDate(s.date) : "Sin fecha"];
                return (
                    <li key={`${s.source}-${s.label}`}>
                        <strong className="source-list__label">{capitalize(name)}:</strong> {data.join(", ")}
                        {s.own_criterion && <span className="source-list__own">, Criterio propio</span>}
                    </li>
                );
            })}
        </ul>
    );
}
