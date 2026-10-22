"""
Regression and verification test suite for CAT Browser overhaul:
1. Strict test data isolation (never writes to user's ~/.cat_browser_tabs.json).
2. Atomic persistence with .bak safety copies.
3. Crash & renderer termination recovery using fresh SecureWebEnginePage recreation (prevents 0xC0000005).
4. Kitty's Viewer naming, sibling collection navigation, and sandboxing.
5. AI Agent screenshot capture with timestamped naming and functional [View Screenshot] clickable link.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QUrl

# Ensure QApplication exists for Qt widget tests
app = QApplication.instance()
if not app:
    app = QApplication(["--platform", "offscreen"])

from calc_terminal.browser.browser_state import BrowserState, TabInfo
from calc_terminal.browser_gui.qt_browser import (
    CATBrowserWindow,
    SecureWebEngineView,
    SecureWebEnginePage,
    set_active_browser_window,
    get_active_browser_window,
)
from calc_terminal.device_control import BrowserProvider, DesktopProvider
from calc_terminal.agent import TOOLS


def test_test_data_isolation_never_alters_real_user_tabs(tmp_path, monkeypatch):
    """Verify test environment auto-detection isolates all persistence and NEVER alters ~/.cat_browser_tabs.json."""
    real_user_file = Path.home() / ".cat_browser_tabs.json"
    real_mtime_before = real_user_file.stat().st_mtime if real_user_file.exists() else None

    # Instantiate BrowserState inside test environment
    state = BrowserState()
    # Confirm it diverted to an isolated test path
    assert "cat_test_isolated_" in str(state.tabs_path)
    assert state.tabs_path != real_user_file

    # Add a mock test tab and persist
    tab = TabInfo(id="test_tab_isolation", url="https://mytestsite.org/isolated_test", title="Isolated Test")
    state.add_tab(tab)
    state.save_tabs()

    # The isolated file must exist and contain the test tab
    assert state.tabs_path.exists()
    content = state.tabs_path.read_text(encoding="utf-8")
    assert "https://mytestsite.org/isolated_test" in content

    # The real user tabs file must remain completely untouched!
    if real_user_file.exists():
        assert real_user_file.stat().st_mtime == real_mtime_before
        real_content = real_user_file.read_text(encoding="utf-8")
        assert "isolated_test" not in real_content


def test_atomic_file_persistence_creates_bak_and_prevents_corruption(tmp_path):
    """Verify _atomic_write_json creates a valid backup and atomically replaces files."""
    target_file = tmp_path / "state_tabs.json"
    bak_file = target_file.with_suffix(".json.bak")

    # Initial write
    initial_data = {"version": "0.8.0", "tabs": [{"id": "tab1", "url": "https://google.com"}]}
    BrowserState._atomic_write_json(target_file, initial_data)
    assert target_file.exists()
    assert json.loads(target_file.read_text(encoding="utf-8")) == initial_data

    # Second write: verify backup creation and replacement
    second_data = {"version": "0.8.0", "tabs": [{"id": "tab2", "url": "https://catbrowser.local"}]}
    BrowserState._atomic_write_json(target_file, second_data)

    assert target_file.exists()
    assert json.loads(target_file.read_text(encoding="utf-8")) == second_data
    assert bak_file.exists()
    assert json.loads(bak_file.read_text(encoding="utf-8")) == initial_data


def test_renderer_crash_recovery_recreates_page_without_0xc0000005(tmp_path):
    """Verify that renderer termination triggers page recreation via _recreate_and_load / _recreate_and_set_html
    rather than invoking load() on the dead page, preventing Qt6WebEngineCore.dll access violation.
    """
    win = CATBrowserWindow()
    set_active_browser_window(win)

    # Open a web page tab so the view is a real SecureWebEngineView
    tab_idx = win._new_tab("https://test-renderer.local", switch=True)
    initial_view = win._views[tab_idx]
    assert isinstance(initial_view, SecureWebEngineView)
    initial_page = initial_view.page()
    assert initial_page is not None
    assert isinstance(initial_page, SecureWebEnginePage)

    # Verify _recreate_and_load installs a fresh SecureWebEnginePage
    target_url = "https://safe-recovered.local"
    recreated_page = win._recreate_and_load(initial_view, target_url)

    assert recreated_page is not initial_page
    assert initial_view.page() is recreated_page
    assert isinstance(recreated_page, SecureWebEnginePage)
    assert recreated_page.requestedUrl().toString().rstrip("/") == target_url.rstrip("/")

    # Verify _recreate_and_set_html installs a fresh SecureWebEnginePage with custom error html
    err_html = "<html><body><h1>Renderer Crash Handled Safely</h1></body></html>"
    recreated_err_page = win._recreate_and_set_html(initial_view, err_html)

    assert recreated_err_page is not recreated_page
    assert initial_view.page() is recreated_err_page
    assert isinstance(recreated_err_page, SecureWebEnginePage)


def test_renderer_process_terminated_bounded_retries(tmp_path):
    """Verify that renderProcessTerminated stops automatic reload loops after max retries."""
    win = CATBrowserWindow()
    tab_idx = win._new_tab("https://crash-test.local/article", switch=True)
    view = win._views[tab_idx]
    assert isinstance(view, SecureWebEngineView)
    page = view.page()
    assert isinstance(page, SecureWebEnginePage)
    page._last_committed_url = "https://crash-test.local/article"
    view._pending_url = "https://crash-test.local/article"

    term_status = 1  # CrashedTerminationStatus
    exit_code = 3221225477  # 0xC0000005

    with patch.object(win, "_recreate_and_set_html") as mock_recreate_html:
        # First 3 crashes trigger bounded reload with backoff without showing the final error page
        for i in range(3):
            page._on_render_process_terminated(term_status, exit_code)
            assert page._crash_retries.get("https://crash-test.local/article") == i + 1
        assert mock_recreate_html.call_count == 0

        # 4th crash: exceeds max retries, terminates auto-reload loop and renders recovery guard HTML
        page._on_render_process_terminated(term_status, exit_code)
        assert page._crash_retries.get("https://crash-test.local/article") == 4
        assert mock_recreate_html.call_count == 1


def test_kittys_viewer_naming_consistency_and_title():
    """Verify exact product name 'Kitty's Viewer' in viewer.html and web server endpoints."""
    viewer_path = Path(__file__).parent.parent / "web" / "static" / "viewer.html"
    assert viewer_path.exists()
    content = viewer_path.read_text(encoding="utf-8")

    # Exact product title
    assert "<title>Kitty's Viewer · CAT Browser</title>" in content
    assert "Kitty's Viewer" in content
    assert "Image preview" not in content or "Kitty’s Viewer · Image" in content

    # Test server endpoint fallback
    from calc_terminal.web.server import app as fastapi_app
    from starlette.testclient import TestClient
    client = TestClient(fastapi_app)

    res = client.get("/viewer.html")
    assert res.status_code == 200
    assert "Kitty's Viewer" in res.text


