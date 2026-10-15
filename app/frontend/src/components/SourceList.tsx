import type { DataSource } from "../api/types";
import { formatSourceDate } from "../lib/format";

// Fuente y fecha de cada dato (RF-19); «criterio propio» si own_criterion
export default function SourceList({ sources, label }: { sources: DataSource[]; label: string }) {
    return (
        <ul className="source-list" aria-label={label}>
            {sources.map((s) => (
                <li key={`${s.source}-${s.label}`}>
                    {s.label} · {s.date ? formatSourceDate(s.date) : "sin fecha"}
                    {s.own_criterion && <span className="source-list__own"> · criterio propio</span>}
                </li>
            ))}
        </ul>
    );
}
