"""
CAT Customization Extension — UI, DOM Manipulation, and Lifecycle Integration Tests.

Verifies:
  1. WorkspaceShell DOM layout manipulation (sidebar, chat, editor positioning & sizing)
  2. Panel visibility and space release
  3. Header customization (height, logo visibility, overall visibility)
  4. Main Menu custom ordering and item visibility
  5. Button shape and size styling classes on Screen
  6. Layout profile application (Development, Research, Writing, Minimal, Full Screen)
  7. Reset actions (reset layout, styles, reset all)
  8. Extension lifecycle end-to-end (Not Installed -> Installed -> Enabled -> Disabled -> Uninstalled)
  9. Safe fallback and error recovery
"""

import asyncio
import os
import sys
import tempfile
import shutil
import pathlib
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from textual.app import App
from textual.widgets import Static, Button, Input
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.header import BrandHeader, Logo, get_nav_items
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui import theme_css
from calc_terminal import customization as cust
from calc_terminal import extensions as ext
from calc_terminal import config as cct_config


class WorkspaceTestApp(App):
    """Headless test application hosting WorkspaceShell and BrandHeader."""
    CSS = CCTApp.CSS

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.brand_header = None
        self._workspace_shell = None

    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v

    def compose(self):
        self.brand_header = BrandHeader()
        yield self.brand_header
        self._workspace_shell = WorkspaceShell(Static("Chat Stream View", id="chat-stream-mock"))
        yield self._workspace_shell


