"""La ingesta escribe el .duckdb que lee la API: la version de DuckDB debe ser identica."""
import re


def pinned(pyproject_text, package):
    m = re.search(rf'"{package}==([^"]+)"', pyproject_text)
    return m.group(1) if m else None


def test_duckdb_version_matches_api(root):
    ingest = pinned((root / "pyproject.toml").read_text(encoding="utf-8"), "duckdb")
    api = pinned((root.parent / "api" / "pyproject.toml").read_text(encoding="utf-8"), "duckdb")
    assert ingest is not None and ingest == api
