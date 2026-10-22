"""
Tests for CAT Code Editor and CLI Crash-Proofing.
Verifies:
1. Editor toolbar refresh with active file editor (no UnboundLocalError: 'icon').
2. Fast and resilient toolbar item updates (_update_tb_item).
3. Tab lifecycle resilience (_create_tab, close_active, active_text_area).
4. WorkspaceShell.open_file and open_file_at error boundary.
5. launch_chat_app SystemExit and exception recovery.
"""

import os
import sys
import tempfile
from unittest.mock import MagicMock, patch
import pytest

from calc_terminal.ui.editor import EditorPane, _EditorArea
from calc_terminal.ui.workspace import WorkspaceShell, WorkspaceMode


class TestCodeEditorAndCliCrashProof:

    def test_editor_refresh_toolbar_with_active_area_no_crash(self):
        """Verifies that _refresh_toolbar executes cleanly with an active _EditorArea
        and does not raise UnboundLocalError: name 'icon' is not defined."""
        pane = EditorPane()
        mock_area = MagicMock()
        mock_area.path = "sample_test.py"
        mock_area.language = "python"
        mock_area.cursor_location = (10, 5)
        mock_area.indent_width = 4
        mock_area.soft_wrap = True

        pane.active_text_area = lambda: mock_area
        pane._get_active_content = lambda: (None, None)
        pane.query_one = MagicMock()

        # Should execute cleanly without UnboundLocalError
        pane._refresh_toolbar()

        # Verify query_one was called to find toolbar
        assert pane.query_one.called

    def test_editor_update_tb_item_defensive(self):
        """Verifies that _update_tb_item works even if _last_tb_values was uninitialized
        or if query_one raises an exception."""
        pane = EditorPane()
        pane._last_tb_values = None

        mock_static = MagicMock()
        pane.query_one = MagicMock(return_value=mock_static)

        pane._update_tb_item("#cct-tb-file", "test_file.py", tooltip="/path/to/test")

        assert pane._last_tb_values is not None
        assert pane._last_tb_values["#cct-tb-file"] == ("test_file.py", "/path/to/test")
        mock_static.update.assert_called_with("test_file.py")

        # Second call with same value should skip update (caching)
        mock_static.update.reset_mock()
        pane._update_tb_item("#cct-tb-file", "test_file.py", tooltip="/path/to/test")
        mock_static.update.assert_not_called()

        # Call when query_one throws should not raise
        pane.query_one = MagicMock(side_effect=Exception("Widget detached"))
        pane._update_tb_item("#cct-tb-file", "new_file.py")

    def test_editor_active_text_area_safety(self):
        """Verifies active_text_area safely returns None when TabbedContent or active pane is missing."""
        pane = EditorPane()
        # When query_one throws NoMatches
        pane.query_one = MagicMock(side_effect=Exception("No widget"))
        assert pane.active_text_area() is None

        # When active tab pane is None
        mock_tabs = MagicMock()
        mock_tabs.active = "tab-missing"
        mock_tabs.get_pane.return_value = None
        pane.query_one = MagicMock(return_value=mock_tabs)
        assert pane.active_text_area() is None

    def test_editor_close_active_safety(self):
        """Verifies close_active does not raise exception when called on empty editor or detached DOM."""
        pane = EditorPane()
        pane.query_one = MagicMock(side_effect=Exception("DOM detached"))
        # Should not crash
        pane.close_active()

    def test_editor_create_tab_error_boundary(self):
        """Verifies _create_tab returns False on DOM error rather than crashing."""
        pane = EditorPane()
        pane.query_one = MagicMock(side_effect=Exception("Add pane failed"))
        result = pane._create_tab("test.py", MagicMock())
        assert result is False

    def test_workspace_shell_open_file_crash_boundary(self):
        """Verifies WorkspaceShell.open_file and open_file_at catch exceptions from editor."""
        mock_conv = MagicMock()
        shell = WorkspaceShell(conversation_view=mock_conv)
        shell._editor = MagicMock()
        shell._editor.open_file.side_effect = RuntimeError("Fatal disk read error")

        # Should catch and return False
        assert shell.open_file("corrupt.py") is False

        shell._editor.open_file_at.side_effect = RuntimeError("Cursor out of range")
        assert shell.open_file_at("corrupt.py", 10, 2) is False

    def test_launch_chat_app_system_exit_handling(self):
        """Verifies launch_chat_app catches SystemExit cleanly instead of aborting the process."""
        from calc_terminal.ui.app import launch_chat_app

        mock_repl = MagicMock()
        mock_repl.history = []

        with patch("calc_terminal.ui.app.TEXTUAL_AVAILABLE", True), \
             patch("calc_terminal.keys.stdin_is_interactive", return_value=True), \
             patch("calc_terminal.ui.app.CCTApp") as mock_app_cls:

            # Case 1: Normal exit (code 0)
            mock_app_instance = MagicMock()
            mock_app_instance.run.side_effect = SystemExit(0)
            mock_app_cls.return_value = mock_app_instance

            ok, msg = launch_chat_app(mock_repl, [], {})
            assert ok is True

            # Case 2: Abnormal exit (code 1) -> should return ok=False so CLI falls back to REPL
            mock_app_instance.run.side_effect = SystemExit(1)
            ok, msg = launch_chat_app(mock_repl, [], {})
            assert ok is False
            assert "exited unexpectedly" in msg or "1" in msg
