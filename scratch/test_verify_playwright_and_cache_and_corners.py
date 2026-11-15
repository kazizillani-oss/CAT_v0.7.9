#!/usr/bin/env python3
"""
Verification suite for CAT Browser crash elimination, Playwright integration,
corner border radius permanence, and total removal of Fatty CAT in Browser & Fomoji.
"""

import os
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

class TestCATBrowserAndPlaywrightResolution(unittest.TestCase):
    def test_01_playwright_package_and_launcher_integration(self):
        """Verify Playwright package is recognized by launcher.py."""
        from calc_terminal.host.launcher import can_launch_host, get_host_status
        from calc_terminal.browser_gui.playwright_browser import can_launch_playwright

        self.assertTrue(can_launch_playwright(), "Playwright should be available and ready")
        self.assertTrue(can_launch_host(), "Launcher should report host can be launched")
        status = get_host_status()
        self.assertIn("Playwright (Chromium)", status["engines"])

    def test_02_playwright_browser_vault_headers_and_no_fatty(self):
        """Verify playwright_browser.py injects Fomoji vault headers and has no fatty cat."""
        p = REPO_ROOT / "calc_terminal" / "browser_gui" / "playwright_browser.py"
        content = p.read_text(encoding="utf-8")

        self.assertIn("X-CAT-Browser", content)
        self.assertIn("X-CAT-Vault-Token", content)
        self.assertIn("CAT Workspace", content)
        self.assertIn("Fomoji Portal", content)
        self.assertIn("12px", content)
        self.assertNotIn("fatty cat", content.lower())
        self.assertNotIn("fattycat", content.lower())

    def test_03_fomoji_server_home_html_no_fatty_cat(self):
        """Verify Fomoji home.html has replaced all FATTY CAT text with CAT Workspace."""
        p = REPO_ROOT / "calc_terminal" / "fomoji_server" / "public" / "home.html"
        content = p.read_text(encoding="utf-8")

        self.assertIn("CAT CLI &amp; CAT Workspace", content)
        self.assertIn("Start CAT Workspace", content)
        self.assertIn("/api/workspace/status", content)
        self.assertNotIn("FATTY CAT", content)
        self.assertNotIn("Fatty CAT", content)

    def test_04_desktop_and_qt_browser_cache_and_translucency(self):
        """Verify MemoryHttpCache and WA_TranslucentBackground in desktop.py and qt_browser.py."""
        desktop_p = REPO_ROOT / "calc_terminal" / "host" / "desktop.py"
        qt_p = REPO_ROOT / "calc_terminal" / "browser_gui" / "qt_browser.py"

        d_text = desktop_p.read_text(encoding="utf-8")
        q_text = qt_p.read_text(encoding="utf-8")

        # MemoryHttpCache prevents Windows 0x5 cache lock crashes
        self.assertIn("MemoryHttpCache", d_text)
        self.assertIn("MemoryHttpCache", q_text)
        self.assertIn("session_", d_text)
        self.assertIn("session_", q_text)

        # Translucency is True so rounded corners do not render black square artifacts
        self.assertIn("WA_TranslucentBackground, True", d_text)
        self.assertIn("WA_TranslucentBackground, True", q_text)

    def test_05_corner_border_radius_permanence(self):
        """Verify 12px rounded corner mask is always applied in normal window mode."""
        desktop_p = REPO_ROOT / "calc_terminal" / "host" / "desktop.py"
        qt_p = REPO_ROOT / "calc_terminal" / "browser_gui" / "qt_browser.py"

        d_text = desktop_p.read_text(encoding="utf-8")
        q_text = qt_p.read_text(encoding="utf-8")

        self.assertIn("addRoundedRect(QRectF(0, 0, w, h), 12.0, 12.0)", d_text)
        self.assertIn("addRoundedRect(QRectF(0, 0, w, h), 12.0, 12.0)", q_text)
        self.assertIn("setMask(QRegion(poly))", d_text)
        self.assertIn("setMask(QRegion(poly))", q_text)

    def test_06_supervisor_playwright_fallback(self):
        """Verify supervisor automatically falls back to Playwright if Qt crashes."""
        sup_p = REPO_ROOT / "calc_terminal" / "host" / "supervisor.py"
        text = sup_p.read_text(encoding="utf-8")

        self.assertIn("fallback_to_playwright_after_qt_crash", text)
        self.assertIn("launch_playwright_browser", text)

    def test_07_cli_launcher_workspace_and_backend_flags(self):
        """Verify launcher.py and cli.py support --workspace and --backend."""
        launch_p = REPO_ROOT / "calc_terminal" / "host" / "launcher.py"
        cli_p = REPO_ROOT / "calc_terminal" / "cli.py"

        l_text = launch_p.read_text(encoding="utf-8")
        c_text = cli_p.read_text(encoding="utf-8")

        self.assertIn("--workspace", l_text)
        self.assertIn("--backend", l_text)
        self.assertIn("workspace", c_text)
        self.assertIn("CAT Workspace", c_text)

if __name__ == "__main__":
    unittest.main()
