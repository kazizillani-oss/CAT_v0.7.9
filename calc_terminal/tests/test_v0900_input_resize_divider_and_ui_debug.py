"""
calc_terminal/tests/test_v0900_input_resize_divider_and_ui_debug.py
==================================================================
Tests for:
1. Composer horizontal divider inside input area (#cct-composer-divider).
2. Composer resizing robustness (no prompt row collapse / squashing at small or large sizes).
3. Bottom statusbar interactive tabs (○ UI, Theme, Tools, Experiments).
4. UI Diagnostics Modal (Loop, CPU, Memory sparklines, Debug overlay toggle).
5. Sidebar Debug Information HUD widget (#cct-sidebar-debug-info).
"""

import sys
import os
sys.path.insert(0, os.path.abspath("."))

import unittest
from unittest.mock import MagicMock
from textual.app import App
from textual.widgets import Static, Button

from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.composer import StickyComposer, ComposerInput
from calc_terminal.ui.statusbar import StatusBar, StatusFields, UIDiagnosticsModal, ToolsModal
from calc_terminal.ui.sidebar import Explorer, DebugInformationWidget
from calc_terminal.ui import theme_css, app as cct_app


class _HarnessTestApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS

    def __init__(self):
        super().__init__()
        self.debug_overlay_enabled = False
        self.status_fields = StatusFields(lambda: {"workspace": "test_ws", "model_label": "nvidia/nemotron"})

    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v

    def compose(self):
        yield Explorer()
        yield StickyComposer(model_label="nvidia/nemotron")
        yield StatusBar(self.status_fields)

    def toggle_debug_overlay(self):
        self.debug_overlay_enabled = not self.debug_overlay_enabled
        try:
            info = self.query_one("#cct-sidebar-debug-info")
            info.set_class(self.debug_overlay_enabled, "visible")
        except Exception:
            pass
        return self.debug_overlay_enabled


