"""
Unit tests for 3D Shading Effects, Chat Redesign, Full Chat Summarization & Stability.
"""

import pytest
import re
from rich.console import Console
from calc_terminal.ui import theme_css
from calc_terminal.ui.conversation import ConversationItem, _bevel_colors
from calc_terminal.commands_data import COMMANDS
from calc_terminal.ui import context_menu
from calc_terminal import chat_store


def _render_to_text(renderable):
    console = Console(record=True, width=100)
    console.print(renderable)
    return console.export_text()


def test_3d_bevel_colors_and_css_variables():
    # Verify bevel_colors generates distinct highlight and shadow
    hi, sh = _bevel_colors("#38bdf8")
    assert hi.startswith("#") and sh.startswith("#")
    assert hi != sh

    # Verify css_variables includes 3D tokens
    theme_css.invalidate_css_cache()
    cv = theme_css.css_variables()
    assert "accent-highlight" in cv
    assert "accent-shadow" in cv
    assert "surface-highlight" in cv
    assert "surface-shadow" in cv


def test_3d_classes_in_base_css():
    assert ".cct-btn-3d" in theme_css.BASE_CSS
    assert ".cct-card-3d" in theme_css.BASE_CSS
    assert ".cct-panel-3d" in theme_css.BASE_CSS


def test_user_bubble_3d_rendering():
    snap = {"accent_hex": "#38bdf8", "icon": "📓", "label": "Notebook"}
    item = ConversationItem(
        turn_id="turn-user-1",
        role="user",
        text="Hello CAT, how does quantum entanglement work?",
        mode_snapshot=snap,
        show_timestamp=True,
    )
    content = item._build_content()
    rendered_plain = _render_to_text(content)
    assert "You" in rendered_plain or "👤" in rendered_plain

    # Verify clean bubble styles
    item._freeze_mode_style()
    top_style, top_color = item.styles.border_top
    assert top_style in ("double", "round", "tall", "heavy")
    assert top_color.hex != "#000000"
    bot_style, bot_color = item.styles.border_bottom
    assert bot_style in ("double", "round", "tall", "heavy")
    # Verify bottom border is vibrant and visible (not clipped or blending into background)
    assert bot_color.hex != "#000000"


import pytest

@pytest.mark.anyio
async def test_bubble_bottom_border_not_clipped_and_animation():
    from textual.app import App, ComposeResult
    from calc_terminal.ui.conversation import ConversationView, MessageRow
    class TestChatApp(App):
        CSS = """
        ConversationView { width: 100%; height: 100%; }
        .cct-row { width: 100%; height: auto; margin-bottom: 1; }
        .cct-row-user { align-horizontal: right; }
        """
        def compose(self) -> ComposeResult:
            yield ConversationView()

    app = TestChatApp()
    async with app.run_test(size=(80, 20)) as pilot:
        cv = pilot.app.screen.query_one(ConversationView)
        item = cv.add_complete("test-1", "user", "hi", mode_snapshot={"accent_hex": "#38bdf8", "icon": "📓", "label": "Notebook"})
        await pilot.pause(0.1)
        row = pilot.app.screen.query_one(MessageRow)
        # Verify item region does not overshoot row height
        assert item.region.y == 0
        assert item.region.y + item.region.height <= row.region.height
        # Verify top border is styled
        assert item.styles.border_top[0] in ("tall", "double", "round", "heavy")
        # Verify bottom border is vibrant accent depth
        assert item.styles.border_bottom[1].hex.lower() != "#000000"


@pytest.mark.anyio
async def test_bubble_3d_hover_elevation():
    from textual.app import App, ComposeResult
    from calc_terminal.ui.conversation import ConversationItem
    class HoverApp(App):
        def compose(self) -> ComposeResult:
            yield ConversationItem("turn-h", "user", "hover test", mode_snapshot={"accent_hex": "#ec4899", "icon": "🔍", "label": "Research"})

    app = HoverApp()
    async with app.run_test(size=(60, 10)) as pilot:
        item = pilot.app.screen.query_one(ConversationItem)
        await pilot.pause(0.05)
        # Initial border
        assert item.styles.border_top[0] in ("tall", "double", "round", "heavy")
        # Hover over bubble
        await pilot.hover(ConversationItem)
        await pilot.pause(0.1)
        assert item.styles.border_top[0] in ("tall", "double", "round", "heavy")


