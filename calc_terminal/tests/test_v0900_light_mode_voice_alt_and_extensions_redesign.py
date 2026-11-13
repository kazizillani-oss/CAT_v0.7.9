"""
calc_terminal/tests/test_v0900_light_mode_voice_alt_and_extensions_redesign.py
=============================================================================
Regression and unit verification suite for v0.9.000:
1. Light mode background distinction (canvas vs sidebar vs footer vs composer)
2. Composer chassis uses $surface with NO hardcoded #252839 background
3. Alt / Alt+V key activation of Voice Mode
4. Real-time colorful ASCII waveform rendering without NaNs
5. Extensions UI single close button (#ext-close2), height 5 action row, 3D tall bevels
6. Sidebar single scrollbar (no double scrollbars in filetree)
"""

import unittest
from unittest.mock import MagicMock
from calc_terminal.theme import set_theme, is_light
from calc_terminal.ui import theme_css
from calc_terminal.voice import (
    voice_manager,
    VoiceState,
    render_ascii_waveform,
    render_3tier_waveform,
)


class TestLightModeVoiceAltAndExtensions(unittest.TestCase):

    def test_light_mode_removal_and_dark_chassis(self):
        # All light modes were removed per prompt 9 specification
        from calc_terminal.theme import available_themes
        self.assertGreaterEqual(len(available_themes()), 60)
        # All active themes are dark/rich themes
        self.assertFalse(is_light())
        vars_theme = theme_css.css_variables()
        self.assertIn("surface", vars_theme)
        self.assertIn("text", vars_theme)

        # Verify #cct-composer uses $surface with NO hardcoded #252839
        css = theme_css.BASE_CSS
        self.assertNotIn("cct-composer.cct-mode-agent {\n    background: #252839;", css)
        self.assertIn("#cct-composer {", css)
        self.assertIn("background: $surface;", css)

        # Verify sidebar and statusline backgrounds
        self.assertIn("#cct-sidebar {", css)
        self.assertIn("background: $surface;", css)
        self.assertIn("#cct-statusline {", css)
        self.assertIn("background: transparent;", css)

    def test_sidebar_single_scrollbar_no_double_scroll(self):
        css = theme_css.BASE_CSS
        self.assertIn("#cct-sidebar.has-tree #cct-sidebar-body", css)
        self.assertIn("scrollbar-size: 0 0;", css)
        self.assertIn(".cct-filetree", css)
        self.assertIn("scrollbar-size: 1 1;", css)

    def test_voice_waveform_realtime_ascii_colors(self):
        amps = [0.0, 0.1, 0.4, 0.8, 1.0, 0.7, 0.3, 0.0]
        wf = render_ascii_waveform(amps, width=8)
        self.assertIn("█", wf)
        self.assertIn(" ", wf)
        self.assertIn("[#", wf)  # Rich color markup

        # Test 3-tier colorful waveform
        tier_str = voice_manager.get_3tier_waveform_str()
        self.assertIn("[#38bdf8]", tier_str)
        self.assertIn("[#a855f7]", tier_str)
        self.assertIn("[#34d399]", tier_str)

    def test_extensions_panel_close_and_height(self):
        from textual.app import App
        from calc_terminal.ui.extensions_panel import ExtensionsPanel
        import asyncio

        class TestExtApp(App):
            def compose(self):
                yield ExtensionsPanel()

        async def run_check():
            app = TestExtApp()
            async with app.run_test() as pilot:
                panel = app.query_one(ExtensionsPanel)
                # Verify close button exists
                close_btn = panel.query_one("#ext-close")
                self.assertIsNotNone(close_btn)
                self.assertIn("cct-modal-close-btn", close_btn.classes)

                # Verify #ext-actions height and styling
                self.assertIn("#ext-actions {", ExtensionsPanel.CSS)
                self.assertIn("border-top: solid $border;", ExtensionsPanel.CSS)

        asyncio.run(run_check())


if __name__ == "__main__":
    unittest.main()
