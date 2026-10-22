import json
import os
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from calc_terminal.host import diagnostics, lifecycle, supervisor
from calc_terminal.browser.browser_state import BrowserState


def test_diagnostics_redact_url_credentials_path_and_query():
    message = diagnostics._safe(
        "load https://alice:secret@example.test/oauth/callback?code=private&state=secret"
    )

    assert message == "load https://example.test/[redacted]"
    assert "secret" not in message
    assert "private" not in message


def test_embedded_view_finds_owning_pane_instead_of_top_level_window():
    class Node:
        def __init__(self, parent=None):
            self._parent = parent

        def parentWidget(self):
            return self._parent

    class Pane(Node):
        tab_bar = object()
        state = SimpleNamespace(tabs=[SimpleNamespace(id="tab-42")])

        def _view_index(self, view):
            return 0

    window = Node()
    pane = Pane(window)
    stack = Node(pane)
    view = Node(stack)

    assert lifecycle.find_tab_owner(view) is pane
    assert lifecycle.tab_id_for_view(pane, view) == "tab-42"


def test_closing_background_tab_keeps_same_active_tab():
    assert lifecycle.current_index_after_tab_close(1, 3, 4) == 2
    assert lifecycle.current_index_after_tab_close(3, 3, 4) == 3
    assert lifecycle.current_index_after_tab_close(3, 3, 0) == -1


def test_initial_browser_tab_reuses_placeholder_id(monkeypatch, tmp_path):
    tabs_path = tmp_path / "tabs.json"
    monkeypatch.setattr(BrowserState, "TABS_FILE", tabs_path)
    state = BrowserState()
    first_id = state.tabs[0].id

    first = state.new_tab("https://first.example")
    second = state.new_tab("https://second.example")

    assert len(state.tabs) == 2
    assert first.id == first_id
    assert second.id != first.id


def test_saved_tabs_are_marked_for_ui_restoration(monkeypatch, tmp_path):
    tabs_path = tmp_path / "tabs.json"
    monkeypatch.setattr(BrowserState, "TABS_FILE", tabs_path)
    original = BrowserState()
    original.new_tab("about:home")
    original.new_tab("https://second.example")

    restored = BrowserState()

    assert restored.session_restored is True
    assert [tab.url for tab in restored.tabs] == ["about:home", "https://second.example"]
    assert restored.active_tab_id == original.active_tab_id


def test_embedded_pane_restores_saved_ids_and_keeps_active_tab_when_closing_background(
    monkeypatch, tmp_path
):
    from PySide6.QtWidgets import QApplication
    from calc_terminal.host.desktop import EmbeddedBrowserPane

    tabs_path = tmp_path / "tabs.json"
    monkeypatch.setattr(BrowserState, "TABS_FILE", tabs_path)
    state = BrowserState()
    state.new_tab("about:home")
    state.new_tab("about:home")
    state.new_tab("about:home")
    saved_ids = [tab.id for tab in state.tabs]
    app = QApplication.instance() or QApplication([])

    pane = EmbeddedBrowserPane("about:home")
    pane._ensure_initial_tab()

    assert len(pane._views) == len(saved_ids) == 3
    assert [pane._tab_id_for_view(view) for view in pane._views] == saved_ids
    active_view = pane._views[2]
    assert pane.tab_bar.currentIndex() == 2

    pane._close_tab(0)

    assert pane.tab_bar.currentIndex() == 1
    assert pane._views[pane.tab_bar.currentIndex()] is active_view
    pane.close()
    app.processEvents()


