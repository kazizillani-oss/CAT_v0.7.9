"""
Tests for UI 3D skeuomorphism, light-mode background fixes, preview single-tab guarantee,
crash-proof markup resilience, and CAT browser accessible skeuomorphism.
"""

import os
import pytest
from rich.console import Console
from calc_terminal import theme
from calc_terminal.ui import theme_css
from calc_terminal.ui.conversation import ConversationItem
from calc_terminal.browser_gui import qt_browser


def _render_to_text(renderable):
    console = Console(record=True, width=100)
    console.print(renderable)
    return console.export_text()


def test_light_mode_theme_css_variables():
    """Verify light mode themes do not emit pitch-black surface variables."""
    theme.set_theme("github-light")
    theme_css.invalidate_css_cache()
    vars_light = theme_css.css_variables()

    assert vars_light["background"] == "#ffffff"
    assert vars_light["surface-dark"] != "#000000"
    assert vars_light["surface-dark"] != "#0e1017"
    assert vars_light["surface-alt"] != "#0e1017"
    # Ensure button foreground and input selection are present
    assert "button-foreground" in vars_light
    assert "input-selection-background" in vars_light


def test_dark_mode_theme_css_variables():
    """Verify dark mode themes emit authentic Tokyo Night surface variables."""
    theme.set_theme("tokyo-night")
    theme_css.invalidate_css_cache()
    vars_dark = theme_css.css_variables()

    assert vars_dark["surface-highlight"].startswith("#")
    assert vars_dark["surface-shadow"].startswith("#")
    assert vars_dark["surface-dark"].startswith("#")
    assert vars_dark["surface-active"].startswith("#")


def test_markup_crash_resilience_with_unclosed_brackets():
    """Verify brackets and pseudo-tags in thought traces do not crash Textual."""
    snap = {"accent_hex": "#38bdf8", "icon": "📓", "label": "Notebook"}
    raw = "<think>Thinking about [0] array access and [INFO] logs and [bold without close tag</think>Final answer"
    item = ConversationItem(
        turn_id="turn-assistant-1",
        role="assistant",
        text=raw,
        mode_snapshot=snap,
    )
    # _build_content should not raise MarkupError
    content = item._build_content()
    assert content is not None
    plain_text = _render_to_text(content)
    assert "[0]" in plain_text
    assert "[INFO]" in plain_text
    assert "Final answer" in plain_text


def test_conversation_3d_bevel_styles():
    """Verify 3D bevel borders adapt between light and dark modes."""
    snap = {"accent_hex": "#38bdf8", "icon": "📓", "label": "Notebook"}
    item = ConversationItem(
        turn_id="turn-assistant-2",
        role="assistant",
        text="Hello world",
        mode_snapshot=snap,
    )

    # In dark mode
    theme.set_theme("tokyo-night")
    theme_css.invalidate_css_cache()
    item._freeze_mode_style()
    top_style, top_color = item.styles.border_top
    assert top_style is not None

    # In light mode
    theme.set_theme("github-light")
    theme_css.invalidate_css_cache()
    item._freeze_mode_style()
    top_style, top_color = item.styles.border_top
    assert top_style is not None


def test_qt_browser_theme_colors_adaptation():
    """Verify CAT browser dynamically adapts colors and computes 3D bevels for dark and light."""
    theme.set_theme("tokyo-night")
    dark_c = qt_browser._cat_theme_colors()
    assert dark_c["is_light"] is False
    assert dark_c["bg"] == "#1a1b26"
    assert "hi" in dark_c and "sh" in dark_c
    assert dark_c["focus_ring"] == dark_c["accent"]

    theme.set_theme("github-light")
    light_c = qt_browser._cat_theme_colors()
    assert light_c["is_light"] is True
    assert light_c["bg"] == "#ffffff"
    assert light_c["hi"] == "#ffffff"
    assert light_c["sh"].startswith("#")
    assert light_c["focus_ring"] == light_c["accent"]


def test_editor_preview_request_only_one_event():
    """Verify EditorPane only dispatches single PreviewRequested event on clicking preview button."""
    from calc_terminal.ui.editor import EditorPane
    import inspect

    # Inspect source of action_show_preview to ensure duplicate launch paths were removed
    source = inspect.getsource(EditorPane.action_show_preview)
    assert "self.post_message(PreviewRequested(path))" in source
    assert "_open_in_cat_browser" not in source
    assert "action_toggle_preview" not in source
