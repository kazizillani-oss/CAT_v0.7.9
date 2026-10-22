"""
Tests for Fatty CAT Vercel Deployment Integration:
Verifies api/index.py entry point, vercel.json configuration, requirements.txt,
and ASGI routes for Cloud IDE.
"""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


def test_vercel_config_files_exist():
    """Verify that all files necessary for Vercel deployment exist in the root."""
    root = Path(__file__).resolve().parents[3]
    vercel_json = root / "vercel.json"
    api_index = root / "api" / "index.py"
    req_txt = root / "requirements.txt"
    vercel_ignore = root / ".vercelignore"

    assert vercel_json.is_file(), "vercel.json missing in repository root"
    assert api_index.is_file(), "api/index.py missing in repository root"
    assert req_txt.is_file(), "requirements.txt missing in repository root"
    assert vercel_ignore.is_file(), ".vercelignore missing in repository root"

    # Validate vercel.json structure
    with open(vercel_json, "r", encoding="utf-8") as f:
        config = json.load(f)
    assert config.get("version") == 2
    rewrites = config.get("rewrites", [])
    assert any(r.get("destination") == "/api/index.py" for r in rewrites)


def test_vercel_api_entrypoint_and_routes():
    """Verify api/index.py imports app cleanly and responds with 200 on key endpoints."""
    import sys
    root = Path(__file__).resolve().parents[3]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))

    from api.index import app

    client = TestClient(app)

    # Root route serves index.html (Fatty CAT Cloud IDE)
    res = client.get("/")
    assert res.status_code == 200
    assert "FATTY CAT" in res.text or "cct-editor-pane" in res.text

    # Permissions endpoint
    res_perm = client.get("/api/permissions")
    assert res_perm.status_code == 200

    # Missions endpoint
    res_missions = client.get("/api/missions")
    assert res_missions.status_code == 200

    # Mascot sprite sheet
    res_mascot = client.get("/mascots/fattycat-directions.webp")
    assert res_mascot.status_code == 200
