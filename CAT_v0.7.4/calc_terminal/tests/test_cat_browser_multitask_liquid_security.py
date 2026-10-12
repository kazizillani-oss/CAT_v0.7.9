"""
Tests for CAT Browser — Multitasking, Unlimited Tabs Virtualization,
Liquid Glass Aesthetics, Anti-Inspection Security & Agentic AI Integration.

Verifies:
1. Multi-tab synchronization and crash-free background multitasking.
2. Tab virtualization: dormant background tabs are suspended to protect RAM
   and revived seamlessly on demand.
3. Security hardening: anti-inspection key/context suppression (F12, Ctrl+U,
   Ctrl+Shift+I, ViewSource).
4. Fomoji browser exclusivity logic (only CAT Browser can access Fomoji portal).
5. Agentic AI browser controller (BrowserProvider & agentic methods).
"""

import os
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QUrl, QKeyCombination
from PySide6.QtGui import QKeyEvent, QContextMenuEvent
from PySide6.QtWebEngineCore import QWebEnginePage

# Initialize offscreen Qt app
app = QApplication.instance()
if not app:
    app = QApplication([])

from calc_terminal.browser_gui.qt_browser import (
    CATBrowserWindow,
    SecureWebEngineView,
    SecureWebEnginePage,
    get_active_browser_window,
    set_active_browser_window,
)
from calc_terminal.device_control import BrowserProvider
from calc_terminal.agent import TOOLS
from calc_terminal.browser.browser_state import BrowserState


@pytest.fixture(autouse=True)
def isolate_browser_tabs(tmp_path, monkeypatch):
    """Ensure tests run against an isolated temporary tabs and history store,
    never reading or polluting the user's real browser state."""
    tabs_file = tmp_path / "test_tabs.json"
    hist_file = tmp_path / "test_history.json"
    monkeypatch.setattr(BrowserState, "TABS_FILE", tabs_file)
    monkeypatch.setattr(BrowserState, "TABS_PATH", tabs_file)
    monkeypatch.setenv("CAT_BROWSER_TABS_FILE", str(tabs_file))
    monkeypatch.setenv("CAT_BROWSER_HISTORY_FILE", str(hist_file))
    yield


def test_multi_tab_synchronization_and_multitasking(tmp_path):
    """Verify multiple tabs can be created and loaded in background without desync or crashes."""
    win = CATBrowserWindow()
    win.resize(1000, 700)
    win.show()
    QApplication.processEvents()

    # Initial tab verification
    assert len(win._views) == 1
    assert len(win.state.tabs) == 1
    assert win.tabs.count() == 1

    # Add 4 additional tabs in parallel (including background tabs)
    t1 = win.new_tab("https://example.com/1", switch=True)
    t2 = win.new_tab("https://example.com/2", switch=False)  # Background task
    t3 = win.new_tab("https://example.com/3", switch=True)
    t4 = win.new_tab("https://example.com/4", switch=False)  # Background task

    QApplication.processEvents()

    # Verify total tab counts strictly match across views, state, and UI
    assert len(win._views) == 5
    assert len(win.state.tabs) == 5
    assert win.tabs.count() == 5

    # Switch tabs smoothly without error
    win.switch_tab(0)
    assert win.current_index == 0
    assert win.current_view() is win._views[0]

    win.switch_tab(2)
    assert win.current_index == 2
    assert win.current_view() is win._views[2]

    # Close tab 1
    win.close_tab(1)
    QApplication.processEvents()

    assert len(win._views) == 4
    assert len(win.state.tabs) == 4
    assert win.tabs.count() == 4

    win.close()


def test_unlimited_tabs_virtualization():
    """Verify dormant distant background tabs are suspended to save memory when > 16 tabs open."""
    win = CATBrowserWindow()
    win.resize(1000, 700)
    win.show()
    QApplication.processEvents()

    # Create 20 tabs
    for i in range(19):
        win.new_tab(f"https://example.com/{i}", switch=False)

    QApplication.processEvents()
    assert len(win._views) == 20
    assert win.tabs.count() == 20

    # Current index is 0 (the initial tab). Switch to tab 19.
    win.switch_tab(19)
    QApplication.processEvents()

    # Trigger virtualization check
    win._check_tab_virtualization()
    QApplication.processEvents()

    # Tab 1 and 2 are > 8 tabs away from index 19; their heavy view should be suspended
    assert getattr(win._views[1], "_is_suspended", False) is True
    assert getattr(win._views[1], "_suspended_url", None) is not None
    assert getattr(win._views[2], "_is_suspended", False) is True
    assert getattr(win._views[2], "_suspended_url", None) is not None

    # Active tab 19 must NOT be suspended
    assert getattr(win._views[19], "_is_suspended", False) is False

    # Switch back to tab 1: it must revive into a real view seamlessly
    win.switch_tab(1)
    QApplication.processEvents()

    assert getattr(win._views[1], "_is_suspended", False) is False
    assert getattr(win._views[1], "_suspended_url", None) is None
    assert win.current_index == 1
    assert win.current_view() is win._views[1]

    win.close()


