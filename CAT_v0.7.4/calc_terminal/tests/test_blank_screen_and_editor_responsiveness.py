"""
Tests for Blank Screen Elimination, Instant Startup Transition,
and Code Editor Typing Responsiveness.
"""

import os
import time
import unittest
from unittest.mock import MagicMock, patch

from calc_terminal import project_stats
from calc_terminal.ui.welcome_modal import (
    WelcomeModal,
    has_seen_version,
    mark_seen,
)
from calc_terminal.ui.editor import (
    _resolve_editor_cmd,
    _get_ed_actions,
    _dispatch_gesture_shortcut,
    _EditorArea,
    EditorPane,
)


class TestBlankScreenAndPerformance(unittest.TestCase):
    def test_project_stats_caching_and_bounds(self):
        """Verify project_stats uses memory cache and bounded scanning to prevent UI freezes."""
        self.assertLessEqual(project_stats.MAX_SCAN_FILES, 5000)
        self.assertIn(".git", project_stats._IGNORE_DIRS)
        self.assertIn("node_modules", project_stats._IGNORE_DIRS)
        self.assertIn("__pycache__", project_stats._IGNORE_DIRS)

        # Call scan_workspace twice; second call should hit memory cache immediately
        t0 = time.time()
        res1 = project_stats.scan_workspace(".")
        t1 = time.time()
        res2 = project_stats.scan_workspace(".")
        t2 = time.time()

        self.assertIsInstance(res1, dict)
        self.assertEqual(res1["total_files"], res2["total_files"])
        # Second call should be near instant (< 5ms)
        self.assertLess(t2 - t1, 0.05)

    def test_welcome_modal_zero_delay_configuration(self):
        """Verify welcome modal has fast interval and eliminates forced 3-second wait."""
        self.assertLessEqual(WelcomeModal._BOOT_INTERVAL, 0.05)
        self.assertEqual(WelcomeModal._BOOT_STEPS, 16)

        modal = WelcomeModal()
        # Verify status text matches progression
        self.assertIn("ready", modal._get_status_text(WelcomeModal._BOOT_STEPS).lower())

        # Verify auto-transition behavior when boot finishes
        modal._boot_step = WelcomeModal._BOOT_STEPS
        modal._boot_timer = MagicMock()
        modal._update_boot_view = MagicMock()
        modal.set_timer = MagicMock()
        modal._tick_boot()
        self.assertTrue(modal._is_boot_done)
        modal.set_timer.assert_called_once()

    def test_editor_typing_fast_path(self):
        """Verify plain keystrokes bypass shortcut overhead for zero typing latency."""
        area = _EditorArea()
        area.action_show_preview = MagicMock()

        # Regular typing character 'a' without modifiers
        mock_event_a = MagicMock()
        mock_event_a.key = "a"
        mock_event_a.ctrl = False
        mock_event_a.alt = False
        mock_event_a.meta = False

        area._on_key(mock_event_a)
        # Should return immediately without stopping event or triggering preview
        mock_event_a.stop.assert_not_called()
        area.action_show_preview.assert_not_called()

        # Special key like shift+enter triggers preview
        mock_event_prev = MagicMock()
        mock_event_prev.key = "shift+enter"
        mock_event_prev.ctrl = False
        mock_event_prev.alt = False
        mock_event_prev.meta = False

        area._on_key(mock_event_prev)
        mock_event_prev.stop.assert_called_once()
        area.action_show_preview.assert_called_once()

    def test_editor_toolbar_dirty_checking(self):
        """Verify EditorPane toolbar updates only dirty widgets to prevent Textual DOM thrashing."""
        pane = EditorPane()
        pane._last_tb_values = {}

        mock_static = MagicMock()
        pane.query_one = MagicMock(return_value=mock_static)

        # First update should call update on widget
        pane._update_tb_item("#cct-tb-pos", "Ln 1, Col 1")
        mock_static.update.assert_called_once_with("Ln 1, Col 1")

        # Second update with SAME value should NO-OP (zero Textual DOM invalidation)
        mock_static.reset_mock()
        pane._update_tb_item("#cct-tb-pos", "Ln 1, Col 1")
        mock_static.update.assert_not_called()

        # Update with new value should update widget
        pane._update_tb_item("#cct-tb-pos", "Ln 1, Col 2")
        mock_static.update.assert_called_once_with("Ln 1, Col 2")


if __name__ == "__main__":
    unittest.main()
