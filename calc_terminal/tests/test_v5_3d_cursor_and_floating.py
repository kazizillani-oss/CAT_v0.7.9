import unittest
from unittest.mock import MagicMock, patch

class TestV53DCursorAndFloating(unittest.TestCase):
    def test_header_3d_bevels_in_app_css(self):
        """Verify .cct-menu-btn, .cct-perm-pill, and #cct-header-right have clean rounded borders (Image 5)."""
        from calc_terminal.ui.app import CCTApp
        css = CCTApp.CSS

        # Clean rounded keycap styles in landscape matching Image 5
        self.assertIn(".cct-menu-btn {", css)
        self.assertIn(".cct-perm-pill {", css)
        self.assertIn("#cct-header-right {", css)
        self.assertIn("border-top: tall #6b7596;", css)

    def test_palette_cursor_tracking_and_selection(self):
        """Verify CommandPalette select_index updates row markup and tracking."""
        from calc_terminal.ui.palette import CommandPalette
        palette = CommandPalette()
        palette._matches = [
            ("/help", "Show help & shortcuts"),
            ("/calculator", "Quick scientific calculator"),
            ("/solve", "Universal formula calculator"),
        ]

        # Initial selection at index 0
        palette._selected = 0
        markup_0 = palette._format_row_markup(0, 80, False)
        markup_2 = palette._format_row_markup(2, 80, False)
        self.assertTrue(markup_0.startswith("▶ "))
        self.assertTrue(markup_2.startswith("  "))

        # Select index 2 (simulating cursor move or click)
        palette._selected = 2
        markup_0_new = palette._format_row_markup(0, 80, False)
        markup_2_new = palette._format_row_markup(2, 80, False)
        self.assertTrue(markup_0_new.startswith("  "))
        self.assertTrue(markup_2_new.startswith("▶ "))

    def test_command_palette_subclass_item_coloring(self):
        """Verify command_palette.CommandPalette color mapping preserves cursor tracking."""
        from calc_terminal.ui.command_palette import CommandPalette as SubCommandPalette
        palette = SubCommandPalette()
        palette._matches = [
            ("/solve", "Solve numericals"),
            ("/formulas", "Browse formula library"),
        ]
        color_solve = palette._get_item_color("/solve", "#89b4fa")
        color_sim = palette._get_item_color("/formulas", "#89b4fa")
        self.assertNotEqual(color_solve, "")
        self.assertNotEqual(color_sim, "")

    def test_composer_height_docking_on_palette_state(self):
        """Verify StickyComposer pins editor to line count when palette opens."""
        from calc_terminal.ui.composer import StickyComposer
        composer = StickyComposer()
        
        # Mock subcomponents
        editor = MagicMock()
        editor.text = "> /"
        stack = MagicMock()
        row = MagicMock()
        
        def fake_query_one(sel, *args):
            if sel == "#cct-input":
                return editor
            elif sel == "#cct-editor-stack":
                return stack
            elif sel == "#cct-prompt-row":
                return row
            raise KeyError(sel)
        
        composer.query_one = fake_query_one
        
        # Palette opens
        composer._on_palette_state_changed(True)
        self.assertEqual(editor.styles.height, 1)
        self.assertEqual(stack.styles.height, 1)
        self.assertEqual(composer.styles.max_height.value, 42.0)

    def test_extensions_panel_redesign_tabs(self):
        """Verify removed filter tabs (Extensions, Skills, Commands, Integrations) (Image 6 & Image 8)."""
        from calc_terminal.ui.extensions_panel import ExtensionsPanel
        import inspect
        src = inspect.getsource(ExtensionsPanel.compose)
        self.assertNotIn('ext-filters', src)
        self.assertNotIn('filter-all', src)
        self.assertNotIn('filter-extension', src)
        self.assertNotIn('filter-skill', src)
        self.assertNotIn('filter-command', src)
        self.assertNotIn('filter-integration', src)

    def test_dashboard_floating_mode_removes_2_cards(self):
        """Verify dashboard on_resize hides recent projects and workspace in floating window."""
        from calc_terminal.ui.dashboard import WelcomeDashboard
        dash = WelcomeDashboard(["CAT"], "v0.8.9.01", "nvidia", 0)
        dash._art_markup = MagicMock(return_value="ART")

        # Mock elements
        mock_art = MagicMock()
        mock_ver = MagicMock()
        mock_tag = MagicMock()
        mock_ready = MagicMock()
        mock_suggest = MagicMock()
        mock_ai = MagicMock()
        mock_cols = MagicMock()
        mock_projects = MagicMock()
        mock_workspace = MagicMock()
        mock_notebooks = MagicMock()

        def fake_dash_query_one(sel, *args):
            m = {
                "#cct-empty-art": mock_art,
                "#cct-empty-version": mock_ver,
                "#cct-empty-tagline": mock_tag,
                "#cct-empty-ready": mock_ready,
                "#cct-empty-suggest": mock_suggest,
                "#cct-dash-ai-status": mock_ai,
                "#cct-dash-columns": mock_cols,
                "#cct-dash-col-projects": mock_projects,
                "#cct-dash-col-workspace": mock_workspace,
                "#cct-dash-col-notebooks": mock_notebooks,
            }
            if sel in m:
                return m[sel]
            return MagicMock()

        dash.query_one = fake_dash_query_one

        with patch.object(WelcomeDashboard, 'is_attached', new=True):
            # 1. Test floating mode (w=80, h=25 -> is_compact_floating=True, is_portrait=False)
            dash._get_viewport_size = MagicMock(return_value=(80, 25))
            dash.on_resize()
            self.assertFalse(mock_projects.display)
            self.assertFalse(mock_workspace.display)
            self.assertTrue(mock_notebooks.display)
            mock_cols.set_class.assert_any_call(True, "mode-floating-single")

            # 2. Test spacious landscape mode (w=120, h=40 -> is_compact_floating=False, is_portrait=False)
            dash._last_resize_w = None
            dash._get_viewport_size = MagicMock(return_value=(120, 40))
            dash.on_resize()
            self.assertTrue(mock_projects.display)
            self.assertTrue(mock_workspace.display)
            self.assertTrue(mock_notebooks.display)


if __name__ == "__main__":
    unittest.main()
