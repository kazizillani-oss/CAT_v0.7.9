import pytest
from unittest.mock import MagicMock, patch

from calc_terminal.ui.app import CCTApp
from calc_terminal.core.mode_registry import mode_registry
from calc_terminal.commands_data import COMMANDS, NATIVE_UI_COMMANDS


def test_command_palette_registry_coverage():
    # Verify all new platform commands are registered
    command_names = [c[0] for c in COMMANDS]
    assert "/cat doctor" in command_names
    assert "/cat self-test" in command_names
    assert "/cat verify" in command_names
    assert "/doctor" in command_names
    assert "/self-test" in command_names
    assert "/verify" in command_names
    assert "/mode create" in command_names
    assert "/mode list" in command_names
    assert "/mode delete" in command_names
    assert "/checkpoint" in command_names
    assert "/compute" in command_names

    assert "/doctor" in NATIVE_UI_COMMANDS
    assert "/self-test" in NATIVE_UI_COMMANDS
    assert "/verify" in NATIVE_UI_COMMANDS
    assert "/checkpoint" in NATIVE_UI_COMMANDS
    assert "/compute" in NATIVE_UI_COMMANDS


def test_ui_command_dispatch_doctor_and_selftest():
    # Instantiate a mock app instance to test _handle_command
    app = CCTApp.__new__(CCTApp)
    notes = []
    app._system_note = lambda msg, role="system": notes.append((msg, role))
    app._workspace_root = None

    # 1. Test /cat doctor
    app._handle_command("/cat doctor")
    assert len(notes) >= 1
    assert "CAT SYSTEM DOCTOR REPORT" in notes[-1][0]

    # 2. Test /doctor alias
    app._handle_command("/doctor")
    assert "CAT SYSTEM DOCTOR REPORT" in notes[-1][0]

    # 3. Test /cat self-test
    app._handle_command("/cat self-test")
    assert "CAT AUTOMATED SELF-TEST SUITE" in notes[-1][0]

    # 4. Test /verify
    app._handle_command("/verify")
    assert "VERIFICATION EVIDENCE TABLE" in notes[-1][0]

    # 5. Test /compute
    app._handle_command("/compute")
    assert "Compute Fabric Targets" in notes[-1][0]


def test_ui_command_dispatch_mode_management():
    app = CCTApp.__new__(CCTApp)
    notes = []
    app._system_note = lambda msg, role="system": notes.append((msg, role))
    app._set_ai_mode = MagicMock()

    with patch.object(CCTApp, "composer", new_callable=lambda: MagicMock()):
        # 1. /mode list
        app._handle_command("/mode list")
        assert "Active AI Modes" in notes[-1][0]

        # 2. /mode create BioLab
        app._handle_command("/mode create BioLab Computational biology mode")
        assert "registered successfully" in notes[-1][0]
        assert mode_registry.get_mode("biolab") is not None

        # 3. /mode biolab (switch)
        app._handle_command("/mode biolab")
        app._set_ai_mode.assert_called_with("biolab")

        # 4. /mode delete BioLab
        app._handle_command("/mode delete BioLab")
        assert "removed successfully" in notes[-1][0]
        assert mode_registry.get_mode("biolab") is None


def test_ui_command_dispatch_cat_browser_fallback():
    app = CCTApp.__new__(CCTApp)
    notes = []
    app._system_note = lambda msg, role="system": notes.append((msg, role))
    browser_calls = []
    app.action_toggle_browser = lambda start_url="": browser_calls.append(start_url)

    # Bare /cat
    app._handle_command("/cat")
    assert len(browser_calls) == 1
    assert browser_calls[-1] == "about:home"

    # /cat https://example.com
    app._handle_command("/cat https://example.com")
    assert len(browser_calls) == 2
    assert browser_calls[-1] == "https://example.com"
