"""
Tests for CAT CLI Terminal Tab and Window Identity.
"""

import os
import sys
import unittest
from unittest import mock

from calc_terminal import identity, terminal_identity, theme
from calc_terminal import doctor


class TestTerminalIdentity(unittest.TestCase):
    def test_identity_constants(self):
        self.assertEqual(identity.CLI_TITLE, "CAT CLI")
        self.assertEqual(identity.CLI_EMOJI, "🐱")
        self.assertEqual(identity.FULL_CLI_TITLE, "🐱 CAT CLI")
        self.assertEqual(terminal_identity.BRAND_NAME, "CAT CLI")
        self.assertEqual(terminal_identity.BRAND_EMOJI, "🐱")
        self.assertEqual(terminal_identity.DEFAULT_TITLE, "🐱 CAT CLI")
        self.assertEqual(terminal_identity.PLAIN_TITLE, "CAT CLI")

    def test_icon_asset_exists_and_valid(self):
        ico_path = terminal_identity.get_icon_path()
        self.assertIsNotNone(ico_path)
        self.assertTrue(os.path.isfile(ico_path))
        self.assertGreater(os.path.getsize(ico_path), 0)

        # Validate with PIL if available
        try:
            from PIL import Image
            with Image.open(ico_path) as img:
                self.assertEqual(img.format, "ICO")
        except ImportError:
            pass

    def test_set_terminal_title_formatting(self):
        # Fake stdout with isatty returning True
        class MockTTY:
            def __init__(self):
                self.data = []
            def isatty(self):
                return True
            def write(self, s):
                self.data.append(s)
            def flush(self):
                pass

        mock_out = MockTTY()
        with mock.patch.object(sys, "stdout", mock_out):
            terminal_identity.set_terminal_title()
            # Check current active title
            self.assertEqual(terminal_identity._current_active_title, "🐱 CAT CLI")

            # Custom title with state
            terminal_identity.set_terminal_title("ready")
            self.assertEqual(terminal_identity._current_active_title, "🐱 CAT CLI — Ready")

            terminal_identity.set_terminal_title("custom title")
            self.assertEqual(terminal_identity._current_active_title, "🐱 CAT CLI — custom title")

            # Restore
            popped = terminal_identity.restore_terminal_title()
            self.assertTrue(popped)

    def test_polluted_title_detection(self):
        # Should detect shells as polluted
        self.assertTrue(terminal_identity._is_polluted_title("Command Prompt"))
        self.assertTrue(terminal_identity._is_polluted_title("Command Prompt - cat"))
        self.assertTrue(terminal_identity._is_polluted_title("PowerShell"))
        self.assertTrue(terminal_identity._is_polluted_title("Windows PowerShell"))
        self.assertTrue(terminal_identity._is_polluted_title("cmd.exe"))
        self.assertTrue(terminal_identity._is_polluted_title("pwsh"))
        self.assertTrue(terminal_identity._is_polluted_title("npm run dev"))
        self.assertTrue(terminal_identity._is_polluted_title("git status"))
        self.assertTrue(terminal_identity._is_polluted_title(""))
        self.assertTrue(terminal_identity._is_polluted_title(None))

        # Should NOT detect CAT as polluted
        self.assertFalse(terminal_identity._is_polluted_title("CAT CLI"))
        self.assertFalse(terminal_identity._is_polluted_title("🐱 CAT CLI"))
        self.assertFalse(terminal_identity._is_polluted_title("🐱 CAT CLI — Ready"))
        self.assertFalse(terminal_identity._is_polluted_title("Coding Agent Terminal"))

    def test_windows_terminal_profile_configuration(self):
        if sys.platform == "win32":
            settings_path = terminal_identity.find_windows_terminal_settings()
            if settings_path and os.path.isfile(settings_path):
                ok, msg = terminal_identity.configure_windows_terminal_profile()
                self.assertTrue(ok)
                import json
                with open(settings_path, "r", encoding="utf-8-sig") as f:
                    data = json.load(f)
                profiles = data.get("profiles", {}).get("list", [])
                cat_profiles = [p for p in profiles if p.get("name") == "CAT CLI"]
                self.assertTrue(len(cat_profiles) >= 1)
                cat_prof = cat_profiles[0]
                self.assertEqual(cat_prof.get("name"), "CAT CLI")
                self.assertEqual(cat_prof.get("tabTitle"), "CAT CLI")
                self.assertTrue(cat_prof.get("icon", "").endswith("cat.ico"))

    def test_theme_compatibility(self):
        # Verify theme.set_terminal_title and set_terminal_title_state work seamlessly
        class MockTTY:
            def __init__(self):
                self.data = []
            def isatty(self):
                return True
            def write(self, s):
                self.data.append(s)
            def flush(self):
                pass

        mock_out = MockTTY()
        with mock.patch.object(sys, "stdout", mock_out):
            ok = theme.set_terminal_title("CAT CLI")
            self.assertTrue(ok)
            theme.set_terminal_title_state("ready")
            joined = "".join(mock_out.data)
            self.assertIn("\x1b]0;CAT CLI\x07", joined)
            self.assertIn("\x1b]0;CAT CLI — Ready\x07", joined)
            popped = theme.restore_terminal_title()
            self.assertTrue(popped)

    def test_doctor_terminal_check(self):
        rc = doctor.fix_terminal()
        self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
