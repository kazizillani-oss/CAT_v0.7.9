"""
Unit tests for Fomoji CLI braille animations, progress bar engine,
background server execution, and Textual bootup loading animations.
"""

import io
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

from calc_terminal.fomoji_manager import (
    CLIProgressAnimation,
    get_fomoji_runtime_state,
    update_fomoji_runtime_state,
    start_fomoji_server,
    start_fomoji_server_background,
    initialize_fomoji_subsystem,
)
from calc_terminal.ui.welcome_modal import WelcomeModal
from calc_terminal.ui.startup_loader import StartupLoadingOverlay


def test_cli_progress_animation_bar_rendering():
    """Verify CLIProgressAnimation accurately renders block bar and percentages."""
    anim = CLIProgressAnimation("Testing", bar_width=20, enabled=False)

    # 0%
    bar_0 = anim._render_bar(0.0)
    assert "0%" in bar_0
    assert "░" in bar_0

    # 50%
    bar_50 = anim._render_bar(0.5)
    assert "50%" in bar_50
    assert "█" in bar_50
    assert "░" in bar_50

    # 100%
    bar_100 = anim._render_bar(1.0)
    assert "100%" in bar_100
    assert "█" in bar_100
    assert "░" not in bar_100


def test_cli_progress_animation_lifecycle_non_tty(capsys):
    """Verify CLIProgressAnimation finishes cleanly without escaping errors on non-tty."""
    anim = CLIProgressAnimation("Starting Fomoji server", enabled=False)
    anim.start()
    anim.update(title="Starting Fomoji server on port 3000...", progress=0.75)
    anim.finish(success=True, message="Fomoji server ready (http://localhost:3000)")

    captured = capsys.readouterr()
    assert "Fomoji server ready" in captured.out
    assert "✓" in captured.out


def test_cli_progress_animation_context_manager(capsys):
    """Verify CLIProgressAnimation context manager auto-finishes cleanly."""
    with CLIProgressAnimation("Checking dependencies", enabled=False) as anim:
        anim.update(progress=0.5)

    captured = capsys.readouterr()
    assert "Checking dependencies" in captured.out


def test_fomoji_runtime_state_tracking():
    """Verify background Fomoji runtime state is updated and queried thread-safely."""
    update_fomoji_runtime_state(
        status="starting",
        running=True,
        ready=False,
        port=3000,
        step="Starting Fomoji server",
        progress=0.6,
    )
    state = get_fomoji_runtime_state()
    assert state["status"] == "starting"
    assert state["running"] is True
    assert state["ready"] is False
    assert state["port"] == 3000
    assert state["step"] == "Starting Fomoji server"
    assert state["progress"] == 0.6

    update_fomoji_runtime_state(
        status="ready",
        ready=True,
        progress=1.0,
    )
    state_ready = get_fomoji_runtime_state()
    assert state_ready["status"] == "ready"
    assert state_ready["ready"] is True
    assert state_ready["progress"] == 1.0


def test_start_fomoji_server_with_progress_animation(tmp_path):
    """Verify start_fomoji_server updates CLIProgressAnimation while probing."""
    server_dir = tmp_path / "fomoji-server"
    server_dir.mkdir()
    (server_dir / "server.js").write_text("console.log('running');")

    mock_proc = MagicMock()
    mock_proc.poll.return_value = None

    anim = CLIProgressAnimation("Starting Fomoji server", enabled=False)
    anim.start = MagicMock()
    anim.update = MagicMock()

    with patch("subprocess.Popen", return_value=mock_proc), patch(
        "calc_terminal.fomoji_manager.check_server_reachable", side_effect=[False, True]
    ):
        started, msg = start_fomoji_server(
            server_dir=server_dir,
            node_path="node",
            timeout=5,
            progress_anim=anim,
        )
        assert started is True
        assert "ready" in msg.lower()
        anim.update.assert_called()


def test_initialize_fomoji_subsystem_background_mode():
    """Verify initialize_fomoji_subsystem with background=True returns immediately."""
    with patch("calc_terminal.fomoji_manager.check_server_reachable", return_value=False), patch(
        "calc_terminal.fomoji_manager.start_fomoji_server_background"
    ) as mock_bg:
        ready = initialize_fomoji_subsystem(interactive=False, background=True, animate=False)
        assert ready is True
        mock_bg.assert_called_once()


def test_welcome_modal_fomoji_background_badge_and_bar():
    """Verify WelcomeModal renders live background Fomoji status badge and shimmering bar."""
    update_fomoji_runtime_state(status="ready", ready=True, port=3000)
    modal = WelcomeModal()

    fomoji_line = modal._render_fomoji_line()
    assert "Fomoji Server Online" in fomoji_line
    assert "3000" in fomoji_line

    # Test starting state
    update_fomoji_runtime_state(status="starting", ready=False, step="installing express", port=3000)
    fomoji_starting = modal._render_fomoji_line()
    assert "Fomoji Server:" in fomoji_starting
    assert "installing express" in fomoji_starting

    # Test shimmering gradient bar
    bar_50 = modal._render_bar(0.5)
    assert "50%" in bar_50
    assert "█" in bar_50

    # Test status progression
    status_fomoji = modal._get_status_text(9)
    assert "Fomoji" in status_fomoji or "AI" in status_fomoji


def test_startup_loading_overlay_fomoji_badge():
    """Verify StartupLoadingOverlay displays background Fomoji server status."""
    update_fomoji_runtime_state(status="ready", ready=True, port=3000)
    overlay = StartupLoadingOverlay()

    badge = overlay._render_fomoji_badge()
    assert "Fomoji Server Online" in badge
    assert "3000" in badge

    bar = overlay._render_bar(0.75)
    assert "75%" in bar
    assert "█" in bar
