import os
import sys
import pytest

def test_fomoji_exclusivity_middleware():
    paths = [
        "calc_terminal/fomoji_server/src/security.js",
        "fomoji-updated/fomoji-server/src/security.js"
    ]
    for p in paths:
        assert os.path.exists(p), f"Missing {p}"
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        assert "isLoopback" in content, f"isLoopback missing in {p}"
        assert "req.hostname === 'localhost'" in content, f"localhost check missing in {p}"
        assert "queryCat" in content, f"queryCat missing in {p}"
        assert "cookieCat" in content, f"cookieCat missing in {p}"
        assert "cat_browser=1" in content, f"cat_browser cookie missing in {p}"
        assert "Open in CAT Browser" in content, f"Button missing in {p}"

def test_agent_browser_tile_removed():
    paths = [
        "calc_terminal/browser_gui/qt_browser.py",
        "calc_terminal/host/desktop.py"
    ]
    for p in paths:
        assert os.path.exists(p), f"Missing {p}"
        with open(p, "r", encoding="utf-8") as f:
            lines = f.readlines()
        in_shortcuts = False
        shortcut_lines = []
        for line in lines:
            if "shortcuts = [" in line:
                in_shortcuts = True
                continue
            if in_shortcuts:
                if "]" in line:
                    in_shortcuts = False
                    break
                shortcut_lines.append(line.strip())
        joined = " ".join(shortcut_lines)
        assert "Agent Browser" not in joined, f"'Agent Browser' still in shortcuts in {p}"
        assert "Autonomous Web Agent" not in joined, f"'Autonomous Web Agent' still in shortcuts in {p}"
        assert "CAT Workspace" in joined, f"'CAT Workspace' missing in {p}"
        assert "https://cat-v0-7-9.vercel.app/" in joined, f"Vercel link missing in shortcuts in {p}"

def test_captcha_immunity_and_user_agent():
    paths = [
        "calc_terminal/browser_gui/qt_browser.py",
        "calc_terminal/host/desktop.py"
    ]
    for p in paths:
        with open(p, "r", encoding="utf-8") as f:
            content = f.read()
        assert "Chrome/131.0.0.0" in content, f"Modern clean User-Agent missing in {p}"
        assert "cat_stealth_anti_captcha" in content, f"Stealth anti-captcha script missing in {p}"
        assert "'webdriver'" in content, f"webdriver masking missing in {p}"

    with open("calc_terminal/host/launcher.py", "r", encoding="utf-8") as f:
        launcher_src = f.read()
    assert "--disable-blink-features=AutomationControlled" in launcher_src
    # On Windows, --no-sandbox must not be unconditional
    assert 'if getattr(os, "geteuid", None) is not None and os.geteuid() == 0:' in launcher_src
    assert "--js-flags=--max-old-space-size=" in launcher_src

def test_vercel_and_mangum_configuration():
    assert os.path.exists("vercel.json")
    with open("vercel.json", "r", encoding="utf-8") as f:
        vjson = f.read()
    assert "@vercel/python" in vjson

    with open("requirements.txt", "r", encoding="utf-8") as f:
        reqs = f.read()
    assert "mangum>=0.17.0" in reqs

    with open("api/index.py", "r", encoding="utf-8") as f:
        api_src = f.read()
    assert "handler = Mangum(app, lifespan=\"off\")" in api_src
    assert "standalone_index" in api_src

def test_api_index_endpoints():
    sys.path.insert(0, ".")
    from starlette.testclient import TestClient
    from api.index import app

    client = TestClient(app)
    r_index = client.get("/")
    assert r_index.status_code == 200
    assert "<!DOCTYPE html>" in r_index.text

    r_health = client.get("/health")
    assert r_health.status_code == 200

    r_diag = client.get("/api/diag")
    assert r_diag.status_code == 200
    data = r_diag.json()
    assert data.get("status") == "healthy"

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
