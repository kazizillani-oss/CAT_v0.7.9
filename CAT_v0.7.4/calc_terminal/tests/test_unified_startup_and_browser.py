"""
Test suite for Unified Startup Welcome Loader, Zero-Blank Splash, and
Anti-Flicker Hardware-Adaptive Browser Engine.
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch


class TestUnifiedStartupAndBrowser(unittest.TestCase):
    """Verifies the merged startup loader and welcome screen, zero-blank splash,
    and adaptive anti-flicker browser configuration."""

    def test_welcome_modal_structure_and_progress(self):
        """Test WelcomeModal has unified hero logo, hardware line, stages, and progress bar."""
        from calc_terminal.ui.welcome_modal import WelcomeModal
        modal = WelcomeModal()
        self.assertIsNotNone(modal)

        # Bar rendering
        bar_50 = modal._render_bar(0.5)
        self.assertIn("50%", bar_50)
        self.assertIn("█", bar_50)

        bar_100 = modal._render_bar(1.0)
        self.assertIn("100%", bar_100)

        # Realistic staged status text
        status_early = modal._get_status_text(2)
        self.assertIn("Mounting workspace", status_early)

        status_touch = modal._get_status_text(6)
        self.assertIn("touchscreen", status_touch.lower())

        status_ai = modal._get_status_text(10)
        self.assertIn("AI", status_ai)

        status_done = modal._get_status_text(16)
        self.assertIn("ready", status_done.lower())

    def test_startup_loading_overlay_backwards_compatibility(self):
        """Verify StartupLoadingOverlay in startup_loader.py still satisfies existing test contracts."""
        from calc_terminal.ui.startup_loader import StartupLoadingOverlay
        overlay = StartupLoadingOverlay()
        self.assertIsNotNone(overlay)

        bar_half = overlay._render_bar(0.50)
        self.assertIn("50%", bar_half)

        overlay.complete_and_dismiss()
        self.assertTrue(overlay._is_finishing)

    def test_hardware_adaptive_chromium_flags(self):
        """Verify Chromium flags are hardware-adaptive and strictly eliminate flickering bugs."""
        from calc_terminal.host.launcher import get_optimal_chromium_flags
        flags = get_optimal_chromium_flags()

        # CRITICAL Anti-Flicker rules:
        # Never disable GPU driver bug workarounds (causes Intel HD crash loops and flickering)
        self.assertNotIn("--disable-gpu-driver-bug-workarounds", flags)
        # Never force ignoring GPU blocklist (causes black screens on low-end GPUs)
        self.assertNotIn("--ignore-gpu-blocklist", flags)
        # Never include Linux-only Vaapi on Windows
        if sys.platform == "win32":
            self.assertNotIn("VaapiVideoDecoder", flags)
            self.assertIn("--use-angle=d3d11", flags)

        # Essential low-end memory / anti-occlusion safety flags
        self.assertIn("--disable-dev-shm-usage", flags)
        self.assertIn("--disable-features=CalculateNativeWinOcclusion", flags)
        self.assertIn("--enable-zero-copy", flags)
        self.assertIn("--enable-gpu-rasterization", flags)

        # Process limit must be bounded to avoid overwhelming CPU/RAM
        self.assertTrue(
            "--renderer-process-limit=2" in flags or "--renderer-process-limit=4" in flags
        )
        self.assertTrue(
            "--num-raster-threads=2" in flags or "--num-raster-threads=3" in flags
        )

    def test_welcome_modal_dismiss_contract(self):
        """Verify WelcomeModal dismisses cleanly on key, button, or click."""
        from calc_terminal.ui.welcome_modal import WelcomeModal, mark_seen
        modal = WelcomeModal()
        dismissed = []
        modal.dismiss = lambda res=None: dismissed.append(res)

        modal.on_key(MagicMock(key="enter"))
        self.assertEqual(dismissed, ["key"])

        modal.on_button_pressed(MagicMock())
        self.assertEqual(dismissed, ["key", "button"])

        modal.on_click(MagicMock())
        self.assertEqual(dismissed, ["key", "button", "click"])

    def test_browser_state_tab_lifecycle(self):
        """Verify BrowserState accurately tracks tabs, active tab, and URL transitions."""
        from calc_terminal.browser.browser_state import BrowserState
        state = BrowserState()
        initial_tab_count = len(state.tabs)
        self.assertGreaterEqual(initial_tab_count, 1)

        # Create additional tab
        t1 = state.new_tab("https://example.com")
        self.assertEqual(len(state.tabs), initial_tab_count + 1)
        self.assertEqual(state.active_tab_id, t1.id)
        self.assertEqual(state.active_tab.url, "https://example.com")

        # Close the newly created tab
        state.close_tab(t1.id)
        self.assertEqual(len(state.tabs), initial_tab_count)

    def test_anti_tearing_vsync_flags(self):
        """Verify --disable-gpu-vsync is never set so frames do not tear or flicker."""
        from calc_terminal.host.launcher import get_optimal_chromium_flags
        flags = get_optimal_chromium_flags()
        self.assertNotIn("--disable-gpu-vsync", flags)
        self.assertNotIn("--disable-gpu-compositing", flags)


if __name__ == "__main__":
    unittest.main()
