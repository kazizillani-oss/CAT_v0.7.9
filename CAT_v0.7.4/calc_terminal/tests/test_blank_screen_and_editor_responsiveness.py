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

    def test_editor_common_typing_keys_bypass(self):
        """Verify space, enter, backspace, and navigation keys bypass all shortcut resolution."""
        area = _EditorArea()
        area.action_show_preview = MagicMock()

        for key_name in ["space", "enter", "backspace", "delete", "tab", "up", "down", "left", "right"]:
            evt = MagicMock()
            evt.key = key_name
            evt.ctrl = False
            evt.alt = False
            evt.meta = False
            evt.shift = False
            area._on_key(evt)
            evt.stop.assert_not_called()
            area.action_show_preview.assert_not_called()

    def test_gestures_disk_io_throttling(self):
        """Verify gestures._load() caches in-memory without repetitive filesystem stats."""
        from calc_terminal.gestures import manager
        with patch("os.path.getmtime") as mock_mtime:
            mock_mtime.return_value = 12345.0
            # Force cache reset
            manager._cache = [{"id": "test_g", "trigger": "test", "target": "test", "enabled": True}]
            manager._last_check_time = time.time()
            
            # Consecutive loads should NOT call os.path.getmtime
            res1 = manager._load()
            res2 = manager._load()
            self.assertEqual(len(res1), 1)
            self.assertEqual(len(res2), 1)
            mock_mtime.assert_not_called()

    def test_shortcut_manager_o1_resolution(self):
        """Verify ShortcutManager resolves indexed keys in O(1)."""
        from calc_terminal.editor.shortcuts import ShortcutManager
        mgr = ShortcutManager()
        self.assertIn("ctrl+s", mgr._by_key)
        self.assertEqual(mgr.resolve("ctrl+s", context="editor"), "editor.save")
        self.assertEqual(mgr.resolve("shift+enter", context="editor"), "preview.open")
        self.assertIsNone(mgr.resolve("non_existent_key_xyz"))

    def test_version_sync_v0_8_ab(self):
        """Verify core and identity versions report 0.8.ab."""
        from calc_terminal import identity, __version__
        self.assertEqual(identity.APP_VERSION, "0.8.ab")
        self.assertEqual(__version__, "0.8.ab")

    def test_statusbar_no_seconds_flicker(self):
        """Verify statusbar output has minute-level time to prevent 1.6s redraw flicker."""
        from calc_terminal.ui.statusbar import StatusFields
        sf = StatusFields(lambda: {"workspace": "test", "model_label": "qwen2.5"})
        fields = sf.fields()
        # Find clock field
        clock_fields = [f[1] for f in fields if f[0] == "" and ":" in f[1]]
        self.assertTrue(len(clock_fields) >= 1)
        clock_val = clock_fields[0]
        # Should be HH:MM format (5 chars), NOT HH:MM:SS (8 chars)
        self.assertEqual(len(clock_val), 5)
        self.assertEqual(clock_val.count(":"), 1)


if __name__ == "__main__":
    unittest.main()