def test_assistant_bubble_3d_and_telemetry():
    snap = {"accent_hex": "#a78bfa", "icon": "🤖", "label": "Build"}
    meta = [
        "✓ Response Complete",
        "[dim]Model: deepseek-r1[/dim]  ·  [dim]Time: 53.5s[/dim]  ·  [dim]Tokens: 33[/dim]",
        "TTFB: 46.8s  ·  Calls: 1",
    ]
    item = ConversationItem(
        turn_id="turn-asst-1",
        role="assistant",
        text="Quantum entanglement is a physical phenomenon...",
        mode_snapshot=snap,
        meta_lines=meta,
    )
    content = item._build_content()
    rendered_plain = _render_to_text(content)
    assert "CAT Assistant" in rendered_plain

    # Telemetry chip bar with rich tags cleanly stripped
    telemetry_table = item._format_telemetry()
    assert telemetry_table is not None
    telemetry_text = _render_to_text(telemetry_table)
    assert "Complete" in telemetry_text
    assert "deepseek-r1" in telemetry_text
    assert "53.5s" in telemetry_text
    assert "33 tokens" in telemetry_text
    assert "[/dim" not in telemetry_text

    # Freeze style
    item._freeze_mode_style()
    top_style, top_color = item.styles.border_top
    assert top_style in ("double", "round", "tall", "heavy")
    bot_style, bot_color = item.styles.border_bottom
    assert bot_style in ("double", "round", "tall", "heavy")


def test_header_no_new_chat_pill():
    import inspect
    from calc_terminal.ui.header import BrandHeader
    src = inspect.getsource(BrandHeader.compose)
    assert "cct-chat-title-pill" not in src
    assert "New Chat" not in src


def test_system_status_pill():
    item = ConversationItem(
        turn_id="turn-sys-1",
        role="system",
        text="Workspace switched to /home/project",
    )
    content = item._build_content()
    rendered_plain = _render_to_text(content)
    assert "ℹ" in rendered_plain
    assert "Workspace switched" in rendered_plain


def test_summarize_slash_commands_registered():
    cmds = [cmd for cmd, desc in COMMANDS]
    assert "/summarize" in cmds
    assert "/summary" in cmds


def test_context_menu_summarize_action():
    ai_actions = [action for action, label in context_menu.AI_MENU_ITEMS]
    user_actions = [action for action, label in context_menu.USER_MENU_ITEMS]
    assert "summarize" in ai_actions
    assert "summarize" in user_actions


def test_quick_title_generation():
    from calc_terminal.ui.app import CCTApp
    t1 = CCTApp._generate_quick_title(None, "How to set up deepseek-r1 locally with Ollama?")
    assert t1 != "New Chat"
    assert len(t1) <= 28
    assert "Deepseek" in t1 or "Set up" in t1

    t2 = CCTApp._generate_quick_title(None, "")
    assert t2 == "New Chat"


def test_extract_title_from_text():
    from calc_terminal.ui.app import CCTApp
    summary_text = (
        "# 📋 Executive Chat Summary: Quantum Computing Intro\n"
        "**Generated Title:** Quantum Computing Intro\n\n"
        "### 🎯 Key Objectives\n"
        "- Learn qubits"
    )
    title = CCTApp._extract_title_from_text(None, summary_text)
    assert title == "Quantum Computing Intro"


def test_chat_store_crud():
    chat = chat_store.create_chat(name="Test Session")
    chat_id = chat["id"]
    assert chat["name"] == "Test Session"

    # Add turn
    chat_store.add_turn(chat_id, "user", "Hello world")
    loaded = chat_store.get_chat(chat_id)
    assert loaded is not None
    assert loaded["turn_count"] == 1

    # Rename
    chat_store.rename_chat(chat_id, "Updated Name")
    loaded = chat_store.get_chat(chat_id)
    assert loaded["name"] == "Updated Name"

    # Delete
    chat_store.delete_chat(chat_id)
    assert chat_store.get_chat(chat_id) is None


