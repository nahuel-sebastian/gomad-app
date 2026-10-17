"""GET /map/points (correccion C2): destinos y puntos utiles de la caja visible del mapa.

La caja es la de la vista del mapa, no la ubicacion de la persona; aun asi no se escribe en los logs."""
import math
from typing import get_args

import schemas as s


class InvalidBbox(ValueError):
    pass


def validate_map_config(cfg):
    """Para el arranque si config/map.yaml falta o tiene valores no validos."""
    if not isinstance(cfg, dict):
        raise ValueError("config/map.yaml: falta o no es un diccionario")
    span, limit, pool = cfg.get("max_span_deg"), cfg.get("max_points"), cfg.get("pool_activity")
    if not isinstance(span, (int, float)) or isinstance(span, bool) or not 0 < span <= 5:
        raise ValueError("config/map.yaml: max_span_deg debe ser un numero entre 0 y 5")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0:
        raise ValueError("config/map.yaml: max_points debe ser un entero positivo")
    if not isinstance(pool, str) or not pool:
        raise ValueError("config/map.yaml: pool_activity debe ser un id de actividad")


def parse_bbox(text):
    """'oeste,sur,este,norte' en grados (EPSG:4326) -> tupla; InvalidBbox si no es una caja valida."""
    parts = (text or "").split(",")
    if len(parts) != 4:
        raise InvalidBbox("La zona del mapa no es válida: hacen falta cuatro números (oeste, sur, este, norte).")
    try:
        w, s, e, n = (float(p) for p in parts)
    except ValueError:
        raise InvalidBbox("La zona del mapa no es válida: hay un valor que no es un número.") from None
    if not all(math.isfinite(v) for v in (w, s, e, n)):
        raise InvalidBbox("La zona del mapa no es válida: hay un valor que no es un número.")
    if not (-180 <= w < e <= 180 and -90 <= s < n <= 90):
        raise InvalidBbox("La zona del mapa no es válida: el oeste debe ser menor que el este y el sur que el norte.")
    return w, s, e, n


def clip_bbox(bbox, max_span):
    """Recorta cada lado a max_span grados alrededor del centro; devuelve (caja, si se recorto)."""
    w, s, e, n = bbox
    clipped = False
    if e - w > max_span:
        cx = (w + e) / 2
        w, e, clipped = cx - max_span / 2, cx + max_span / 2, True
    if n - s > max_span:
        cy = (s + n) / 2
        s, n, clipped = cy - max_span / 2, cy + max_span / 2, True
    return (w, s, e, n), clipped


def map_points(bbox_text, kinds, repo, cfg):
    """MapPointsResponse de la caja (recortada a max_span_deg) con como mucho max_points puntos de esos tipos."""
    box, clipped = clip_bbox(parse_bbox(bbox_text), cfg["max_span_deg"])
    wanted = set(kinds)
    destination_kinds = [k for k in get_args(s.MapDestinationKind) if k in wanted]
    poi_kinds = [k for k in get_args(s.MapPoiKind) if k in wanted]
    limit = cfg["max_points"]
    rows = repo.map_points(box, destination_kinds, poi_kinds, limit + 1, cfg["pool_activity"])
    points = [s.MapPoint(id=i, kind=kind, name=name, source=source, working=working,
                         coordinate=s.Coordinate(lat=lat, lon=lon))
              for i, kind, name, source, working, lon, lat in rows[:limit]]
    return s.MapPointsResponse(points=points, truncated=len(rows) > limit, clipped=clipped)