def test_sibling_images_endpoint_for_collection_navigation(tmp_path):
    """Verify /api/file/sibling-images returns ordered image filenames in the same folder for collection navigation."""
    from calc_terminal.web.server import app as fastapi_app
    from starlette.testclient import TestClient
    client = TestClient(fastapi_app)

    # Create dummy images in a folder
    img1 = tmp_path / "img_a.png"
    img2 = tmp_path / "img_b.jpg"
    img3 = tmp_path / "img_c.webp"
    doc = tmp_path / "doc.txt"
    img1.write_bytes(b"\x89PNG\r\n\x1a\n")
    img2.write_bytes(b"\xff\xd8\xff")
    img3.write_bytes(b"RIFF....WEBP")
    doc.write_text("not an image")

    res = client.get(f"/api/file/sibling-images?path={img2}")
    assert res.status_code == 200
    data = res.json()
    assert "images" in data
    assert data["images"] == ["img_a.png", "img_b.jpg", "img_c.webp"]
    assert data["index"] == 1


def test_agent_screenshot_capture_and_clickable_link(tmp_path):
    """Verify agent screenshot creation produces timestamped file and functional [View Screenshot] clickable link."""
    provider = BrowserProvider()
    assert provider.available()

    # Execute screenshot action
    result = provider.execute("screenshot", {})
    assert result.get("ok") is True

    # Validate output link format
    output = result.get("output", "")
    assert "Screenshot captured successfully" in output
    assert "[View Screenshot](http://localhost:8765/viewer.html?path=" in output

    # Validate saved file
    path = result.get("path")
    assert path is not None
    p = Path(path)
    assert p.exists()
    assert p.name.startswith("CAT_Screenshot_")
    assert p.suffix == ".png"
    assert p.stat().st_size > 0

    # Cleanup test screenshot
    try:
        p.unlink()
    except Exception:
        pass


def test_desktop_provider_screenshot_and_link(tmp_path):
    """Verify DesktopProvider screenshot action also generates timestamped artifact and [View Screenshot] link."""
    provider = DesktopProvider()
    assert provider.available()

    result = provider.execute({"action": "screenshot", "target": ""})
    assert result.get("ok") is True

    output = result.get("output", "")
    assert "Screenshot captured successfully" in output
    assert "[View Screenshot](http://localhost:8765/viewer.html?path=" in output

    path = result.get("path")
    assert path is not None
    p = Path(path)
    assert p.exists()
    assert p.name.startswith("CAT_Screenshot_")
    assert p.suffix == ".png"

    # Cleanup test screenshot
    try:
        p.unlink()
    except Exception:
        pass


def test_cat_browser_tool_registration_documents_screenshot():
    """Verify cat_browser tool is in TOOLS dictionary and documents screenshot functionality."""
    assert "cat_browser" in TOOLS
    cat_spec = TOOLS["cat_browser"]
    assert "screenshot" in cat_spec["desc"]
    assert "screenshot" in cat_spec["args"]
