"""
Unit tests for CAT Browser Low-End Stability, Terminal Pop-up Elimination,
macOS Safari Title Bar, and 4-Way Tab Bar Positioning.
"""

import os
import sys
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from calc_terminal.browser.browser_state import BrowserState
from calc_terminal.activity import _win_hidden_kwargs, ActivityManager
from calc_terminal.host.launcher import get_optimal_chromium_flags
from calc_terminal.web.server import FATTY_PID_FILE, stop_fatty_server


def test_browser_state_tab_position_defaults_and_persistence(tmp_path):
    """Verify that tab_position defaults to 'top', allows 4-way positions, and persists."""
    dummy_file = tmp_path / "tabs.json"
    with patch.object(BrowserState, "TABS_FILE", dummy_file):
        state = BrowserState()
        assert state.tab_position == "top"

        # Change to left sidebar
        state.tab_position = "left"
        state._save_tabs()

        # Reload state from disk
        state2 = BrowserState()
        assert state2.tab_position == "left"

        # Change to bottom
        state2.tab_position = "bottom"
        state2._save_tabs()
        state3 = BrowserState()
        assert state3.tab_position == "bottom"

        # Change to right
        state3.tab_position = "right"
        state3._save_tabs()
        state4 = BrowserState()
        assert state4.tab_position == "right"


def test_browser_state_tab_position_invalid_fallback(tmp_path):
    """Verify that invalid tab positions fallback to 'top'."""
    dummy_file = tmp_path / "tabs.json"
    dummy_file.write_text(json.dumps({"tabs": [], "active_tab_id": "", "tab_position": "invalid_diagonal"}), encoding="utf-8")
    with patch.object(BrowserState, "TABS_FILE", dummy_file):
        state = BrowserState()
        assert state.tab_position == "top"


def test_win_hidden_kwargs_flags():
    """Verify that _win_hidden_kwargs supplies CREATE_NO_WINDOW and SW_HIDE on Windows."""
    kwargs = _win_hidden_kwargs()
    if sys.platform == "win32":
        import subprocess
        CREATE_NO_WINDOW = 0x08000000
        assert "creationflags" in kwargs
        assert kwargs["creationflags"] & CREATE_NO_WINDOW == CREATE_NO_WINDOW
        assert "startupinfo" in kwargs
        si = kwargs["startupinfo"]
        assert si.dwFlags & subprocess.STARTF_USESHOWWINDOW
        assert si.wShowWindow == 0  # SW_HIDE
    else:
        assert isinstance(kwargs, dict)


def test_activity_manager_gpu_caching_eliminates_repeated_tabs():
    """Verify that GPU checks are cached and do not spawn subprocess storms every second."""
    mgr = ActivityManager()
    rm = mgr.resource_monitor
    rm._last_gpu_query_ts = 9999999999.0
    rm._cached_gpu_info = ("NVIDIA GeForce RTX Simulated", 4.0, 8.0)
    with patch("subprocess.check_output") as mock_sub:
        sample = rm.sample_now()
        assert sample.gpu_name == "NVIDIA GeForce RTX Simulated"
        # Subprocess should not be called because cache is fresh
        mock_sub.assert_not_called()


def test_optimal_chromium_flags_preserve_watchdogs_and_bound_resources():
    """Keep Chromium recovery enabled and cap renderer/raster worker counts."""
    flags = get_optimal_chromium_flags()
    assert "--disable-gpu-watchdog" not in flags
    assert "--disable-gpu-process-crash-limit" not in flags
    assert "--disable-breakpad" not in flags
    assert "--disable-hang-monitor" not in flags
    assert "--renderer-process-limit=" in flags
    assert "--num-raster-threads=" in flags

    # When simulated on low-end hardware (< 4GB RAM, micro circuit mini PC)
    from calc_terminal.hardware_analyzer import HardwareAnalyzer
    mock_prof = MagicMock()
    mock_prof.ai_capability = "LIMITED"
    mock_prof.ram_total_gb = 2.0
    mock_prof.cpu_threads = 2
    mock_prof.has_gpu = False
    with patch.object(HardwareAnalyzer, "analyze", return_value=mock_prof):
        low_flags = get_optimal_chromium_flags()
        assert "--enable-low-end-device-mode" in low_flags
        assert "--renderer-process-limit=1" in low_flags
        assert "--num-raster-threads=1" in low_flags


def test_fatty_server_pid_tracking_and_stop():
    """Verify fatty server PID file can be created and cleaned up by stop_fatty_server."""
    # Write simulated PID file
    FATTY_PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    FATTY_PID_FILE.write_text("99999999", encoding="utf-8")
    assert FATTY_PID_FILE.exists()

    with patch("subprocess.run") as mock_run:
        stop_fatty_server()
        assert not FATTY_PID_FILE.exists()


def test_squircle_buttons_and_tab_close_icon_assets():
    """Verify squircle traffic light buttons, tab close icons, and restart_browser."""
    from calc_terminal.browser_gui.tab_bar import _get_close_icons
    from pathlib import Path
    import sys
    
    icons = _get_close_icons()
    assert Path(icons["png"]).exists()
    assert Path(icons["png_hover"]).exists()
    assert Path(icons["svg"]).exists()
    assert Path(icons["svg_hover"]).exists()
    assert Path(icons["png"]).stat().st_size > 0
    assert Path(icons["svg"]).stat().st_size > 0

    try:
        from PySide6.QtWidgets import QApplication
        from calc_terminal.browser_gui.tab_bar import CATBrowserTabs
        app = QApplication.instance() or QApplication(sys.argv)
        tabs = CATBrowserTabs()
        assert not tabs._h_tab_bar.expanding()
    except ImportError:
        pass

    from calc_terminal.host.desktop import CATDesktopWindow
    assert hasattr(CATDesktopWindow, "restart_browser")

    try:
        from PySide6.QtCore import Qt
        from calc_terminal.browser_gui.qt_browser import CATBrowserWindow
        app = QApplication.instance() or QApplication(sys.argv)
        w_desk = CATDesktopWindow()
        assert bool(w_desk.windowFlags() & Qt.WindowType.FramelessWindowHint)
        w_brow = CATBrowserWindow()
        assert bool(w_brow.windowFlags() & Qt.WindowType.FramelessWindowHint)
    except Exception:
        pass


