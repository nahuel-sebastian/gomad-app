import type { MapPoint, MapPointKind } from "../api/types";
import MapDialog from "./MapDialog";
import { KIND_ORDER, KIND_STYLES, OUT_OF_SERVICE_COLOR, POI_KINDS } from "./mapIcons";
import { NEARBY_MIN_ZOOM, POI_MIN_ZOOM } from "./mapUtils";

interface MapLegendProps {
    // tipo de cada pin numerado (uno por resultado)
    markerKinds: MapPointKind[];
    // puntos que se ven en el mapa (los que cuenta la leyenda)
    points: MapPoint[];
    // todos los puntos cargados de la zona (aunque no se vean): deciden «sin datos»; por defecto, points
    loadedPoints?: MapPoint[];
    // zoom del mapa; null = todavia no se sabe (o el mapa no es explorable)
    zoom: number | null;
    truncated: boolean;
    live?: boolean;
    // tipos de punto util que comprobo la ultima respuesta aplicada (completa); solo de esos se dice
    // «sin datos»: mientras llega otra o si fallo, no se afirma nada
    checkedPoiKinds?: MapPointKind[];
}

function KindIcon({ color, path }: { color: string; path: string }) {
    return (
        <span className="map-legend__icon" style={{ background: color }}>
            <svg viewBox="0 0 960 960" aria-hidden="true" focusable="false">
                <path d={path} />
            </svg>
        </span>
    );
}

// Leyenda del mapa (C2): cada tipo con icono + color + texto y cuantos hay a la vista (nunca
// solo color, CLAUDE.md §2.10), y una pista de zoom. Un boton de icono la abre en una ventana
// (MapDialog), asi no tapa el mapa.
export default function MapLegend({
    markerKinds,
    points,
    loadedPoints = points,
    zoom,
    truncated,
    live = false,
    checkedPoiKinds = [],
}: MapLegendProps) {
    const counts = new Map<MapPointKind, number>();
    for (const kind of [...markerKinds, ...points.map((p) => p.kind)]) counts.set(kind, (counts.get(kind) ?? 0) + 1);
    // fuera de servicio por tipo (hoy solo fuentes; el mobiliario de OSM puede traer mas)
    const outOfService = new Map<MapPointKind, number>();
    for (const p of points) if (p.working === false) outOfService.set(p.kind, (outOfService.get(p.kind) ?? 0) + 1);
    const kinds = KIND_ORDER.filter((k) => counts.has(k));

    // el mobiliario solo esta donde la fuente tiene datos (CLAUDE.md §7.4: aviso de cobertura)
    const hints: string[] = [];
    if (zoom !== null && zoom < NEARBY_MIN_ZOOM) hints.push("Acerca el mapa para ver más lugares de la zona.");
    else if (zoom !== null && zoom < POI_MIN_ZOOM)
        hints.push("Acerca más para ver fuentes, bancos, papeleras, juegos, desfibriladores y áreas caninas (solo donde hay datos).");
    else if (zoom !== null) {
        hints.push("Fuentes, bancos, papeleras, juegos, desfibriladores y áreas caninas: solo donde hay datos.");
        const loaded = new Set(loadedPoints.map((p) => p.kind));
        const missing = POI_KINDS.filter((k) => checkedPoiKinds.includes(k) && !loaded.has(k)).map(
            (k) => KIND_STYLES[k].label,
        );
        if (!truncated && missing.length > 0) hints.push(`Sin datos en esta zona: ${missing.join(", ")}.`);
    }
    if (truncated) hints.push("Hay más lugares de los que se ven: acerca el mapa.");

    if (kinds.length === 0 && !live && hints.length === 0) return null;

    return (
        <MapDialog
            label="Leyenda del mapa"
            title="Leyenda del mapa"
            action="gomad-action-open-map-legend"
            className="map-legend gomad-map-legend"
            icon={
                // icono de leyenda: un punto de color por tipo y una raya de texto
                <span className="map-legend-button__glyph" aria-hidden="true">
                    {KIND_ORDER.slice(0, 3).map((k) => (
                        <span key={k} style={{ background: KIND_STYLES[k].color }} />
                    ))}
                </span>
            }>
            <>
                <ul role="list" aria-label="Tipos de lugar en el mapa">
                    {kinds.map((kind) => (
                        <li key={kind}>
                            <KindIcon color={KIND_STYLES[kind].color} path={KIND_STYLES[kind].path} />
                            {`${KIND_STYLES[kind].label}: ${counts.get(kind)}`}
                        </li>
                    ))}
                    {KIND_ORDER.filter((k) => outOfService.has(k)).map((kind) => (
                        <li key={`off-${kind}`}>
                            <KindIcon color={OUT_OF_SERVICE_COLOR} path={KIND_STYLES[kind].path} />
                            {`${KIND_STYLES[kind].label} fuera de servicio: ${outOfService.get(kind)}`}
                        </li>
                    ))}
                    {live && (
                        <li>
                            <span className="map-legend__icon map-legend__icon--live" aria-hidden="true" />
                            Estás aquí (en tiempo real)
                        </li>
                    )}
                </ul>
                {hints.map((hint) => (
                    <p key={hint} className="map-legend__hint">
                        {hint}
                    </p>
                ))}
            </>
        </MapDialog>
    );
}
