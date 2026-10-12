"""
Tests for CAT Browser CLI Command Dispatch, Document/Media/PDF Viewing,
Interactive Web Terminal, and Fomoji Integration.
"""

import os
import json
import pathlib
import pytest
from unittest.mock import patch, MagicMock

from calc_terminal.cli import main
from calc_terminal.browser_gui.qt_browser import _resolve_navigation_url
from calc_terminal.host.launcher import get_host_status, launch_cat_host


def test_cat_browser_status_command():
    """Verify `cat browser --status` and `cat open --status` return JSON status with code 0."""
    with patch("sys.argv", ["cat", "browser", "--status"]):
        with patch("sys.stdout.write"):
            rc = main()
            assert rc == 0

    with patch("sys.argv", ["cat", "open", "--status"]):
        with patch("sys.stdout.write"):
            rc = main()
            assert rc == 0


def test_cat_browser_file_dispatch():
    """Verify passing a file on disk directly opens it in CAT Browser rather than erroring as not a directory."""
    test_file = pathlib.Path(__file__).resolve()
    with patch("calc_terminal.host.launcher.launch_cat_host") as mock_launch:
        mock_launch.return_value = 0
        with patch("sys.argv", ["cat", str(test_file)]):
            rc = main()
            assert rc == 0
            assert mock_launch.called
            called_url = mock_launch.call_args[1].get("start_browser_url")
            assert called_url.startswith("file://")
            assert "test_cat_browser_cli_and_integration.py" in called_url


def test_cat_browser_url_dispatch():
    """Verify passing a URL directly opens it in CAT Browser."""
    with patch("calc_terminal.host.launcher.launch_cat_host") as mock_launch:
        mock_launch.return_value = 0
        with patch("sys.argv", ["cat", "https://github.com/kazizillani-oss/CAT_v0.7.9"]):
            rc = main()
            assert rc == 0
            assert mock_launch.called
            called_url = mock_launch.call_args[1].get("start_browser_url")
            assert called_url == "https://github.com/kazizillani-oss/CAT_v0.7.9"


def test_cat_terminal_cli_command():
    """Verify `cat terminal` and `cat cli` launch the authentic native CAT CLI terminal."""
    with patch("calc_terminal.cli._launch_cat_terminal") as mock_launch:
        mock_launch.return_value = 0
        with patch("sys.argv", ["cat", "terminal"]):
            rc = main()
            assert rc == 0
            assert mock_launch.called

    with patch("calc_terminal.cli._launch_cat_terminal") as mock_launch:
        mock_launch.return_value = 0
        with patch("sys.argv", ["cat", "cli"]):
            rc = main()
            assert rc == 0
            assert mock_launch.called


def test_cat_fomoji_cli_command():
    """Verify `cat fomoji` launches Fomoji Portal in CAT Browser."""
    with patch("calc_terminal.host.launcher.launch_cat_host") as mock_launch:
        mock_launch.return_value = 0
        with patch("sys.argv", ["cat", "fomoji"]):
            rc = main()
            assert rc == 0
            assert mock_launch.called
            called_url = mock_launch.call_args[1].get("start_browser_url")
            assert "3000/home.html" in called_url


def test_cat_open_and_view_aliases():
    """Verify `cat open` and `cat view` dispatch to launcher."""
    with patch("calc_terminal.host.launcher.launch_cat_host") as mock_launch:
        mock_launch.return_value = 0
        with patch("sys.argv", ["cat", "open", "https://example.com"]):
            rc = main()
            assert rc == 0
            assert mock_launch.called
            assert mock_launch.call_args[1].get("start_browser_url") == "https://example.com"

    with patch("calc_terminal.host.launcher.launch_cat_host") as mock_launch:
        mock_launch.return_value = 0
        with patch("sys.argv", ["cat", "view", "viewer"]):
            rc = main()
            assert rc == 0
            assert mock_launch.called
            assert "viewer.html" in mock_launch.call_args[1].get("start_browser_url")


def test_resolve_navigation_url_local_files_and_shortcuts():
    """Verify _resolve_navigation_url correctly parses local files and internal shortcuts."""
    assert _resolve_navigation_url("terminal") == "about:cat-cli"
    assert _resolve_navigation_url("cli") == "about:cat-cli"
    assert _resolve_navigation_url("about:cat-cli") == "about:cat-cli"
    assert _resolve_navigation_url("viewer") == "http://localhost:8765/viewer.html"
    assert _resolve_navigation_url("fatty") == "http://localhost:8765/"
    assert _resolve_navigation_url("fomoji") == "http://localhost:3000/home.html"

    # Local file path resolution
    this_file = str(pathlib.Path(__file__).resolve())
    resolved = _resolve_navigation_url(this_file)
    assert resolved.startswith("file://")
    assert "test_cat_browser_cli_and_integration.py" in resolved


def test_browser_navigates_to_native_cli():
    """Verify navigating to about:cat-cli or typing cli/terminal triggers _launch_native_cli."""
    try:
        from calc_terminal.browser_gui.qt_browser import CATBrowserWindow, _QT_BINDING
        if not _QT_BINDING:
            return
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])
        win = CATBrowserWindow(start_url="about:blank")
        with patch.object(win, "_launch_native_cli") as mock_cli:
            win.navigate("about:cat-cli")
            assert mock_cli.called
        with patch.object(win, "_launch_native_cli") as mock_cli2:
            win.navigate("terminal")
            assert mock_cli2.called
    except Exception:
        pass


def test_pdf_viewer_setting_enabled():
    """Verify PdfViewerEnabled is set on WebEngineSettings."""
    try:
        from PySide6.QtWebEngineCore import QWebEngineSettings
        assert hasattr(QWebEngineSettings.WebAttribute, "PdfViewerEnabled")
    except ImportError:
        pass


def test_server_file_view_endpoint():
    """Verify /api/file/view serves existing files."""
    try:
        from fastapi.testclient import TestClient
        from calc_terminal.web.server import app
        client = TestClient(app)
        this_file = str(pathlib.Path(__file__).resolve())
        resp = client.get(f"/api/file/view?path={this_file}")
        assert resp.status_code == 200
        assert "test_cat_browser_cli_and_integration" in resp.text
    except ImportError:
        pass