@pytest.mark.anyio
async def test_bubble_top_border_and_no_negative_offset_clipping():
    from textual.app import App, ComposeResult
    from calc_terminal.ui.conversation import ConversationView

    class TestApp(App):
        def compose(self) -> ComposeResult:
            yield ConversationView(id="cct-conversation")

    app = TestApp()
    async with app.run_test(size=(100, 30)) as pilot:
        conv = app.query_one(ConversationView)
        item = conv.add_complete("turn-test", "user", "hi", mode_snapshot={"accent_hex": "#38bdf8", "icon": "📓", "label": "Notebook"})
        await pilot.pause(0.1)

        # 1. Top padding is 1 (clean vertical spacing, not cramped against top border)
        assert item.styles.padding.top == 1

        # 2. Offset remains 0 initially (no negative shift clipping)
        assert (item.styles.offset.x.value, item.styles.offset.y.value) == (0, 0)

        # 3. Hover does not set negative offset
        await pilot.hover(item)
        await pilot.pause(0.05)
        assert (item.styles.offset.x.value, item.styles.offset.y.value) == (0, 0)

        # 4. Leave resets and keeps offset at (0, 0)
        item.on_leave(None)
        assert (item.styles.offset.x.value, item.styles.offset.y.value) == (0, 0)

        # 5. Top border is rendered
        svg = app.export_screenshot()
        assert ("▔" in svg or "╭" in svg or "─" in svg)

        # 6. User header does not wrap Notebook onto line 2
        lines = [l for l in svg.splitlines() if "Notebook" in l]
        assert len(lines) > 0
        assert "You" in lines[0] and "Notebook" in lines[0]


@pytest.mark.anyio
async def test_sidebar_opener_hidden_when_open_and_shown_when_collapsed():
    from textual.app import App, ComposeResult
    from calc_terminal.ui.workspace import WorkspaceShell
    from calc_terminal.ui.conversation import ConversationView
    from textual.containers import Horizontal
    from textual.widgets import Button

    class ShellApp(App):
        def get_css_variables(self):
            from calc_terminal.ui.theme_css import css_variables
            v = dict(super().get_css_variables())
            v.update(css_variables())
            return v

        def compose(self) -> ComposeResult:
            yield WorkspaceShell(conversation_view=ConversationView(id="cct-conversation"))

    app = ShellApp()
    async with app.run_test(size=(120, 35)) as pilot:
        shell = app.query_one(WorkspaceShell)
        nav = shell.query_one("#cct-chat-nav", Horizontal)
        btn = shell.query_one("#cct-chat-sidebar-toggle", Button)
        await pilot.pause(0.1)

        # When sidebar is open on mount (or after being opened):
        # Explorer is visible (display=True, width>0), so nav MUST be hidden to avoid wasting space!
        if shell.explorer.display and shell.explorer.width > 0:
            assert nav.display is False

            # When sidebar is collapsed via toggle_sidebar:
            shell.toggle_sidebar()
            await pilot.pause(0.1)
            assert shell.explorer.width == 0 or not shell.explorer.display
            # Opener nav MUST be visible with "▸ Explorer" badge!
            assert nav.display is True
            assert "Explorer" in str(btn.label)

            # When sidebar is re-opened:
            shell.toggle_sidebar()
            await pilot.pause(0.1)
            assert shell.explorer.display is True
            assert shell.explorer.width > 0
            # Opener nav MUST be hidden again!
            assert nav.display is False
        else:
            # If initial state is collapsed:
            assert nav.display is True
            assert "Explorer" in str(btn.label)
            shell.toggle_sidebar()
            await pilot.pause(0.1)
            assert nav.display is False


def test_editor_toolbar_refresh_no_name_error():
    from calc_terminal.ui.editor import EditorPane
    editor = EditorPane()
    editor._schedule_toolbar_refresh()
    assert hasattr(editor, "_last_tb_refresh")
    editor._delayed_toolbar_refresh()
    assert hasattr(editor, "_last_tb_refresh")