class TestCustomizationUI(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cct_cust_ui_test_")
        self._orig_home = os.environ.get("HOME")
        self._orig_up = os.environ.get("USERPROFILE")
        os.environ["HOME"] = self.tmp
        os.environ["USERPROFILE"] = self.tmp

        # Point registry and customization paths to temp
        ext.REGISTRY_FILE = pathlib.Path(self.tmp) / ".cct_extensions_registry.json"
        cust.CONFIG_PATH = pathlib.Path(self.tmp) / ".cct_customization.json"
        ext._cached_state = None
        ext._cached_mtime = 0
        cust._manager_instance = None

        # Start clean
        ext._load_registry()
        # Install and enable customization extension for UI tests
        ext.install("customization")
        ext.enable("customization")

    def tearDown(self):
        if self._orig_home is None:
            os.environ.pop("HOME", None)
        else:
            os.environ["HOME"] = self._orig_home
        if self._orig_up is None:
            os.environ.pop("USERPROFILE", None)
        else:
            os.environ["USERPROFILE"] = self._orig_up
        shutil.rmtree(self.tmp, ignore_errors=True)
        ext._cached_state = None
        ext._cached_mtime = 0
        cust._manager_instance = None

    def test_01_workspace_sidebar_right_position(self):
        """Moving sidebar to right repositions explorer after workspace main."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test() as pilot:
                shell = app.query_one(WorkspaceShell)
                mgr = cust.get_manager()
                
                # Apply sidebar right
                mgr.set_position("sidebar", "right")
                shell.apply_custom_layout()

                # In right position, #cct-workspace-main must precede explorer in children
                children_ids = [c.id for c in shell.children]
                self.assertIn("cct-sidebar", children_ids)
                self.assertIn("cct-workspace-main", children_ids)
                main_idx = children_ids.index("cct-workspace-main")
                sb_idx = children_ids.index("cct-sidebar")
                self.assertLess(main_idx, sb_idx, "Workspace main should be before sidebar when position=right")
        asyncio.run(run())

    def test_02_workspace_sidebar_left_position(self):
        """Moving sidebar back to left repositions explorer before workspace main."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test() as pilot:
                shell = app.query_one(WorkspaceShell)
                mgr = cust.get_manager()
                
                # Set to right then left
                mgr.set_position("sidebar", "right")
                shell.apply_custom_layout()
                mgr.set_position("sidebar", "left")
                shell.apply_custom_layout()

                children_ids = [c.id for c in shell.children]
                main_idx = children_ids.index("cct-workspace-main")
                sb_idx = children_ids.index("cct-sidebar")
                self.assertLess(sb_idx, main_idx, "Sidebar should be before workspace main when position=left")
        asyncio.run(run())

    def test_03_workspace_sidebar_visibility_releases_space(self):
        """Hiding sidebar hides the explorer and its resize handle to release space."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test() as pilot:
                shell = app.query_one(WorkspaceShell)
                mgr = cust.get_manager()
                
                # Show sidebar
                mgr.set_visibility("sidebar", True)
                shell.apply_custom_layout()
                self.assertTrue(shell.explorer.display)

                # Hide sidebar
                mgr.set_visibility("sidebar", False)
                shell.apply_custom_layout()
                self.assertFalse(shell.explorer.display, "Explorer must be display=False when hidden")
        asyncio.run(run())

    def test_04_chat_and_editor_swap_positions(self):
        """Setting chat to right and editor to left swaps their order in workspace body."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test() as pilot:
                shell = app.query_one(WorkspaceShell)
                body = shell.query_one("#cct-workspace-body")
                mgr = cust.get_manager()

                # Default: chat col on left, right pane on right
                shell.apply_custom_layout()
                children_ids = [c.id for c in body.children]
                self.assertEqual(children_ids[0], "cct-chat-col")

                # Swap: Chat right, Editor left
                mgr.set_position("chat", "right")
                mgr.set_position("editor", "left")
                shell.apply_custom_layout()

                swapped_ids = [c.id for c in body.children]
                self.assertEqual(swapped_ids[0], "cct-right-pane", "Right pane (editor) should be first when position=left")
        asyncio.run(run())

    def test_05_editor_visibility_releases_space(self):
        """Hiding editor sets right_pane display to False, releasing full width to chat."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test() as pilot:
                shell = app.query_one(WorkspaceShell)
                mgr = cust.get_manager()

                mgr.set_visibility("editor", False)
                shell.apply_custom_layout()
                self.assertFalse(shell.right_pane.display, "Right pane must be display=False when editor is hidden")
        asyncio.run(run())

    def test_06_header_customization(self):
        """Custom height, overall visibility, and logo visibility apply to BrandHeader."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test() as pilot:
                hdr = app.query_one(BrandHeader)
                mgr = cust.get_manager()

                # Custom height
                mgr.set_header({"height": 5, "visible": True, "logo_visible": True})
                hdr.apply_custom_header()
                self.assertEqual(hdr.styles.height.value, 5)

                # Hide logo
                mgr.set_header({"logo_visible": False})
                hdr.apply_custom_header()
                logo = hdr.query_one(Logo)
                self.assertFalse(logo.display)

                # Hide header entirely
                mgr.set_header({"visible": False})
                hdr.apply_custom_header()
                self.assertFalse(hdr.display)
        asyncio.run(run())

    def test_07_main_menu_reordering_and_filtering(self):
        """Main menu custom ordering and item visibility are reflected in get_nav_items()."""
        mgr = cust.get_manager()

        # Hide 'themes' from main menu
        mgr.set_main_menu({
            "visibility": {"themes": False, "mcp_servers": True},
            "order": ["extensions", "chats", "open_folder"]
        })
        items = get_nav_items()
        item_actions = [it[0] for it in items]

        # 'themes' should not be present in top selectable items
        self.assertNotIn("themes", item_actions)
        # Order should prioritize 'extensions', then 'chats', then 'open_folder'
        self.assertIn("extensions", item_actions)
        self.assertIn("chats", item_actions)
        ext_idx = item_actions.index("extensions")
        chats_idx = item_actions.index("chats")
        self.assertLess(ext_idx, chats_idx)

    def test_08_button_shape_and_size_classes(self):
        """Changing button shape and size dynamically updates Screen CSS classes."""
        app = CCTApp(mock.MagicMock(), [], mock.MagicMock())
        # Mock app screen
        screen = mock.MagicMock()
        screen.classes = set()
        def _add_class(c): screen.classes.add(c)
        def _remove_class(c): screen.classes.discard(c)
        screen.add_class = _add_class
        screen.remove_class = _remove_class
        app._screen = screen

        mgr = cust.get_manager()
        mgr.set_button_style({"shape": "pill", "size": "large"})
        
        with mock.patch.object(CCTApp, "screen", new_callable=mock.PropertyMock) as mock_scr:
            mock_scr.return_value = screen
            app._apply_customization_layout()

        self.assertIn("cust-btn-shape-pill", screen.classes)
        self.assertIn("cust-btn-size-large", screen.classes)

        # Switch to square and small
        mgr.set_button_style({"shape": "square", "size": "small"})
        with mock.patch.object(CCTApp, "screen", new_callable=mock.PropertyMock) as mock_scr:
            mock_scr.return_value = screen
            app._apply_customization_layout()

        self.assertNotIn("cust-btn-shape-pill", screen.classes)
        self.assertIn("cust-btn-shape-square", screen.classes)
        self.assertIn("cust-btn-size-small", screen.classes)

    def test_09_layout_profiles_application(self):
        """Built-in layout profiles apply cleanly to workspace."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test() as pilot:
                shell = app.query_one(WorkspaceShell)
                mgr = cust.get_manager()

                for profile_name in ["Development", "Research", "Writing", "Minimal", "Full Screen"]:
                    applied = mgr.apply_profile(profile_name)
                    self.assertTrue(applied, f"Failed to apply profile {profile_name}")
                    # apply to workspace
                    shell.apply_custom_layout()
                    # Verify no crash and basic sanity
                    self.assertIsNotNone(shell.children)
        asyncio.run(run())

    def test_10_reset_controls(self):
        """Reset controls restore default settings and persist safely."""
        mgr = cust.get_manager()
        mgr.set_position("sidebar", "right")
        mgr.set_button_style({"shape": "pill"})

        # Reset pane positions
        mgr.reset_pane_positions()
        self.assertEqual(mgr.get_position("sidebar"), "left")

        # Reset button styles
        mgr.reset_button_styles()
        self.assertEqual(mgr.get_styles().get("buttons", {}).get("shape"), "rounded")

        # Mutate and reset everything
        mgr.set_position("sidebar", "right")
        mgr.reset_all()
        self.assertEqual(mgr.get_position("sidebar"), "left")
        self.assertEqual(mgr.get_styles().get("buttons", {}).get("shape"), "rounded")

    def test_11_extension_lifecycle_and_ui_fallback(self):
        """When extension is disabled or uninstalled, UI immediately falls back to core defaults."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test() as pilot:
                shell = app.query_one(WorkspaceShell)
                body = shell.query_one("#cct-workspace-body")
                mgr = cust.get_manager()

                # Put sidebar on right and swap chat
                mgr.set_position("sidebar", "right")
                mgr.set_position("chat", "right")
                mgr.set_position("editor", "left")
                shell.apply_custom_layout()

                # Disable extension
                ext.disable("customization")
                self.assertFalse(cust.is_active())

                # Apply layout should restore defaults
                shell.apply_custom_layout()
                children_ids = [c.id for c in shell.children]
                body_ids = [c.id for c in body.children]
                self.assertEqual(children_ids[0], "cct-sidebar", "Disabled extension must restore sidebar to left")
                self.assertEqual(body_ids[0], "cct-chat-col", "Disabled extension must restore chat col to left")

                # Re-enable extension
                ext.enable("customization")
                self.assertTrue(cust.is_active())
                shell.apply_custom_layout()
                children_ids2 = [c.id for c in shell.children]
                self.assertEqual(children_ids2[-2], "cct-sidebar", "Re-enabled extension must restore custom sidebar position")

                # Uninstall extension
                ext.uninstall("customization")
                self.assertFalse(cust.is_active())
                shell.apply_custom_layout()
                children_ids3 = [c.id for c in shell.children]
                self.assertEqual(children_ids3[0], "cct-sidebar", "Uninstalled extension must restore core defaults")
                
                # Verify configuration file is preserved on disk
                self.assertTrue(cust.CONFIG_PATH.exists(), "User customization file must be preserved on uninstall")
        asyncio.run(run())

    def test_12_permission_mode_pill_no_bottom_clipping(self):
        """Permission mode pill must render with both top and bottom rounded borders intact."""
        import re
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test(size=(80, 20)) as pilot:
                await pilot.pause()
                hdr = app.query_one(BrandHeader)
                self.assertGreaterEqual(hdr.styles.height.value, 4, "Header height must be at least 4 to avoid clipping pill border")
                shot = pilot.app.export_screenshot()
                texts = re.findall(r'<text[^>]*>([^<]+)</text>', shot)
                # Verify top corner and bottom corner are both rendered
                has_top_corner = any('╭' in t for t in texts)
                has_bottom_corner = any('╰' in t for t in texts)
                self.assertTrue(has_top_corner, "Top rounded corner must be rendered")
                self.assertTrue(has_bottom_corner, "Bottom rounded corner must not be clipped by border-bottom")
        asyncio.run(run())

    def test_13_customization_panel_all_sections_mount_without_errors(self):
        """CustomizationPanel must mount and navigate through every section without error or Select crash."""
        from calc_terminal.ui.customization_panel import CustomizationPanel, _NAV_SECTIONS, _Preview
        from textual.widgets import Select, Button
        async def run():
            ext.enable("customization")
            app = WorkspaceTestApp()
            async with app.run_test(size=(120, 36)) as pilot:
                panel = CustomizationPanel()
                await app.push_screen(panel)
                await pilot.pause(0.1)

                # Verify overview preview is deduplicated
                preview = panel.query_one(_Preview)
                preview_text = str(preview.render())
                self.assertIn("HEADER", preview_text)
                self.assertIn("SIDEBAR", preview_text)
                self.assertIn("CHAT", preview_text)
                self.assertIn("EDITOR", preview_text)
                # Count occurrences of EDITOR in diagram — must appear only once, not twice
                self.assertEqual(preview_text.count("EDITOR"), 1, "EDITOR must not be duplicated in preview schematic")

                # Verify panel selection buttons in overview
                overview_btn_ids = [b.id for b in panel.query_one("#cust-content").query(Button)]
                self.assertIn("cust-sel-sidebar", overview_btn_ids)
                self.assertIn("cust-sel-chat", overview_btn_ids)
                self.assertIn("cust-sel-code_editor", overview_btn_ids)
                self.assertIn("cust-sel-terminal", overview_btn_ids)
                self.assertNotIn("cust-sel-file_explorer", overview_btn_ids, "File explorer alias must not be duplicated as separate button")

                # Navigate all sections and assert zero crashes / exceptions
                all_keys = [k for sec, items in _NAV_SECTIONS for k, l in items]
                for key in all_keys:
                    panel._set_nav(key)
                    await pilot.pause(0.05)
                    c = panel.query_one("#cust-content")
                    for s in c.query(Static):
                        txt = str(getattr(s, "_renderable", ""))
                        self.assertNotIn("Error:", txt, f"Section '{key}' must not display error: {txt}")

                # Specifically inspect Spacing section Select widget
                panel._set_nav("spacing")
                await pilot.pause(0.05)
                border_sel = panel.query_one("#cust-border-style", Select)
                self.assertIsNotNone(border_sel)
                self.assertEqual(border_sel.value, "solid", "Initial border style must be 'solid'")
                # Verify options values are lowercase strings
                opt_values = [v for _, v in border_sel._options]
                self.assertIn("solid", opt_values)
                self.assertIn("round", opt_values)
                self.assertIn("heavy", opt_values)
                self.assertIn("none", opt_values)

                # Test close button
                close_btn = panel.query_one("#cust-close3", Button)
                close_btn.press()
                await pilot.pause(0.05)
                self.assertFalse(app.screen is panel, "Panel must be dismissed upon clicking close")
        asyncio.run(run())

    def test_14_pill_and_narrow_buttons_render_safely(self):
        """Verify button rendering at small widths with borders (pill, rounded, square) never crashes divide_line / chop_cells."""
        from calc_terminal.ui.customization_panel import CustomizationPanel
        from textual.widgets import Button
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test(size=(88, 30)) as pilot:
                panel = CustomizationPanel()
                app.push_screen(panel)
                await pilot.pause(0.05)
                panel._set_nav("buttons")
                await pilot.pause(0.05)

                # Set shape to pill and test line rendering of every button
                pill_btn = panel.query_one("#cust-btn-shape-pill", Button)
                pill_btn.press()
                await pilot.pause(0.05)

                for b in panel.query(Button):
                    strips = b.render_lines(b.region)
                    self.assertGreater(len(strips), 0, f"Button {b.id} must render strips without crashing")

                # Test pathological narrow button: width=8, border=round, padding=(0,2)
                # This was the exact configuration that triggered rich.cells.chop_cells range() arg 3 error
                narrow_btn = Button("Pill", id="pathological-narrow-test")
                narrow_btn.styles.width = 8
                narrow_btn.styles.min_width = 8
                narrow_btn.styles.height = 3
                narrow_btn.styles.border = ("round", "#737aa2")
                narrow_btn.styles.padding = (0, 2)

                panel.mount(narrow_btn)
                await pilot.pause(0.05)
                strips = narrow_btn.render_lines(narrow_btn.region)
                self.assertGreater(len(strips), 0, "Pathological narrow button must render without error")

        asyncio.run(run())

    def test_15_code_editor_hidden_when_no_files_and_works_when_opened(self):
        """When customization is active, right pane is hidden if no files open, and works when opened."""
        async def run():
            app = WorkspaceTestApp()
            async with app.run_test(size=(100, 30)) as pilot:
                shell = app.query_one(WorkspaceShell)
                # Apply custom layout
                shell.apply_custom_layout()
                await pilot.pause(0.05)

                # No files open: right_pane MUST be display=False (no empty welcome editor shown)
                self.assertFalse(shell.right_pane.display, "Code editor right pane must not be shown when no files are open")

                # Now open a file in the editor
                test_file = os.path.join(self.tmp, "test_code.py")
                with open(test_file, "w", encoding="utf-8") as f:
                    f.write("print('hello world')\n")

                ok = shell.open_file(test_file)
                self.assertTrue(ok, "open_file must succeed")
                await pilot.pause(0.05)

                # Now right pane MUST be display=True and working
                self.assertTrue(shell.right_pane.display, "Code editor must be visible when file is opened")
                self.assertIn(test_file, shell.editor._open_paths)

                # Closing the tab should hide right pane again
                shell.editor.close_active()
                await pilot.pause(0.05)
                self.assertFalse(shell.right_pane.display, "Code editor must hide again when all files closed")

        asyncio.run(run())

    def test_16_personalize_center_save_from_non_personality_tab(self):
        """PersonalizeCenter properly saves tone, instructions, etc. even when on other tabs."""
        from calc_terminal.ui.personalize_center import PersonalizeCenter
        from calc_terminal import ai_personalization as ap
        # Install and enable personalize extension
        ext.install("personalize")
        ext.enable("personalize")
        ap.PROFILE_FILE = os.path.join(self.tmp, ".cct_profiles.json")
        ap.add_profile("TestProf", tone="balanced", additions="")
        ap.set_active("TestProf")

        async def run():
            app = WorkspaceTestApp()
            async with app.run_test(size=(100, 35)) as pilot:
                pc = PersonalizeCenter()
                app.push_screen(pc)
                await pilot.pause(0.05)

                # Switch to Tone tab
                pc._set_nav("tone")
                await pilot.pause(0.05)
                self.assertEqual(pc._nav_state, "tone")

                # Click playful tone
                tone_btn = pc.query_one("#pc-tone-playful", Button)
                tone_btn.press()
                await pilot.pause(0.05)

                # Switch to Custom Instructions tab
                pc._set_nav("instructions")
                await pilot.pause(0.05)

                # Set additions
                try:
                    ta = pc.query_one("#pc-additions-ta")
                    ta.text = "Always use metric units"
                except Exception:
                    inp = pc.query_one("#pc-additions", Input)
                    inp.value = "Always use metric units"
                await pilot.pause(0.05)

                # Click Save from instructions tab
                save_btn = pc.query_one("#pc-save", Button)
                save_btn.press()
                await pilot.pause(0.05)

                # Verify profile updated in storage
                profs = ap.profiles()
                saved_prof = next((p for p in profs if p.get("name") == "TestProf"), None)
                self.assertIsNotNone(saved_prof, "TestProf must be saved in storage")
                self.assertEqual(saved_prof.get("tone"), "playful", "Tone must be saved even though Save was clicked from instructions tab")
                self.assertIn("Always use metric units", saved_prof.get("additions", ""), "Additions must be saved")

        asyncio.run(run())

    def test_17_customization_panel_preview_click_no_crash_or_lag(self):
        """Clicking _Preview in CustomizationPanel cycles selection in-place without lag or NoneType.region crash."""
        from calc_terminal.ui.customization_panel import CustomizationPanel, _Preview
        from textual.widgets import Button, Static
        async def run():
            ext.enable("customization")
            app = WorkspaceTestApp()
            async with app.run_test(size=(120, 36)) as pilot:
                panel = CustomizationPanel()
                await app.push_screen(panel)
                await pilot.pause(0.1)

                # 1. Verify allow_select = False
                self.assertFalse(panel.allow_select, "CustomizationPanel.allow_select must be False")
                preview = panel.query_one(_Preview)
                self.assertFalse(preview.allow_select, "_Preview.allow_select must be False")

                preview_id_before = id(preview)

                # 2. Click preview directly via pilot
                await pilot.click(_Preview)
                await pilot.pause(0.05)

                # Preview widget must not be unmounted or recreated (same ID = in-place update)
                preview_after = panel.query_one(_Preview)
                self.assertEqual(id(preview_after), preview_id_before, "Preview widget must be updated in-place, not destroyed and recreated")

                # 3. Click one of the panel buttons, e.g. cust-sel-chat
                btn_chat = panel.query_one("#cust-sel-chat", Button)
                await pilot.click("#cust-sel-chat")
                await pilot.pause(0.05)

                self.assertEqual(panel._selected_panel, "chat")
                self.assertEqual(btn_chat.variant, "primary")

                # Hint should reflect the chat panel
                hint = panel.query_one(".cust-hint", Static)
                self.assertIn("chat", str(hint.render()))
        asyncio.run(run())

    def test_18_screen_forward_event_safeguard(self):
        """Screen._forward_event handles NoneType.region gracefully without propagating AttributeError."""
        from textual.screen import Screen
        from textual.events import MouseDown

        screen = Screen()
        event = MouseDown(None, 10, 10, 0, 0, 1, False, False, False)

        # Force inner call to trigger AttributeError("'NoneType' object has no attribute 'region'")
        with mock.patch("calc_terminal.ui.app._orig_screen_forward_event", side_effect=AttributeError("'NoneType' object has no attribute 'region'")):
            # Must not raise
            res = screen._forward_event(event)
            self.assertIsNone(res)


if __name__ == "__main__":
    unittest.main()


