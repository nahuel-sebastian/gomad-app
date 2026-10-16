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
    base = dict(list=False, group="minimal", only=None, include_heavy=False, refresh=None, force=False)
    base.update(kw)
    return argparse.Namespace(**base)


def test_every_source_has_level(dl):
    for key, src in dl.SOURCES.items():
        assert src.refresh in dl.REFRESH_LEVELS, key


def test_select_hourly_level(dl):
    assert set(dl.select(args(refresh="hourly"))) == {"aire_dia", "ay_aire", "ay_meteo", "open_meteo"}


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


POINTS_CSV = "ine_code,name,lat,lon\n28065,Getafe,40.2991,-3.6734\n28079,Madrid,40.4654,-3.6965\n"


def test_open_meteo_one_request_for_all_points(dl, monkeypatch, tmp_path):
    """DEC-16: una sola peticion con las coordenadas de config/forecast_points.csv, en su orden, sin clave."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "forecast_points.csv").write_text(POINTS_CSV, encoding="utf-8")
    monkeypatch.setattr(dl, "CONFIG_DIR", tmp_path / "config")
    seen = []

    def fake_fetch(url, timeout=300, headers=None):
        seen.append((url, headers))
        return json.dumps([{"hourly": {}}, {"hourly": {}}]).encode()

    monkeypatch.setattr(dl, "fetch", fake_fetch)
    paths, urls = dl.download_open_meteo(dl.RAW_DIR / "open_meteo")
    assert len(seen) == 1 and seen[0][1] is None
    assert seen[0][0] == dl.OPEN_METEO_URL + "&latitude=40.2991,40.4654&longitude=-3.6734,-3.6965"
    assert sorted(p.name for p in paths) == ["forecast.json", "points.csv"]
    assert (dl.RAW_DIR / "open_meteo" / "points.csv").read_text(encoding="utf-8") == POINTS_CSV


def test_open_meteo_length_mismatch_is_error(dl, monkeypatch, tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "forecast_points.csv").write_text(POINTS_CSV, encoding="utf-8")
    monkeypatch.setattr(dl, "CONFIG_DIR", tmp_path / "config")
    monkeypatch.setattr(dl, "fetch", lambda url, timeout=300, headers=None: b'{"hourly": {}}')
    with pytest.raises(RuntimeError, match="1 puntos de 2"):
        dl.download_open_meteo(dl.RAW_DIR / "open_meteo")
    assert not (dl.RAW_DIR / "open_meteo" / "forecast.json").exists()


def test_open_meteo_url_matches_realtime_yaml(dl):
    import yaml
    cfg = yaml.safe_load((ROOT.parent / "config" / "realtime.yaml").read_text(encoding="utf-8"))
    assert dl.OPEN_METEO_URL == cfg["sources"]["forecast"]["url"]
    assert dl.SOURCES["open_meteo"].refresh == "hourly" and dl.SOURCES["open_meteo"].group == "minimal"


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

    def other_run_writes(key, src, previous, force):
        # mientras esta ejecucion descarga, otra actualiza farmacias en el manifiesto
        manifest_path.write_text(json.dumps({"farmacias": {"sha256": "new"}}), encoding="utf-8")
        return {"sha256": "x", "changed": True, "bytes": 0}

    monkeypatch.setattr(dl, "download_source", other_run_writes)
    assert dl.run(args(only="ay_trafico")) == 0
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["farmacias"]["sha256"] == "new"
    assert manifest["ay_trafico"]["sha256"] == "x"
