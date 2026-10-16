"""GET /sources: editor, licencia, URL y fechas de cada fuente que usa la app (RF-19, B1 Task 38)."""
import json
import logging

import schemas as s
import settings
from repository import DataUnavailable, parse_date

log = logging.getLogger("gomad.api")

# referencias de umbrales: no salen en DataSource, pero la app las cita (ICA del BOE y calor de Sanidad)
THRESHOLD_REFERENCES = ("boe_ica", "sanidad_calor")


def used_ids(sources_cfg, indicators_cfg):
    """Fuentes usadas: las etiquetadas, las de los indicadores y las de umbrales."""
    ids = set(sources_cfg.get("labels", {})) | set(THRESHOLD_REFERENCES)
    for item in indicators_cfg.get("indicators", []):
        ids |= set(item.get("source") or [])
    return ids


def manifest_dates(data_dir):
    """{id: (ultima recarga, ultimo fallo)} de raw/manifest.json; sin fichero o roto -> {}."""
    path = data_dir / "raw" / "manifest.json"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log.warning("manifest.json ilegible: %s", e)
        return {}
    out = {}
    for sid, entry in manifest.items():
        if not isinstance(entry, dict):
            continue
        failure = entry.get("last_failure")
        failure = parse_date(failure.get("date")) if isinstance(failure, dict) else None
        out[sid] = (parse_date(entry.get("checked") or entry.get("downloaded")), failure)
    return out


def sources(repo, data_dir):
    cfg = settings.load("sources") or {}
    labels = cfg.get("labels", {})
    from_manifest = manifest_dates(data_dir)
    try:
        from_db = repo.source_dates()
    except DataUnavailable:
        from_db = {}
    live_feed = getattr(repo.live, "forecast", None) if repo.live is not None else None
    if live_feed is not None:                                   # prevision en vivo: su ultima descarga, no la ingesta
        from_manifest["open_meteo"] = (live_feed.fetched_at, from_manifest.get("open_meteo", (None, None))[1])
        from_db.pop("open_meteo", None)
    items = []
    for sid, entry in (cfg.get("catalog") or {}).items():
        refresh, failure = from_manifest.get(sid, (None, None))
        items.append(s.SourceInfo(id=sid, name=labels.get(sid, sid), publisher=entry["publisher"],
                                  license=entry["license"], url=entry["url"],
                                  last_refresh=refresh or from_db.get(sid), last_failure=failure))
    return s.SourcesResponse(sources=items)
