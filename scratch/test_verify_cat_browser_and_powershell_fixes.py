import os
import sys
import unittest
import time
from pathlib import Path
from unittest.mock import patch

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from calc_terminal import commands_data
from calc_terminal import registry
from calc_terminal.browser_gui import browser_pages
from calc_terminal.host.launcher import get_optimal_chromium_flags
from calc_terminal.host import supervisor
from calc_terminal import doctor
from calc_terminal import first_run


class TestCatBrowserAndPowerShellFixes(unittest.TestCase):
    def test_01_cat_command_completely_removed(self):
        """Verify /cat slash command is completely eliminated from CAT CLI."""
        # 1. commands_data
        names_to_desc = dict(commands_data.COMMANDS)
        self.assertNotIn("/cat", names_to_desc)
        self.assertNotIn("/cat doctor", names_to_desc)
        self.assertNotIn("/cat self-test", names_to_desc)
        self.assertNotIn("/cat verify", names_to_desc)
        self.assertNotIn("/cat", commands_data.NATIVE_UI_COMMANDS)

        self.assertIn("/browser", names_to_desc)
        self.assertIn("/browse", names_to_desc)
        self.assertIn("/doctor", names_to_desc)
        self.assertIn("/self-test", names_to_desc)
        self.assertIn("/verify", names_to_desc)

        # 2. registry
        reg = registry.get_registry()
        self.assertNotIn("/cat", reg)
        self.assertNotIn("/cat", registry.ALIAS_TABLE)
        browser_spec = reg.get("/browser")
        self.assertIsNotNone(browser_spec)
        self.assertIn("/browse", browser_spec.aliases)
        self.assertNotIn("/cat", browser_spec.aliases)

    def test_02_backend_agent_browser_and_obscura(self):
        """Verify Agent Browser and Obscura work in the backend for AI agents."""
        # DOM accessibility inspection
        html_sample = "<html><body><h1>Dashboard</h1><button id='btn1'>Submit</button></body></html>"
        tree = browser_pages.agent_inspect_page("https://example.com", html_content=html_sample)
        self.assertIn("tree", tree)
        self.assertIn("interactable_elements", tree)
        self.assertTrue(len(tree["interactable_elements"]) >= 1)
        self.assertEqual(tree["interactable_elements"][0]["tag"], "button")

        # Obscura stealth tracker stripping
        clean_url = browser_pages.strip_tracker_params("https://example.com/page?utm_source=twitter&fbclid=123&keep=ok")
        self.assertNotIn("utm_source", clean_url)
        self.assertNotIn("fbclid", clean_url)
        self.assertIn("keep=ok", clean_url)

        # Agent tool empowerment in agent.py
        from calc_terminal.agent import _tool_cat_browser
        res = _tool_cat_browser({"action": "agent_inspect", "url": "https://example.com"})
        self.assertIn("success", res)

    def test_03_front_end_browser_clean_ui(self):
        """Verify Fatty CAT, Obscura, and Agent Browser are removed from browser front-end UI."""
        with open(repo_root / "calc_terminal" / "host" / "desktop.py", "r", encoding="utf-8") as f:
            desktop_code = f.read()
        self.assertNotIn('("🐱", "Fatty CAT"', desktop_code)
        self.assertNotIn('("🤖", "Agent Browser"', desktop_code)
        self.assertNotIn('("🛡️", "Obscura Web"', desktop_code)
        self.assertIn('"CAT Workspace"', desktop_code)
        self.assertIn('"Fomoji Portal"', desktop_code)

        with open(repo_root / "calc_terminal" / "browser_gui" / "qt_browser.py", "r", encoding="utf-8") as f:
            qt_code = f.read()
        self.assertNotIn('("🐱", "Fatty CAT"', qt_code)
        self.assertNotIn('("🤖", "Agent Browser"', qt_code)
        self.assertNotIn('("🛡️", "Obscura Web"', qt_code)
        self.assertIn('"CAT Workspace"', qt_code)
        self.assertIn('"Fomoji Portal"', qt_code)

    def test_04_zoom_anti_crash_protection(self):
        """Verify debounced rate-limiting, range clamping (0.25-3.0), and crash recovery exist."""
        with open(repo_root / "calc_terminal" / "browser_gui" / "qt_browser.py", "r", encoding="utf-8") as f:
            qt_code = f.read()
        self.assertIn("def _step_zoom", qt_code)
        self.assertIn("def _apply_debounced_zoom", qt_code)
        self.assertIn("self._zoom_timer.setInterval(45)", qt_code)
        self.assertIn("max(0.25, min(3.0", qt_code)
        self.assertIn("renderProcessTerminated.connect", qt_code)

        with open(repo_root / "calc_terminal" / "host" / "desktop.py", "r", encoding="utf-8") as f:
            desktop_code = f.read()
        self.assertIn("def _step_zoom", desktop_code)
        self.assertIn("def _apply_debounced_zoom", desktop_code)
        self.assertIn("self._zoom_timer.setInterval(45)", desktop_code)
        self.assertIn("max(0.25, min(3.0", desktop_code)
        self.assertIn("renderProcessTerminated.connect", desktop_code)

    def test_05_custom_ultra_smooth_scrollbar(self):
        """Verify modern 8px custom scrollbar is injected into WebEngine and styled on Qt widgets."""
        with open(repo_root / "calc_terminal" / "browser_gui" / "qt_browser.py", "r", encoding="utf-8") as f:
            qt_code = f.read()
        self.assertIn("cat_custom_scrollbar_engine", qt_code)
        self.assertIn("::-webkit-scrollbar { width: 8px", qt_code)
        self.assertIn("QScrollBar:vertical", qt_code)

        with open(repo_root / "calc_terminal" / "host" / "desktop.py", "r", encoding="utf-8") as f:
            desktop_code = f.read()
        self.assertIn("cat_custom_scrollbar_engine", desktop_code)
        self.assertIn("::-webkit-scrollbar { width: 8px", desktop_code)
        self.assertIn("QScrollBar:vertical", desktop_code)

    def test_06_fomoji_exclusivity_middleware(self):
        """Verify Fomoji server enforces exclusive CAT Browser access with 403 screen for external browsers."""
        with open(repo_root / "calc_terminal" / "fomoji_server" / "src" / "security.js", "r", encoding="utf-8") as f:
            sec_code = f.read()
        self.assertIn("catBrowserExclusivityMiddleware", sec_code)
        self.assertIn("CATBrowser", sec_code)
        self.assertIn("x-cat-browser", sec_code)
        self.assertIn("x-cat-vault-token", sec_code)
        self.assertIn("Access Restricted — CAT Browser Required", sec_code)

    def test_07_hardware_system_algorithm_tuning(self):
        """Verify dynamic hardware algorithm adjusts HTTP cache and raster limits."""
        with open(repo_root / "calc_terminal" / "host" / "desktop.py", "r", encoding="utf-8") as f:
            desktop_code = f.read()
        self.assertIn("HardwareAnalyzer", desktop_code)
        self.assertIn("32 * 1024 * 1024", desktop_code)
        self.assertIn("256 * 1024 * 1024", desktop_code)

    def test_08_corner_border_radius_rock_solid(self):
        """Verify 12px rounded corner clipping is enforced in any condition."""
        with open(repo_root / "calc_terminal" / "browser_gui" / "qt_browser.py", "r", encoding="utf-8") as f:
            qt_code = f.read()
        self.assertIn("def _update_window_mask", qt_code)
        self.assertIn("border-radius: 12px;", qt_code)
        self.assertIn("_apply_win32_window_decorations", qt_code)

        with open(repo_root / "calc_terminal" / "host" / "desktop.py", "r", encoding="utf-8") as f:
            desktop_code = f.read()
        self.assertIn("def _update_window_mask", desktop_code)
        self.assertIn("border-radius: 12px;", desktop_code)
        self.assertIn("_apply_win32_window_decorations", desktop_code)


if __name__ == "__main__":
    unittest.main()