def test_embedded_restore_defers_inactive_webengine_tabs_until_selected(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineWidgets import QWebEngineView
    from calc_terminal.host.desktop import EmbeddedBrowserPane

    tabs_path = tmp_path / "tabs.json"
    monkeypatch.setattr(BrowserState, "TABS_FILE", tabs_path)
    page_a = tmp_path / "a.html"
    page_b = tmp_path / "b.html"
    page_a.write_text("<title>A</title>", encoding="utf-8")
    page_b.write_text("<title>B</title>", encoding="utf-8")
    state = BrowserState()
    state.new_tab(page_a.as_uri())
    state.new_tab(page_b.as_uri())
    saved_ids = [tab.id for tab in state.tabs]
    app = QApplication.instance() or QApplication([])

    pane = EmbeddedBrowserPane("about:home")
    pane._ensure_initial_tab()

    assert len(pane._views) == 2
    assert getattr(pane._views[0], "_cat_deferred_url", None) == page_a.as_uri()
    assert isinstance(pane._views[1], QWebEngineView)
    assert [pane._tab_id_for_view(view) for view in pane._views] == saved_ids

    pane.tab_bar.setCurrentIndex(0)
    assert isinstance(pane._views[0], QWebEngineView)
    assert pane.viewport_stack.currentWidget() is pane._views[0]
    pane.close()
    app.processEvents()


def test_embedded_tab_switch_freezes_and_resumes_background_pages(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineCore import QWebEnginePage
    from calc_terminal.host.desktop import EmbeddedBrowserPane

    monkeypatch.setattr(BrowserState, "TABS_FILE", tmp_path / "tabs.json")
    app = QApplication.instance() or QApplication([])
    pane = EmbeddedBrowserPane("about:home")
    pane._ensure_initial_tab()
    web_view = pane._create_webengine_view()
    pane._views.append(web_view)
    pane.viewport_stack.addWidget(web_view)
    pane.tab_bar.addTab("○  Blank Web Tab")
    pane._rebuild_view_index()
    pane._low_end_mode = True

    pane.tab_bar.setCurrentIndex(1)
    app.processEvents()
    assert web_view.page().lifecycleState() == QWebEnginePage.LifecycleState.Active
    pane.tab_bar.setCurrentIndex(0)
    app.processEvents()
    assert web_view.page().lifecycleState() == QWebEnginePage.LifecycleState.Frozen
    assert web_view._cat_discard_timer.isActive()
    recommended_state = web_view.page().recommendedState()
    pane._discard_background_view(web_view)
    if recommended_state == QWebEnginePage.LifecycleState.Discarded:
        assert web_view.page().lifecycleState() == QWebEnginePage.LifecycleState.Discarded
    else:
        assert web_view.page().lifecycleState() == QWebEnginePage.LifecycleState.Frozen
    pane.tab_bar.setCurrentIndex(1)
    app.processEvents()
    assert web_view.page().lifecycleState() == QWebEnginePage.LifecycleState.Active
    pane.close()
    app.processEvents()


def test_embedded_renderer_failure_defers_background_tab_reload(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication
    from calc_terminal.host.desktop import EmbeddedBrowserPane

    monkeypatch.setattr(BrowserState, "TABS_FILE", tmp_path / "tabs.json")
    app = QApplication.instance() or QApplication([])
    page_file = tmp_path / "page.html"
    page_file.write_text("<title>test page</title>", encoding="utf-8")
    page_url = page_file.as_uri()
    pane = EmbeddedBrowserPane(page_url)
    pane._ensure_initial_tab()
    view = pane._views[0]
    page = view.page()
    page._last_committed_url = page_url
    pane.new_tab("about:home")

    page._on_render_process_terminated("simulated", 17)

    assert pane.tab_bar.currentIndex() == 1
    assert view._suspended_url == page_url
    assert getattr(view, "_pending_url", None) is None
    pane.close()
    app.processEvents()


def test_standalone_browser_keeps_active_view_when_closing_background_tab(
    monkeypatch, tmp_path
):
    from PySide6.QtWidgets import QApplication
    from calc_terminal.browser_gui.qt_browser import CATBrowserWindow, _NewTabWidget

    monkeypatch.setattr(BrowserState, "TABS_FILE", tmp_path / "tabs.json")
    app = QApplication.instance() or QApplication([])
    saved_state = BrowserState()
    saved_state.new_tab("about:home")
    saved_state.new_tab("about:home")
    saved_state.new_tab("about:home")
    saved_ids = [tab.id for tab in saved_state.tabs]

    window = CATBrowserWindow("about:home")
    active_view = window.current_view()

    assert [window.state.tabs[i].id for i in range(window.tab_bar.count())] == saved_ids
    assert window.tab_bar.currentIndex() == 2
    window._close_tab(0)

    assert window.tab_bar.currentIndex() == 1
    assert window.current_view() is active_view
    assert isinstance(active_view, _NewTabWidget)
    window.close()
    app.processEvents()


def test_native_crash_uses_one_compositor_fallback(monkeypatch, tmp_path):
    state_path = tmp_path / "fallback.json"
    log_path = tmp_path / "recovery.log"
    monkeypatch.setattr(supervisor, "_state_paths", lambda: (state_path, log_path))
    modes = []
    outcomes = iter((0xC0000005, 0))

    def run_child(_url, compatibility_compositing):
        modes.append(compatibility_compositing)
        return next(outcomes)

    monkeypatch.setattr(supervisor, "_run_child", run_child)

    assert supervisor.run_supervisor() == 0
    assert modes == [False, True]
    assert json.loads(state_path.read_text(encoding="utf-8"))["fallback_until"] > 0


def test_compatibility_crash_does_not_create_an_automatic_restart_loop(monkeypatch, tmp_path):
    state_path = tmp_path / "fallback.json"
    log_path = tmp_path / "recovery.log"
    state_path.write_text(
        json.dumps({"fallback_until": supervisor.time.time() + 60}), encoding="utf-8"
    )
    monkeypatch.setattr(supervisor, "_state_paths", lambda: (state_path, log_path))
    modes = []

    def run_child(_url, compatibility_compositing):
        modes.append(compatibility_compositing)
        return 0xC0000005

    monkeypatch.setattr(supervisor, "_run_child", run_child)

    assert supervisor.run_supervisor() == 0xC0000005
    assert modes == [True]


def test_supervisor_spawns_browser_child_with_popen_supported_options(monkeypatch):
    captured = {}

    class FakeProcess:
        pid = 12345

        def wait(self):
            return 0

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured.update(kwargs)
        return FakeProcess()

    monkeypatch.setattr(
        supervisor,
        "_browser_command",
        lambda url: (["python", "-m", "calc_terminal.host.launcher", "--url", url], {}, {}),
    )
    monkeypatch.setattr(supervisor.subprocess, "Popen", fake_popen)

    assert supervisor._run_child("about:home", compatibility_compositing=True) == 0
    assert captured["command"][-1] == "about:home"
    assert "check" not in captured
