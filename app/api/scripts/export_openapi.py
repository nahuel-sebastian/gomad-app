#!/usr/bin/env python3
"""Exporta el contrato OpenAPI para el front: app/frontend/src/api/openapi.json."""
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent      # app/api
sys.path.insert(0, str(ROOT))
from main import app  # noqa: E402

target = ROOT.parent / "frontend" / "src" / "api" / "openapi.json"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Escrito {target}")