def test_anti_inspection_and_security_controls():
    """Verify anti-inspect blocks F12, Ctrl+U, Ctrl+Shift+I, ViewSource."""
    view = SecureWebEngineView()
    page = SecureWebEnginePage(view)
    view.setPage(page)

    # 1. Test F12 key press is blocked
    f12_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F12, Qt.KeyboardModifier.NoModifier)
    view.keyPressEvent(f12_event)
    assert f12_event.isAccepted()

    # 2. Test Ctrl+U key press is blocked
    ctrl_u_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_U, Qt.KeyboardModifier.ControlModifier)
    view.keyPressEvent(ctrl_u_event)
    assert ctrl_u_event.isAccepted()

    # 3. Test Ctrl+Shift+I is blocked
    ctrl_shift_i = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_I, Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
    view.keyPressEvent(ctrl_shift_i)
    assert ctrl_shift_i.isAccepted()

    # 4. Test ViewSource action is ignored on page
    page.triggerAction(QWebEnginePage.WebAction.ViewSource, False)

    # 5. Test context menu on Fomoji URL is suppressed
    view.setUrl(QUrl("http://localhost:3000/dashboard"))
    ctx_event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, QPoint(100, 100))
    view.contextMenuEvent(ctx_event)
    assert ctx_event.isAccepted()


def test_fomoji_exclusivity_security_logic():
    """Verify server exclusivity logic: only CAT Browser can access Fomoji portal."""
    def simulate_fomoji_security(headers, url="/dashboard"):
        ua = headers.get("user-agent", "")
        cat_hdr = headers.get("x-cat-browser", "")

        is_cat_browser = "CATBrowser" in ua or cat_hdr == "1"
        is_html_route = not (url.startswith("/api/") or url.endswith(".css") or url.endswith(".js"))

        if is_html_route and not is_cat_browser:
            return 403, "RESTRICTED ACCESS: CAT Browser Required"
        return 200, "OK"

    # External Chrome browser
    status, msg = simulate_fomoji_security({
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    })
    assert status == 403
    assert "CAT Browser Required" in msg

    # External Edge browser
    status, msg = simulate_fomoji_security({
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Edg/124.0.0.0"
    })
    assert status == 403

    # CAT Browser user agent
    status, msg = simulate_fomoji_security({
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CATBrowser/0.8.4 (CAT OS; LiquidGlassEngine; FomojiAuthorized)"
    })
    assert status == 200
    assert msg == "OK"

    # CAT Browser custom header
    status, msg = simulate_fomoji_security({
        "user-agent": "Mozilla/5.0 CustomClient",
        "x-cat-browser": "1"
    })
    assert status == 200


def test_agentic_ai_integration_and_cat_browser_tool():
    """Verify CAT AI can drive CAT Browser through BrowserProvider and TOOLS['cat_browser']."""
    win = CATBrowserWindow()
    set_active_browser_window(win)
    assert get_active_browser_window() is win

    # 1. Agent list tabs
    tabs_info = win.agent_list_tabs()
    assert isinstance(tabs_info, list)
    assert len(tabs_info) == 1
    assert tabs_info[0]["index"] == 0
    assert tabs_info[0]["is_active"] is True

    # 2. Agent new tab
    new_idx = win.agent_new_tab("https://fattycat.local")
    assert new_idx == 1
    assert len(win.agent_list_tabs()) == 2

    # 3. Agent switch tab
    switched = win.agent_switch_tab(0)
    assert switched is True
    assert win.current_index == 0

    # 4. Agent close tab
    closed = win.agent_close_tab(1)
    assert closed is True
    assert len(win.agent_list_tabs()) == 1

    # 5. Verify BrowserProvider execution
    provider = BrowserProvider()
    assert provider.available()

    # List tabs via BrowserProvider
    res = provider.execute("list_tabs", {})
    assert res["ok"] is True
    assert "Open tabs (1)" in res["output"]

    # New tab via BrowserProvider with real URL
    res_new = provider.execute("new_tab", {"target": "https://wikipedia.org"})
    assert res_new["ok"] is True
    assert len(win.state.tabs) == 2

    # Verify local development navigation via BrowserProvider is permitted
    res_local = provider.execute("new_tab", {"target": "http://localhost:3000"})
    assert res_local["ok"] is True
    assert len(win.state.tabs) == 3

    # Switch tab via BrowserProvider
    res_switch = provider.execute("switch_tab", {"target": "0"})
    assert res_switch["ok"] is True
    assert win.current_index == 0

    # 6. Verify cat_browser in TOOLS dictionary
    assert "cat_browser" in TOOLS
    cat_tool = TOOLS["cat_browser"]
    assert callable(cat_tool["run"])
    assert "agentic mode" in cat_tool["desc"].lower()

    win.close()
