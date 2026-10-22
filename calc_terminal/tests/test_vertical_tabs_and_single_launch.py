"""
Comprehensive tests for CAT Browser Vertical Tabs, Hybrid Tab Bar,
and Single-Attempt Browser Launch Guarantee.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch

# Ensure Qt offscreen platform if running headless
os.environ["QT_QPA_PLATFORM"] = "offscreen"


def test_cat_browser_tabs_api_and_vertical_layout():
    """Verify CATBrowserTabs implements QTabBar API and provides vertical sidebar rows."""
    try:
        from PySide6.QtWidgets import QApplication
        from calc_terminal.browser_gui.tab_bar import CATBrowserTabs, VerticalTabRow
    except ImportError:
        pytest.skip("PySide6 not available for GUI test")

    app = QApplication.instance() or QApplication(sys.argv)

    tabs = CATBrowserTabs()
    assert tabs.count() == 0
    assert tabs.currentIndex() == -1

    # Add tabs
    idx0 = tabs.addTab("Home")
    idx1 = tabs.addTab("Documentation")
    idx2 = tabs.addTab("GitHub Issues")

    assert idx0 == 0
    assert idx1 == 1
    assert idx2 == 2
    assert tabs.count() == 3
    assert tabs.currentIndex() == 0
    assert "Home" in tabs.tabText(0)
    assert "Documentation" in tabs.tabText(1)
    assert "GitHub Issues" in tabs.tabText(2)

    tabs.show()

    # Test Horizontal mode (default "top")
    assert not tabs.is_vertical
    assert not tabs._h_tab_bar.isHidden()
    assert tabs._v_scroll.isHidden()

    # Switch position to "left" (Vertical Tabs Sidebar matching reference image)
    tabs.set_position("left")
    assert tabs.is_vertical
    assert not tabs._v_scroll.isHidden()
    assert tabs._h_tab_bar.isHidden()
    assert len(tabs.vertical_rows) == 3

    row1 = tabs.vertical_rows[1]
    assert isinstance(row1, VerticalTabRow)
    assert "Documentation" in row1.title
    assert not row1.is_active

    # Change active tab
    current_changes = []
    tabs.currentChanged.connect(lambda i: current_changes.append(i))

    tabs.setCurrentIndex(1)
    assert tabs.currentIndex() == 1
    assert tabs.vertical_rows[1].is_active
    assert not tabs.vertical_rows[0].is_active
    assert 1 in current_changes

    # Test close signal on vertical tab row
    close_requested = []
    tabs.tabCloseRequested.connect(lambda i: close_requested.append(i))
    tabs._on_vertical_tab_close(1)
    assert 1 in close_requested

    # Test removing tab
    tabs.removeTab(1)
    assert tabs.count() == 2
    assert len(tabs.vertical_rows) == 2
    assert "GitHub Issues" in tabs.tabText(1)

    # Test switching back to "bottom" (Horizontal mode)
    tabs.set_position("bottom")
    assert not tabs.is_vertical
    assert not tabs._h_tab_bar.isHidden()
    assert tabs._v_scroll.isHidden()

    # Test switching to "right" (Vertical mode on right side)
    tabs.set_position("right")
    assert tabs.is_vertical
    assert not tabs._v_scroll.isHidden()
    assert tabs._h_tab_bar.isHidden()

    # Test WA_TransparentForMouseEvents on title and favicon so tab rows are 100% clickable
    from PySide6.QtCore import Qt
    assert tabs.vertical_rows[0].title_lbl.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert tabs.vertical_rows[0].fav_lbl.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    # Test new tab button emits newTabRequested
    new_tab_calls = []
    tabs.newTabRequested.connect(lambda: new_tab_calls.append(True))
    tabs._v_add_btn.click()
    assert len(new_tab_calls) == 1

    # Switch back to "top" and verify clean state
    tabs.set_position("top")
    assert not tabs.is_vertical
    assert not tabs._h_tab_bar.isHidden()
    assert tabs._v_scroll.isHidden()


def test_single_command_browser_launch_in_cli_and_app():
    """Verify that browser launches immediately on attempt 1 without needing two inputs."""
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.host import launcher

    app = CCTApp.__new__(CCTApp)
    notes = []
    app._system_note = lambda msg, role="system": notes.append((msg, role))
    browser_calls = []
    app.action_toggle_browser = lambda start_url="": browser_calls.append(start_url)

    # 1. Test slashless command in _handle_command
    app._handle_command("browser")
    assert len(browser_calls) == 1
    assert browser_calls[-1] == "about:home"

    app._handle_command("cat browser")
    assert len(browser_calls) == 2
    assert browser_calls[-1] == "about:home"

    app._handle_command("browse")
    assert len(browser_calls) == 3
    assert browser_calls[-1] == "about:home"

    # 2. Test slash commands
    app._handle_command("/browser")
    assert len(browser_calls) == 4
    assert browser_calls[-1] == "about:home"

    app._handle_command("/browse")
    assert len(browser_calls) == 5
    assert browser_calls[-1] == "about:home"


def test_action_toggle_browser_never_blocked_by_html_preview(tmp_path):
    """
    Verify that action_toggle_browser does NOT get trapped or do an early return
    when an HTML file is open; it converts the file to a file:// URL and launches
    the browser directly on attempt 1.
    """
    from calc_terminal.ui.app import CCTApp
    from calc_terminal.host import launcher

    app = CCTApp.__new__(CCTApp)
    notes = []
    app._system_note = lambda msg, role="system": notes.append((msg, role))
    app.repl = None

    html_file = tmp_path / "index.html"
    html_file.write_text("<h1>Hello World</h1>", encoding="utf-8")

    app._workspace_shell = MagicMock()
    mock_editor = MagicMock()
    mock_area = MagicMock()
    mock_area.path = str(html_file)
    mock_editor.active_text_area.return_value = mock_area
    app._workspace_shell.editor = mock_editor
    app._workspace_root = tmp_path

    launched = []
    with patch("calc_terminal.host.launcher.launch_cat_host", side_effect=lambda **kwargs: launched.append(kwargs) or 0):
        with patch("calc_terminal.host.launcher.can_launch_host", return_value=True):
            app.action_toggle_browser("")

    assert len(launched) == 1
    call = launched[0]
    assert call["start_mode"] == "browser"
    assert "file:///" in call["start_browser_url"].lower()
    assert "index.html" in call["start_browser_url"].lower()
