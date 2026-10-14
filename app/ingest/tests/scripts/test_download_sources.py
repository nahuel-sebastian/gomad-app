"""Pruebas del descargador. No tocan la red: se sustituye fetch."""
import argparse
import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]      # app/ingest


@pytest.fixture
def dl(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("download_sources", ROOT / "scripts" / "download_sources.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path / "raw")
    monkeypatch.setattr(mod, "APP_DIR", tmp_path)
    return mod


def args(**kw):
    base = dict(list=False, group="minimal", only=None, include_heavy=False, refresh=None, force=False,
                aemet_municipalities=None)
    base.update(kw)
    return argparse.Namespace(**base)


def test_every_source_has_level(dl):
    for key, src in dl.SOURCES.items():
        assert src.refresh in dl.REFRESH_LEVELS, key


def test_select_hourly_level(dl):
    assert set(dl.select(args(refresh="hourly"))) == {"aire_dia", "ay_aire", "ay_meteo", "aemet"}


def test_select_level_excludes_heavy_unless_flag(dl):
    assert "osm" not in dl.select(args(refresh="weekly"))
    assert dl.select(args(refresh="weekly", include_heavy=True)) == ["osm"]


def test_osm_and_street_directory_registered(dl):
    assert dl.SOURCES["osm"].ident == "https://download.geofabrik.de/europe/spain/madrid-latest.osm.pbf"
    assert dl.SOURCES["callejero"].ident == "callejero_completo_2025"
    assert dl.SOURCES["callejero"].kind == "nmc"


def test_unchanged_ckan_is_not_downloaded(dl, monkeypatch):
    calls = []
    monkeypatch.setattr(dl, "ckan_modified", lambda base, ident: "2026-10-01T10:00:00")
    monkeypatch.setattr(dl, "fetch", lambda *a, **k: calls.append(a) or b"x")
    previous = {"modified": "2026-10-01T10:00:00", "sha256": "abc", "files": []}
    entry = dl.download_source("padron", dl.SOURCES["padron"], previous, force=False)
    assert entry["changed"] is False
    assert calls == []


def test_force_skips_change_check(dl, monkeypatch):
    monkeypatch.setattr(dl, "ckan_modified", lambda base, ident: "2026-10-01T10:00:00")
    monkeypatch.setattr(dl, "download_ckan", lambda base, ident, folder, heavy: (
        [dl.save(folder, "a.csv", b"1;2")], ["https://x/a.csv"], "2026-10-01T10:00:00"))
    previous = {"modified": "2026-10-01T10:00:00", "sha256": "abc", "files": []}
    entry = dl.download_source("padron", dl.SOURCES["padron"], previous, force=True)
    assert entry["changed"] is True


def test_same_content_is_not_a_change(dl, monkeypatch):
    monkeypatch.setattr(dl, "fetch_conditional", lambda url, previous, timeout=300: (b"<xml/>", {}))
    e1 = dl.download_source("ay_trafico", dl.SOURCES["ay_trafico"], {}, force=False)
    e2 = dl.download_source("ay_trafico", dl.SOURCES["ay_trafico"], e1, force=False)
    assert e1["changed"] is True and e2["changed"] is False
    assert e1["files"] == ["ay_trafico/pm.xml"]                  # relativas a RAW_DIR


def test_304_is_not_downloaded(dl, monkeypatch):
    monkeypatch.setattr(dl, "fetch_conditional", lambda url, previous, timeout=300: (None, {}))
    previous = {"etag": '"v1"', "sha256": "abc", "files": ["osm/madrid-latest.osm.pbf"]}
    entry = dl.download_source("osm", dl.SOURCES["osm"], previous, force=False)
    assert entry["changed"] is False and entry["etag"] == '"v1"'


def test_failure_keeps_manifest(dl, monkeypatch):
    dl.RAW_DIR.mkdir(parents=True)
    (dl.RAW_DIR / "manifest.json").write_text(json.dumps({"aire_dia": {"sha256": "old"}}), encoding="utf-8")

    def broken(*a, **k):
        raise OSError("portal caído")

    monkeypatch.setattr(dl, "download_ckan", broken)
    monkeypatch.setattr(dl, "ckan_modified", lambda *a: None)
    rc = dl.run(args(only="aire_dia"))
    manifest = json.loads((dl.RAW_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert rc == 1
    assert manifest["aire_dia"]["sha256"] == "old"
    assert "error" in manifest["aire_dia"]["last_failure"]


def test_wfs_timestamp_is_not_a_change(dl, monkeypatch):
    # GeoServer pone un timeStamp distinto en cada respuesta y no manda ETag ni Last-Modified
    bodies = iter([b'{"type":"FeatureCollection","features":[],"timeStamp":"2026-10-14T13:41:11.102Z","crs":null}',
                   b'{"type":"FeatureCollection","features":[],"timeStamp":"2026-10-14T13:41:12.181Z","crs":null}'])
    monkeypatch.setattr(dl, "fetch_conditional", lambda url, previous, timeout=300: (next(bodies), {}))
    e1 = dl.download_source("municipios", dl.SOURCES["municipios"], {}, force=False)
    e2 = dl.download_source("municipios", dl.SOURCES["municipios"], e1, force=False)
    assert e1["changed"] is True and e2["changed"] is False


def test_wfs_generated_fid_is_not_a_change(dl, monkeypatch):
    # capas sin clave primaria: GeoServer inventa un id "<capa>.fid-<uuid>_<n>" en cada peticion
    bodies = iter([b'{"features":[{"type":"Feature","id":"CAPA.fid-4fcc7590_1a13aa0262d_-1802","properties":{"MUN":"001"}}]}',
                   b'{"features":[{"type":"Feature","id":"CAPA.fid-5721aa4e_1a13a9ff168_277","properties":{"MUN":"001"}}]}',
                   b'{"features":[{"type":"Feature","id":"CAPA.fid-5721aa4e_1a13a9ff168_277","properties":{"MUN":"002"}}]}'])
    monkeypatch.setattr(dl, "fetch_conditional", lambda url, previous, timeout=300: (next(bodies), {}))
    e1 = dl.download_source("eiel_deporte", dl.SOURCES["eiel_deporte"], {}, force=False)
    e2 = dl.download_source("eiel_deporte", dl.SOURCES["eiel_deporte"], e1, force=False)
    e3 = dl.download_source("eiel_deporte", dl.SOURCES["eiel_deporte"], e2, force=False)
    assert e2["changed"] is False
    assert e3["changed"] is True                                  # un cambio real si se detecta


def test_aemet_without_key_gives_clear_error(dl, monkeypatch):
    monkeypatch.setattr(dl, "read_env", lambda path=None: {})
    with pytest.raises(RuntimeError, match="AEMET_API_KEY"):
        dl.download_aemet(dl.RAW_DIR / "aemet", "28065")


def test_aemet_key_not_in_urls_or_files(dl, monkeypatch):
    key = "SECRET-KEY-123"
    monkeypatch.setattr(dl, "read_env", lambda path=None: {"AEMET_API_KEY": key, "AEMET_PAUSE_S": "0"})
    seen = []

    def fake_fetch(url, timeout=300, headers=None):
        seen.append((url, headers))
        if "opendata/api/prediccion" in url:
            return json.dumps({"estado": 200, "datos": "https://opendata.aemet.es/opendata/sh/abc"}).encode()
        return b'[{"nombre": "Getafe", "prediccion": {"dia": []}}]'

    monkeypatch.setattr(dl, "fetch", fake_fetch)
    paths, urls = dl.download_aemet(dl.RAW_DIR / "aemet", "28065")
    assert all(key not in u for u in urls)
    assert all(key not in p.read_text(encoding="latin-1") for p in paths)
    assert seen[0][1]["api_key"] == key and key not in seen[0][0]


def test_aemet_status_429_is_error(dl, monkeypatch):
    monkeypatch.setattr(dl, "read_env", lambda path=None: {"AEMET_API_KEY": "k", "AEMET_PAUSE_S": "0"})
    monkeypatch.setattr(dl, "fetch", lambda url, timeout=300, headers=None: json.dumps(
        {"estado": 429, "descripcion": "Límite de peticiones"}).encode())
    with pytest.raises(RuntimeError, match="429"):
        dl.download_aemet(dl.RAW_DIR / "aemet", "28065")


def test_aemet_all_reads_179_municipalities(dl):
    folder = dl.RAW_DIR / "municipios"
    folder.mkdir(parents=True)
    feats = [{"type": "Feature", "properties": {"CDMUNICIPIO": f"{i:03d}"}, "geometry": None} for i in range(1, 180)]
    (folder / "municipios.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}))
    assert len(dl.aemet_municipalities("todos")) == 179
    assert dl.aemet_municipalities("28065,28079") == ["28065", "28079"]


def test_read_env_reads_app_env(dl):
    (dl.APP_DIR / ".env").write_text("AEMET_API_KEY=abc\n# comentario\n", encoding="utf-8")
    assert dl.read_env()["AEMET_API_KEY"] == "abc"


def test_unchanged_clears_last_failure(dl, monkeypatch):
    # un fallo de ayer no debe quedarse pegado si hoy la fuente responde bien (304 / sin cambios)
    monkeypatch.setattr(dl, "fetch_conditional", lambda url, previous, timeout=300: (None, {}))
    previous = {"etag": '"v1"', "sha256": "abc", "files": ["osm/madrid-latest.osm.pbf"],
                "last_failure": {"date": "2026-10-13T04:00:00", "error": "portal caído"}}
    entry = dl.download_source("osm", dl.SOURCES["osm"], previous, force=False)
    assert "last_failure" not in entry


def test_concurrent_run_keeps_other_entries(dl, monkeypatch):
    # dos ejecuciones solapadas (cron diario y horario): ninguna borra lo que escribio la otra
    dl.RAW_DIR.mkdir(parents=True)
    manifest_path = dl.RAW_DIR / "manifest.json"
    manifest_path.write_text(json.dumps({"farmacias": {"sha256": "old"}}), encoding="utf-8")

    def other_run_writes(key, src, previous, force, aemet_municipalities=None):
        # mientras esta ejecucion descarga, otra actualiza farmacias en el manifiesto
        manifest_path.write_text(json.dumps({"farmacias": {"sha256": "new"}}), encoding="utf-8")
        return {"sha256": "x", "changed": True, "bytes": 0}

    monkeypatch.setattr(dl, "download_source", other_run_writes)
    assert dl.run(args(only="ay_trafico")) == 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["farmacias"]["sha256"] == "new"
    assert manifest["ay_trafico"]["sha256"] == "x"


def test_aemet_all_without_municipalities_gives_clear_error(dl):
    # sin municipios.geojson, "todos" debe explicar que hacer, no un FileNotFoundError suelto
    with pytest.raises(RuntimeError, match="--only municipios"):
        dl.aemet_municipalities("todos")


def test_unchanged_hash_keeps_downloaded(dl, monkeypatch):
    # RF-19: "actualizado hace..." es cuando cambio el dato, no cuando se comprobo
    monkeypatch.setattr(dl, "fetch_conditional", lambda url, previous, timeout=300: (b"<xml/>", {}))
    e1 = dl.download_source("ay_trafico", dl.SOURCES["ay_trafico"], {}, force=False)
    e1 = {**e1, "downloaded": "2026-10-01T10:00:00", "checked": "2026-10-01T10:00:00"}
    e2 = dl.download_source("ay_trafico", dl.SOURCES["ay_trafico"], e1, force=False)
    assert e2["changed"] is False
    assert e2["downloaded"] == "2026-10-01T10:00:00"
    assert e2["checked"] != "2026-10-01T10:00:00"
    e3 = dl.download_source("ay_trafico", dl.SOURCES["ay_trafico"], e1, force=True)
    assert e3["downloaded"] != "2026-10-01T10:00:00"           # con --force cuenta como descarga nueva
