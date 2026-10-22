"""
Tests for Page Mascot Studio (Chibi Otter & Fatty Cat in Classic and Risograph styles),
React Component, Web Assets, CLI Dispatch, and TUI Command Routing.
"""

import os
import pathlib
import pytest
from unittest.mock import patch, MagicMock

from calc_terminal.cli import main, get_command_safety
from calc_terminal.app import App
from calc_terminal.registry import bootstrap, ALIAS_TABLE, CATEGORY_MAP


def test_mascot_assets_exist():
    """Verify all 8 direction and reaction atlases exist and are non-empty WebP files."""
    static_mascots = pathlib.Path(__file__).parent.parent / "web" / "static" / "mascots"
    assert static_mascots.is_dir()

    expected_assets = [
        "otter-directions.webp",
        "otter-reactions.webp",
        "otter-riso-directions.webp",
        "otter-riso-reactions.webp",
        "fattycat-directions.webp",
        "fattycat-reactions.webp",
        "fattycat-riso-directions.webp",
        "fattycat-riso-reactions.webp",
    ]

    for name in expected_assets:
        asset_file = static_mascots / name
        assert asset_file.is_file(), f"Missing mascot atlas: {name}"
        assert asset_file.stat().st_size > 1000, f"Mascot atlas {name} is empty or corrupted"


def test_react_mascot_component_file():
    """Verify Mascot.tsx exists and defines the React Mascot component."""
    mascot_tsx = pathlib.Path(__file__).parent.parent / "web" / "static" / "Mascot.tsx"
    assert mascot_tsx.is_file()
    content = mascot_tsx.read_text(encoding="utf-8")
    assert "export function Mascot" in content
    assert "directions" in content
    assert "reactions" in content
    assert "MascotProps" in content


def test_mascot_web_integration():
    """Verify mascot.js, mascot.css, and index.html mount the mascot."""
    web_dir = pathlib.Path(__file__).parent.parent / "web" / "static"
    mascot_js = web_dir / "js" / "mascot.js"
    mascot_css = web_dir / "css" / "mascot.css"
    index_html = web_dir / "index.html"

    assert mascot_js.is_file()
    assert mascot_css.is_file()
    assert index_html.is_file()

    js_code = mascot_js.read_text(encoding="utf-8")
    assert "MascotController" in js_code or "FattyMascot" in js_code
    assert "otter" in js_code
    assert "fattycat" in js_code
    assert "riso" in js_code

    html_code = index_html.read_text(encoding="utf-8")
    assert "mascot.css" in html_code
    assert "mascot.js" in html_code
    assert 'id="cct-mascot-container"' in html_code


def test_cli_mascot_safety_contract():
    """Verify `mascot` and `mascots` are classified as safe and read-only."""
    s1 = get_command_safety(["mascot"])
    assert s1["classification"] == "read-only"
    assert s1["safe_to_automate"] is True
    assert s1["changes_state"] is False

    s2 = get_command_safety(["mascots"])
    assert s2["classification"] == "read-only"
    assert s2["safe_to_automate"] is True
    assert s2["changes_state"] is False


def test_cli_mascot_dispatch():
    """Verify running `cat mascot` launches Fatty CAT Web."""
    with patch("calc_terminal.web.server.is_server_running", return_value=True):
        with patch("calc_terminal.host.launcher.launch_cat_host", return_value=0) as mock_host:
            with patch("calc_terminal.host.launcher.can_launch_host", return_value=True):
                with patch("sys.argv", ["cat", "mascot"]):
                    rc = main()
                    assert rc == 0
                    assert mock_host.called
                    assert mock_host.call_args[1].get("start_browser_url") == "http://localhost:8765/"


def test_app_cmd_mascot():
    """Verify App.cmd_mascot runs without error and prints ASCII art."""
    app = App()
    with patch.object(app, "cmd_browser") as mock_browser:
        with patch("builtins.print") as mock_print:
            app.cmd_mascot("otter")
            assert mock_print.called
            assert mock_browser.called
            assert mock_browser.call_args[0][0] == "http://localhost:8765/"


def test_registry_mascot_commands():
    """Verify /mascot and /mascots are properly registered in the CommandRegistry."""
    reg = bootstrap()
    spec = reg.get("/mascot")
    assert spec is not None
    assert "otter" in spec.autocomplete_keywords or "mascot" in spec.autocomplete_keywords
    assert "/mascots" in spec.aliases

    spec_alias = reg.get("/mascots")
    assert spec_alias is not None


def test_tui_command_routing_mascot():
    """Verify Textual TUI routes /mascot and launches browser."""
    from calc_terminal.ui.app import CCTApp
    app = CCTApp.__new__(CCTApp)
    browser_calls = []
    notes = []
    app.action_toggle_browser = lambda start_url="": browser_calls.append(start_url)
    app._system_note = lambda text, role="system": notes.append(text)

    app._handle_command("/mascot")
    assert len(browser_calls) == 1
    assert browser_calls[0] == "http://localhost:8765/"
    assert any("Page Mascot Studio" in n for n in notes)

    app._handle_command("mascot")
    assert len(browser_calls) == 2
    assert browser_calls[1] == "http://localhost:8765/"