@pytest.mark.anyio
async def test_composer_3d_effect_no_shading():
    from textual.app import App, ComposeResult
    from calc_terminal.ui.composer import StickyComposer
    from calc_terminal.ui import theme_css
    from calc_terminal.ui.app import _COMPONENT_CSS

    class ComposerTestApp(App):
        CSS = theme_css.BASE_CSS + _COMPONENT_CSS
        def get_css_variables(self):
            v = dict(super().get_css_variables())
            v.update(theme_css.css_variables())
            return v

        def compose(self) -> ComposeResult:
            yield StickyComposer(id="cct-composer")

    app = ComposerTestApp()
    async with app.run_test(size=(90, 15)) as pilot:
        composer = app.query_one("#cct-composer")
        await pilot.pause(0.1)

        # 1. Border styles must be heavy blocky 3D (or round fallback) top/left and bottom/right
        assert composer.styles.border_top[0] in ("heavy", "round", "tall")
        assert composer.styles.border_left[0] in ("heavy", "round", "tall")
        assert composer.styles.border_bottom[0] in ("heavy", "round", "tall")
        assert composer.styles.border_right[0] in ("heavy", "round", "tall")

        # 2. Border colors must be vibrant visible colors, not black shadow shading
        top_color = composer.styles.border_top[1].hex
        bot_color = composer.styles.border_bottom[1].hex
        assert bot_color.lower() not in ("#000000", "#10121a")
        assert top_color.lower() not in ("#000000", "#10121a")

        # 3. Status pill and icon buttons inside composer must have 3D tactile styling without ugly block characters
        status = app.query_one("#cct-center-status")
        assert status.styles.background is not None
        attach_btn = app.query_one("#btn-attach")
        assert attach_btn.styles.background is not None
        send_btn = app.query_one("#btn-send")
        assert send_btn.styles.background is not None

        # 4. Verify rendered lines have 3D border characters and NO block shading (U+2581, U+2594, U+258E, U+2588)
        lines = composer.render_lines(composer.region)
        all_text = "".join("".join(s.text for s in row) for row in lines)
        assert any(c in all_text for c in ("┏", "━", "┓", "┃", "┛", "┗", "╭", "╰", "│", "╮", "─"))
        assert "▁" not in all_text
        assert "▔" not in all_text
        assert "▎" not in all_text
        assert "█" not in all_text


@pytest.mark.anyio
async def test_dashboard_and_sidebar_3d_bevel_buttons():
    from textual.app import App, ComposeResult
    from calc_terminal.ui.dashboard import WelcomeDashboard
    from calc_terminal.ui.sidebar import Explorer
    from calc_terminal.ui import theme_css
    from calc_terminal.ui.app import _COMPONENT_CSS

    class Button3DTestApp(App):
        CSS = theme_css.BASE_CSS + _COMPONENT_CSS
        def get_css_variables(self):
            v = dict(super().get_css_variables())
            v.update(theme_css.css_variables())
            return v

        def compose(self) -> ComposeResult:
            yield WelcomeDashboard([], "0.7.9", "test-model", 0)
            yield Explorer()

    app = Button3DTestApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.1)

        # 1. Dashboard quick action buttons must have 3D blocky heavy bevels with top highlight
        dash_btn = app.query_one(".cct-dash-action")
        assert dash_btn.styles.border_top[0] in ("heavy", "round", "tall")
        assert dash_btn.styles.border_left[0] in ("heavy", "round", "tall")
        assert dash_btn.styles.border_bottom[0] in ("heavy", "round", "tall")
        assert dash_btn.styles.border_right[0] in ("heavy", "round", "tall")
        # Top border should be lighter/highlight
        assert dash_btn.styles.border_top[1].hex.lower() not in ("#000000", "#10121a")

        # 2. Sidebar open folder button must have 3D blocky heavy bevels with top highlight
        side_btn = app.query_one("#cct-open-folder-btn")
        assert side_btn.styles.border_top[0] in ("heavy", "round", "tall")
        assert side_btn.styles.border_left[0] in ("heavy", "round", "tall")
        assert side_btn.styles.border_bottom[0] in ("heavy", "round", "tall")
        assert side_btn.styles.border_right[0] in ("heavy", "round", "tall")
        assert side_btn.styles.border_top[1].hex.lower() not in ("#000000", "#10121a")