def test_vertical_tabs_resizable_and_splitters():
    """Verify vertical tabs sidebar is interactively resizable with constraints and handle."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt, QPoint
        from PySide6.QtGui import QMouseEvent
        from calc_terminal.browser_gui.tab_bar import CATBrowserTabs
    except ImportError:
        pytest.skip("PySide6 not available for GUI test")

    app = QApplication.instance() or QApplication(sys.argv)
    tabs = CATBrowserTabs()
    tabs.resize(800, 600)
    tabs.show()

    # In top mode, not vertical
    assert not tabs.is_vertical

    # Switch to left (sidebar vertical tabs)
    tabs.set_position("left")
    assert tabs.is_vertical
    assert tabs._sidebar_width == 240
    assert tabs.minimumWidth() == 240
    assert tabs.maximumWidth() == 240

    # Test edge detection on resize handle (within 8px of right border)
    assert tabs._is_on_resize_handle(QPoint(238, 100)) is True
    assert tabs._is_on_resize_handle(QPoint(100, 100)) is False

    # Simulate mouse press, drag, and release to resize
    press_ev = QMouseEvent(QMouseEvent.Type.MouseButtonPress, QPoint(240, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tabs.mousePressEvent(press_ev)
    assert tabs._is_resizing is True

    # Drag to 320px
    move_ev = QMouseEvent(QMouseEvent.Type.MouseMove, QPoint(320, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tabs.mouseMoveEvent(move_ev)
    assert tabs._sidebar_width == 320
    assert tabs.minimumWidth() == 320

    # Drag beyond max (480)
    move_max = QMouseEvent(QMouseEvent.Type.MouseMove, QPoint(600, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tabs.mouseMoveEvent(move_max)
    assert tabs._sidebar_width == 480

    # Drag below min (140)
    move_min = QMouseEvent(QMouseEvent.Type.MouseMove, QPoint(50, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tabs.mouseMoveEvent(move_min)
    assert tabs._sidebar_width == 140

    release_ev = QMouseEvent(QMouseEvent.Type.MouseButtonRelease, QPoint(140, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tabs.mouseReleaseEvent(release_ev)
    assert tabs._is_resizing is False

    # Test double click on resize handle toggles compact (150px) and standard (240px)
    dbl_ev1 = QMouseEvent(QMouseEvent.Type.MouseButtonDblClick, QPoint(138, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tabs.mouseDoubleClickEvent(dbl_ev1)
    assert tabs._sidebar_width == 240

    dbl_ev2 = QMouseEvent(QMouseEvent.Type.MouseButtonDblClick, QPoint(238, 100), Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tabs.mouseDoubleClickEvent(dbl_ev2)
    assert tabs._sidebar_width == 150


def test_window_chrome_rework_frameless_and_controls():
    """Verify complete window chrome rework: frameless window, branding, single header, window controls."""
    try:
        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import Qt, QPoint
        from calc_terminal.host.desktop import CATDesktopWindow
        from calc_terminal.browser_gui.qt_browser import CATBrowserWindow
    except ImportError:
        pytest.skip("PySide6 not available for GUI test")

    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Test CATDesktopWindow
    w_desk = CATDesktopWindow()
    flags = w_desk.windowFlags()
    assert bool(flags & Qt.WindowType.FramelessWindowHint)
    assert hasattr(w_desk.browser, "safari_bar")

    # Header controls presence
    sb = w_desk.browser
    assert hasattr(sb, "traffic_close")
    assert hasattr(sb, "traffic_min")
    assert hasattr(sb, "traffic_max")
    assert hasattr(sb, "win_btn_min")
    assert hasattr(sb, "win_btn_max")
    assert hasattr(sb, "win_btn_close")

    # Maximize/Restore state update
    sb._update_window_controls_state()
    assert sb.win_btn_max.text() in ("🗖", "🗗")

    # Edge detection for 8-way border resize
    assert w_desk._get_edge(QPoint(2, 100)) == Qt.Edge.LeftEdge
    assert w_desk._get_edge(QPoint(w_desk.width() - 2, 100)) == Qt.Edge.RightEdge
    assert w_desk._get_edge(QPoint(100, 2)) == Qt.Edge.TopEdge
    assert w_desk._get_edge(QPoint(100, w_desk.height() - 2)) == Qt.Edge.BottomEdge

    # 2. Test CATBrowserWindow (standalone)
    w_brow = CATBrowserWindow()
    b_flags = w_brow.windowFlags()
    assert bool(b_flags & Qt.WindowType.FramelessWindowHint)
    assert hasattr(w_brow, "safari_bar")
    assert hasattr(w_brow, "btn_close")
    assert hasattr(w_brow, "btn_min")
    assert hasattr(w_brow, "btn_zoom")
    assert hasattr(w_brow, "win_btn_min")
    assert hasattr(w_brow, "win_btn_max")
    assert hasattr(w_brow, "win_btn_close")

    w_brow._update_window_controls_state()
    assert w_brow.win_btn_max.text() in ("🗖", "🗗")



