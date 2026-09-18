import unittest
from unittest.mock import MagicMock
from textual.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.permission_panel import Toggle3D, PermissionsSettingsPanel
from calc_terminal.ui.composer import StickyComposer


class TestPermissionsAndFooterUI(unittest.IsolatedAsyncioTestCase):
    async def test_permissions_and_footer_controls(self):
        app = CCTApp(MagicMock(), [], MagicMock())
        async with app.run_test() as pilot:
            await pilot.pause()
            if type(app.screen).__name__ == "WelcomeModal":
                app.pop_screen()
                await pilot.pause()
            composer = app.query_one(StickyComposer)
            self.assertIsNotNone(composer)
            
            # Check right controls
            right_controls = app.query_one("#cct-right-controls")
            self.assertIsNotNone(right_controls)
            
            btn_perm = app.query_one("#btn-permissions")
            btn_attach = app.query_one("#btn-attach")
            btn_send = app.query_one("#btn-send")
            self.assertIsNotNone(btn_perm)
            self.assertIsNotNone(btn_attach)
            self.assertIsNotNone(btn_send)
            
            # Check initial permission panel state
            panel = app.query_one(PermissionsSettingsPanel)
            self.assertIsNotNone(panel)
            self.assertFalse(panel.is_open, "Permissions panel should initially be closed")
            
            orig_max_h = composer.styles.max_height.value
            
            # Test opening permissions panel via button
            btn_perm.press()
            await pilot.pause()
            self.assertTrue(panel.is_open, "Permissions panel should be open after clicking #btn-permissions")
            self.assertEqual(composer.styles.max_height.value, 85)
            
            # Test 3D Toggle
            toggles = list(panel.query(Toggle3D))
            self.assertTrue(len(toggles) > 0, "Should have Toggle3D instances in panel")
            first_toggle = toggles[0]
            initial_val = first_toggle.is_enabled
            first_toggle.press()
            await pilot.pause()
            self.assertNotEqual(first_toggle.is_enabled, initial_val, "Toggle state should have inverted")
            
            # Test mode cycler
            mode_btn = panel.query_one("#cct-perm-mode-btn")
            self.assertIsNotNone(mode_btn)
            old_mode_label = str(mode_btn.label)
            mode_btn.press()
            await pilot.pause()
            self.assertNotEqual(str(mode_btn.label), old_mode_label, "Security mode label should have updated")
            
            # Test close button
            close_btn = panel.query_one("#cct-perm-close")
            self.assertIsNotNone(close_btn)
            close_btn.press()
            await pilot.pause()
            self.assertFalse(panel.is_open, "Permissions panel should be closed after clicking #cct-perm-close")
            self.assertEqual(composer.styles.max_height.value, orig_max_h)
            
            # Test Escape key closes panel
            btn_perm.press()
            await pilot.pause()
            self.assertTrue(panel.is_open)
            await pilot.press("escape")
            await pilot.pause()
            self.assertFalse(panel.is_open, "Permissions panel should be closed after pressing escape")


if __name__ == "__main__":
    unittest.main()
