import unittest
import asyncio
from unittest import mock
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.nav_screens import (
    ThemesPanel, SettingsPanel, UserPanel, InfoPanel,
    ThemePreviewRequested, ThemePreviewEnded
)
from calc_terminal import theme

class TestNavScreensCenteringAndThemes(unittest.IsolatedAsyncioTestCase):
    async def test_screen_centering(self):
        app = CCTApp(mock.MagicMock(), [], mock.MagicMock())
        async with app.run_test(size=(120, 40)) as pilot:
            # Check ThemesPanel
            themes_panel = ThemesPanel("tokyo-night")
            await app.push_screen(themes_panel)
            await pilot.pause()
            box = themes_panel.query_one("#cct-navpanel-box")
            # Should be horizontally centered: (120 - 56) / 2 = 32
            self.assertEqual(box.region.x, 32)
            self.assertEqual(box.region.y, 5)
            self.assertEqual(themes_panel.styles.align_horizontal, "center")
            self.assertEqual(themes_panel.styles.align_vertical, "middle")
            themes_panel.dismiss(None)
            await pilot.pause()

            # Check SettingsPanel
            settings_panel = SettingsPanel(lambda: {})
            await app.push_screen(settings_panel)
            await pilot.pause()
            box = settings_panel.query_one("#cct-navpanel-box")
            self.assertEqual(box.region.x, 26)
            self.assertEqual(box.region.y, 5)
            self.assertEqual(settings_panel.styles.align_horizontal, "center")
            self.assertEqual(settings_panel.styles.align_vertical, "middle")
            settings_panel.dismiss(None)
            await pilot.pause()

            # Check UserPanel
            user_panel = UserPanel(lambda: {})
            await app.push_screen(user_panel)
            await pilot.pause(0.1)
            box = user_panel.query_one("#cct-navpanel-box")
            self.assertEqual(box.region.x, 26)
            self.assertEqual(box.region.y, 3)
            self.assertEqual(user_panel.styles.align_horizontal, "center")
            self.assertEqual(user_panel.styles.align_vertical, "middle")
            user_panel.dismiss(None)
            await pilot.pause()

    async def test_theme_preview_debouncing(self):
        app = CCTApp(mock.MagicMock(), [], mock.MagicMock())
        async with app.run_test(size=(120, 40)) as pilot:
            themes_panel = ThemesPanel("tokyo-night")
            await app.push_screen(themes_panel)
            await pilot.pause()

            # Rapidly fire theme previews
            app.on_theme_preview_requested(ThemePreviewRequested("dracula"))
            app.on_theme_preview_ended(ThemePreviewEnded())
            app.on_theme_preview_requested(ThemePreviewRequested("nord"))
            app.on_theme_preview_ended(ThemePreviewEnded())
            app.on_theme_preview_requested(ThemePreviewRequested("monokai"))

            # Before timers fire, monokai preview timer is scheduled
            self.assertIsNotNone(app._theme_preview_timer)
            # Wait for debounce timer (0.06s) to fire
            await pilot.pause(0.2)

            # The current active theme preview should be monokai without intermediate thrash
            self.assertEqual(theme.get_theme(), "monokai")

            # Now let preview end
            app.on_theme_preview_ended(ThemePreviewEnded())
            self.assertIsNotNone(app._theme_restore_timer)
            # Wait for restore timer (0.10s) to fire
            await pilot.pause(0.5)

            # Restores back to saved theme
            self.assertEqual(theme.get_theme(), "tokyo-night")
            themes_panel.dismiss(None)
            await pilot.pause(0.05)

if __name__ == "__main__":
    unittest.main()