class TestInputResizeDividerAndUIDebug(unittest.IsolatedAsyncioTestCase):

    async def test_composer_internal_divider_exists(self):
        """Verify the restored horizontal divider #cct-composer-divider exists inside StickyComposer."""
        app = _HarnessTestApp()
        async with app.run_test(size=(100, 30)) as pilot:
            comp = app.query_one(StickyComposer)
            self.assertIsNotNone(comp)
            divider = comp.query_one("#cct-composer-divider", Static)
            self.assertIsNotNone(divider)

            # Ensure divider is between prompt row and footer
            children = list(comp.children)
            prompt_idx = children.index(comp.query_one("#cct-prompt-row"))
            divider_idx = children.index(divider)
            footer_idx = children.index(comp.query_one("#cct-bottom-row"))
            self.assertTrue(prompt_idx < divider_idx < footer_idx, "Divider must separate prompt row from footer")

    async def test_composer_resize_robustness(self):
        """Verify composer resize bounds prevent editor/prompt collapse."""
        app = _HarnessTestApp()
        async with app.run_test(size=(80, 24)) as pilot:
            comp = app.query_one(StickyComposer)
            editor = comp.query_one("#cct-input", ComposerInput)
            row = comp.query_one("#cct-prompt-row")

            # 1. Normal state: editor and row must have positive height
            self.assertGreaterEqual(row.region.height, 1)
            self.assertGreaterEqual(editor.region.height, 1)

            # 2. Resizing to explicit heights
            comp.set_explicit_height(12)
            await pilot.pause()
            self.assertEqual(comp._explicit_height, 12)
            self.assertGreaterEqual(row.region.height, 2)

            # 3. Resizing down to minimum bounds
            comp.set_explicit_height(5)
            await pilot.pause()
            # None or clamped to minimum
            self.assertIsNone(comp._explicit_height)
            self.assertGreaterEqual(row.region.height, 1)

            # 4. Extreme terminal resize should not crash or squash editor
            await pilot.resize_terminal(50, 15)
            await pilot.pause()
            self.assertGreaterEqual(row.region.height, 1)

    async def test_statusbar_tabs_and_ui_modal(self):
        """Verify statusbar has tabs, no experiments/workspace/model, and Tools tab opens ToolsModal."""
        app = _HarnessTestApp()
        async with app.run_test(size=(100, 30)) as pilot:
            statusbar = app.query_one(StatusBar)
            self.assertIsNotNone(statusbar)

            # Check buttons exist: UI and Tools. Theme and Experiments are removed!
            btn_ui = statusbar.query_one("#btn-status-ui", Button)
            btn_tools = statusbar.query_one("#btn-status-tools", Button)
            theme_buttons = list(statusbar.query("#btn-status-theme"))
            exp_buttons = list(statusbar.query("#btn-status-experiments"))
            self.assertIsNotNone(btn_ui)
            self.assertIsNotNone(btn_tools)
            self.assertEqual(len(theme_buttons), 0, "Theme button must be removed from footer tabs")
            self.assertEqual(len(exp_buttons), 0, "Experiments button must be removed from footer tabs")

            # Check StatusFields does NOT include Workspace, Model, GPU, API, Ollama in bottom status line
            fields = app.status_fields.fields()
            labels = [f[0] for f in fields]
            self.assertNotIn("Workspace", labels, "Workspace must be removed from bottom statusline")
            self.assertNotIn("Model", labels, "Model must be removed from bottom statusline")
            self.assertNotIn("GPU", labels, "GPU must be removed from bottom statusline")
            self.assertNotIn("API", labels, "API must be removed from bottom statusline")
            self.assertNotIn("Ollama", labels, "Ollama must be removed from bottom statusline")

            # Click ○ UI to open modal
            btn_ui.press()
            await pilot.pause()

            modal = app.screen
            self.assertIsInstance(modal, UIDiagnosticsModal)

            # Check modal metrics widgets
            loop_w = modal.query_one("#cct-uidiag-loop", Static)
            cpu_w = modal.query_one("#cct-uidiag-cpu", Static)
            mem_w = modal.query_one("#cct-uidiag-mem", Static)
            toggle_w = modal.query_one("#cct-uidiag-toggle", Button)
            self.assertIsNotNone(loop_w)
            self.assertIsNotNone(cpu_w)
            self.assertIsNotNone(mem_w)
            self.assertIsNotNone(toggle_w)

            # Toggle debug overlay via modal button
            self.assertFalse(app.debug_overlay_enabled)
            toggle_w.press()
            await pilot.pause()
            self.assertTrue(app.debug_overlay_enabled)

            # Dismiss modal via escape
            modal.action_dismiss_modal()
            await pilot.pause()
            self.assertNotIsInstance(app.screen, UIDiagnosticsModal)

            # Click Tools to open ToolsModal
            btn_tools.press()
            await pilot.pause()

            tools_modal = app.screen
            self.assertIsInstance(tools_modal, ToolsModal)
            snap_btn = tools_modal.query_one("#cct-tools-snapshot-btn", Button)
            ttfd_btn = tools_modal.query_one("#cct-tools-ttfd-btn", Button)
            token_btn = tools_modal.query_one("#cct-tools-token-btn", Button)
            verbose_btn = tools_modal.query_one("#cct-tools-verbose-btn", Button)
            self.assertIsNotNone(snap_btn)
            self.assertIsNotNone(ttfd_btn)
            self.assertIsNotNone(token_btn)
            self.assertIsNotNone(verbose_btn)

            # Toggle ttfd option
            self.assertFalse(tools_modal._ttfd)
            ttfd_btn.press()
            await pilot.pause()
            self.assertTrue(tools_modal._ttfd)

            # Write debug snapshot
            snap_btn.press()
            await pilot.pause()

            # Dismiss tools modal
            tools_modal.action_dismiss_modal()
            await pilot.pause()
            self.assertNotIsInstance(app.screen, ToolsModal)

    async def test_sidebar_debug_information_hud(self):
        """Verify sidebar debug information overlay displays when debug_overlay_enabled is True."""
        app = _HarnessTestApp()
        async with app.run_test(size=(100, 30)) as pilot:
            explorer = app.query_one(Explorer)
            debug_info = explorer.query_one("#cct-sidebar-debug-info", DebugInformationWidget)
            self.assertIsNotNone(debug_info)

            # Initially hidden
            self.assertFalse(debug_info.has_class("visible"))

            # Toggle on
            app.toggle_debug_overlay()
            debug_info.refresh_metrics()
            await pilot.pause()
            self.assertTrue(debug_info.has_class("visible"))

            # Check rendered text content contains HUD metrics
            text = str(debug_info.render())
            self.assertIn("Debug Information", text)
            self.assertIn("FPS:", text)
            self.assertIn("Frame:", text)
            self.assertIn("Cells:", text)
            self.assertIn("Memory:", text)

    async def test_explorer_and_input_area_coexist_never_hides_main_at_any_width(self):
        """Verify landscape mode keeps side-by-side coexistence, while portrait mode toggles full screen."""
        from calc_terminal.ui.workspace import WorkspaceShell
        from calc_terminal.ui.conversation import ConversationView

        class _WorkspaceHarnessApp(App):
            CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS

            def __init__(self):
                super().__init__()
                self.status_fields = StatusFields(lambda: {"workspace": "test_ws", "model_label": "nvidia/nemotron"})

            def get_css_variables(self):
                v = super().get_css_variables()
                v.update(theme_css.css_variables())
                return v

            def compose(self):
                yield WorkspaceShell(
                    ConversationView(),
                    composer=StickyComposer(model_label="nvidia/nemotron")
                )
                yield StatusBar(self.status_fields)

        # 1. Test Landscape mode (80x24, 120x35, 52x28): MUST co-exist side-by-side, NEVER full screen
        for width, height in [(52, 28), (80, 24), (120, 35)]:
            app = _WorkspaceHarnessApp()
            async with app.run_test(size=(width, height)) as pilot:
                shell = app.query_one(WorkspaceShell)
                main = shell.query_one("#cct-workspace-main")
                composer = shell.query_one("#cct-composer")
                self.assertFalse(shell.is_portrait())

                # Initial state check
                self.assertTrue(main.display, f"Main workspace must be displayed at {width}x{height}")
                self.assertIsNotNone(composer)
                self.assertNotEqual(composer.display, False, f"Composer must be visible at {width}x{height}")

                # Toggle explorer open in landscape
                shell.toggle_sidebar()
                await pilot.pause()

                # Landscape invariant: main and composer remain visible side-by-side, never 100% width
                self.assertTrue(main.display, f"Main workspace must remain visible after toggle at {width}x{height}")
                self.assertNotEqual(composer.display, False, f"Composer must remain visible after toggle at {width}x{height}")
                self.assertNotEqual(str(shell.explorer.styles.width), "100%", "Explorer must never take 100% width in landscape")

                # Verify clean statusbar (GPU/API/Ollama removed from left area)
                statusbar = app.query_one(StatusBar)
                statusbar.refresh_status()
                status_str = statusbar._last_rendered_text or ""
                self.assertNotIn("GPU", status_str)
                self.assertNotIn("API", status_str)
                self.assertNotIn("Ollama", status_str)

        # 2. Test Portrait mode (45x60): ONLY and ONLY in portrait mode, explorer is full screen
        app = _WorkspaceHarnessApp()
        async with app.run_test(size=(45, 60)) as pilot:
            shell = app.query_one(WorkspaceShell)
            main = shell.query_one("#cct-workspace-main")
            self.assertTrue(shell.is_portrait(), "45x60 must be recognized as portrait mode")

            # Inline expand buttons in chat MUST NOT be displayed in portrait mode
            nav = shell.query_one("#cct-chat-nav")
            exp_btn = shell.query_one("#cct-sidebar-expand-btn")
            self.assertFalse(nav.display, "Chat nav inline button must be hidden in portrait mode")
            self.assertFalse(exp_btn.display, "Sidebar expand button must be hidden in portrait mode")

            # Open explorer in portrait -> full screen
            shell.toggle_sidebar()
            await pilot.pause()
            self.assertIn(str(shell.explorer.styles.width), ("100%", "100w"), "Explorer must be 100% full screen in portrait mode")
            self.assertFalse(main.display, "Main area must be hidden when full-screen explorer is open in portrait mode")

            # Close explorer in portrait -> main is restored
            shell.toggle_sidebar()
            await pilot.pause()
            self.assertTrue(main.display, "Main area must be restored when explorer is closed in portrait mode")


if __name__ == "__main__":
    unittest.main()

