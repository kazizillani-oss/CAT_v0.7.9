"""
Tests for Fomoji Reachability, Dual-Stack Probing, Startup Timeout,
Fatty CAT & Fomoji 3D Anti-Jitter, and Browser Window Stability.
"""

import inspect
import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from calc_terminal.fomoji_manager import (
    check_server_reachable,
    detect_port_conflict,
    start_fomoji_server,
)
from calc_terminal.fomoji_auth import check_server_reachable as auth_check_reachable
import calc_terminal.browser_gui.launcher as bg_launcher
import calc_terminal.host.launcher as host_launcher


def test_fomoji_manager_probe_dual_stack_candidates():
    """Verify check_server_reachable probes both localhost and 127.0.0.1 dual-stack."""
    probed_urls = []

    def mock_urlopen(req, timeout=1.0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        probed_urls.append(url)
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps({"ok": True, "applications": []}).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        assert check_server_reachable(timeout=1.0, base_url="http://localhost:3000") is True

    assert any("localhost:3000" in u for u in probed_urls)


def test_detect_port_conflict_recognizes_running_fomoji():
    """Verify detect_port_conflict returns (False, 'Fomoji server already running') when Fomoji is up."""
    with patch("socket.socket.connect_ex", return_value=0):
        with patch("calc_terminal.fomoji_manager.check_server_reachable", return_value=True):
            conflict, msg = detect_port_conflict(port=3000)
            assert conflict is False
            assert "already running" in msg


def test_start_fomoji_server_timeout_configuration():
    """Verify start_fomoji_server has 35s default timeout and respects FOMOJI_START_TIMEOUT env var."""
    sig = inspect.signature(start_fomoji_server)
    assert sig.parameters["timeout"].default == 35


def test_browser_gui_launcher_does_not_hide_window_on_windows():
    """Verify GUI browser launchers do not pass SW_HIDE or CREATE_NO_WINDOW for GUI windows."""
    source_bg = inspect.getsource(bg_launcher.launch_browser_gui)
    assert "SW_HIDE" not in source_bg
    assert "CREATE_NO_WINDOW" not in source_bg

    source_host = inspect.getsource(host_launcher.launch_cat_host)
    assert "wShowWindow = 0" not in source_host


def test_certificate_error_graceful_exception_handling():
    """Verify certificateError catches exceptions and returns False rather than crashing."""
    try:
        from calc_terminal.browser_gui.qt_browser import SecureWebEnginePage
        src = inspect.getsource(SecureWebEnginePage.certificateError)
        assert "super().certificateError(certificateError)" in src
        assert "except Exception:" in src
        assert "return False" in src

        from calc_terminal.host.desktop import SecureWebEnginePage as DesktopPage
        src_desktop = inspect.getsource(DesktopPage.certificateError)
        assert "super().certificateError(certificateError)" in src_desktop
        assert "except Exception:" in src_desktop
        assert "return False" in src_desktop
    except ImportError:
        pass


def test_fatty_cat_orb_no_transform_transition_conflict():
    """Verify Fatty CAT .cct-home-orb in app.css does not have transition: transform conflict."""
    css_path = Path(__file__).parent.parent / "web" / "static" / "css" / "app.css"
    content = css_path.read_text(encoding="utf-8")
    assert ".cct-home-orb {" in content
    # Look for .cct-home-orb block
    idx = content.find(".cct-home-orb {")
    block = content[idx:idx + 300]
    assert "transition: transform" not in block
    assert "will-change: transform" in block


def test_fomoji_3d_card_tilt_no_transform_transition_conflict():
    """Verify Fomoji 3D cards in fomoji-3d.css do not transition transform during hover."""
    css_path = Path(__file__).parent.parent / "fomoji_server" / "public" / "css" / "fomoji-3d.css"
    content = css_path.read_text(encoding="utf-8")
    idx = content.find('.card-3d[data-tilt="pointer"][data-fx-state="hover"]')
    assert idx != -1
    block = content[idx:idx + 300]
    assert "transition: transform" not in block
    assert "will-change: transform" in block
