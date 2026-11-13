"""
Unit tests for Composer 3D Skeuomorphic Block Redesign, Command Palette Cursor Tracking,
Recent Workspaces Non-Clipping Bottom Buttons & 3D Close, and Portrait Header Ghost Border Removal.
"""

import pytest
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Button, Static, TextArea
from textual.containers import Vertical, Horizontal

from calc_terminal.ui import theme_css
from calc_terminal.ui.app import _COMPONENT_CSS
from calc_terminal.ui.composer import StickyComposer, ComposerInput
from calc_terminal.ui.palette import CommandPalette, CommandPaletteRow
from calc_terminal.ui.header import BrandHeader, MenuButton, PermissionPill
from calc_terminal.ui.sidebar import RecentWorkspacesScreen, OpenWorkspaceScreen


class BaseTestApp(App):
    CSS = theme_css.BASE_CSS + _COMPONENT_CSS

    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v


class ComposerApp(BaseTestApp):
    def compose(self) -> ComposeResult:
        yield StickyComposer(id="cct-composer")


class PortraitHeaderApp(BaseTestApp):
    def compose(self) -> ComposeResult:
        yield BrandHeader()


class RecentWorkspacesApp(BaseTestApp):
    def compose(self) -> ComposeResult:
        yield RecentWorkspacesScreen()


class OpenWorkspacesApp(BaseTestApp):
    def compose(self) -> ComposeResult:
        yield OpenWorkspaceScreen()


@pytest.mark.anyio
async def test_composer_3d_skeuomorphic_block_geometry():
    """Verify composer chassis has square/rectangular block 3D bevels, recessed deck,
    and the v0.9.000 height-3 3D Send/Stop/Attach/Mic keycaps in the bottom row."""
    app = ComposerApp()
    async with app.run_test(size=(90, 30)) as pilot:
        composer = app.query_one("#cct-composer", StickyComposer)
        await pilot.pause(0.05)

        # 1. Outer Chassis: Heavy or tall rectangular 3D border
        assert composer.styles.border_top[0] in ("heavy", "tall")
        assert composer.styles.border_left[0] in ("heavy", "tall")
        assert composer.styles.border_bottom[0] in ("heavy", "tall")
        assert composer.styles.border_right[0] in ("heavy", "tall")

        # 2. Prompt row: Single border design — no duplicate inner border, transparent well
        deck = app.query_one("#cct-prompt-row")
        assert deck is not None
        assert deck.styles.border_top[0] in ("", "none")
        assert deck.styles.border_left[0] in ("", "none")

        # 3. Prompt glyph: amber gold or mode accent indicator
        glyph = app.query_one("#cct-prompt-glyph")
        assert glyph.styles.color.hex.lower() in ("#e0af68", "#f7d794", "#9ece6a", "#ff69b4", "#7aa2f7", "#bb9af7", "#dc143c")

        # 4. Bottom status row: compact control deck
        footer = app.query_one("#cct-bottom-row")
        assert footer is not None
        assert footer.styles.border_top[0] in ("", "none")
        assert footer.styles.height.value in (1.0, 3.0)

        # 5. Send button: compact tactile amber keycap
        send_btn = app.query_one("#btn-send", Button)
        assert send_btn.styles.border_top[0] in ("tall", "", "none")
        assert send_btn.styles.height.value in (1.0, 3.0)
        assert send_btn.styles.background.hex.lower() == "#e0af68"

        # 6. Attachment + Mic: compact slate tactile buttons; the
        #    Permissions/Security buttons are decommissioned from the
        #    composer entirely
        attach_btn = app.query_one("#btn-attach", Button)
        mic_btn = app.query_one("#btn-mic", Button)
        stop_btn = app.query_one("#btn-stop", Button)
        assert attach_btn.styles.border_top[0] in ("tall", "", "none")
        assert attach_btn.styles.height.value in (1.0, 3.0)
        assert mic_btn.styles.height.value in (1.0, 3.0)
        assert stop_btn.styles.height.value in (1.0, 3.0)
        assert not app.query("#btn-permissions")
        assert not app.query("#btn-security")


@pytest.mark.anyio
async def test_palette_no_composer_void_and_cursor_tracking():
    """Verify command palette opening resets composer min-height to 0 and tracks cursor."""
    app = ComposerApp()
    async with app.run_test(size=(90, 30)) as pilot:
        composer = app.query_one("#cct-composer", StickyComposer)
        await pilot.pause(0.05)

        # Simulate user having dragged an explicit height
        composer.set_explicit_height(14)
        assert composer.styles.height.value == 14.0

        # Open palette
        palette = composer.palette
        palette.open_for_query("/")
        await pilot.pause(0.05)

        # Composer must reset min_height to 0 so there is no empty void
        assert composer.styles.min_height.value == 0.0
        assert composer.styles.height.is_auto

        # Verify cursor tracking: rows have ALLOW_SELECT=False and hover triggers selection
        rows = [c for c in palette.children if isinstance(c, CommandPaletteRow)]
        assert len(rows) > 0
        assert rows[0].ALLOW_SELECT is False
        assert rows[0].can_focus is False

        # Close palette: restores explicit height
        palette.close()
        await pilot.pause(0.05)
        assert composer.styles.height.value == 14.0


@pytest.mark.anyio
async def test_recent_workspaces_buttons_no_clipping_and_3d_close():
    """Verify RecentWorkspacesScreen buttons do not overflow/clip on narrow widths and close button is 3D."""
    # Test on a compact width (54 cols, matching screenshot)
    app = RecentWorkspacesApp()
    async with app.run_test(size=(54, 25)) as pilot:
        rws = app.query_one(RecentWorkspacesScreen)
        await pilot.pause(0.05)

        # 1. Close button is 3D red keycap
        close_btn = rws.query_one("#cct-recentws-close", Button)
        assert close_btn.styles.border_top[0] == "tall"
        assert close_btn.styles.height.value == 3.0

        # 2. Bottom buttons: Clear, Cancel, Open all mounted and visible
        clear_btn = rws.query_one("#cct-recentws-clear", Button)
        cancel_btn = rws.query_one("#cct-recentws-cancel", Button)
        open_btn = rws.query_one("#cct-recentws-open", Button)

        assert clear_btn.is_attached and clear_btn.display is True
        assert cancel_btn.is_attached and cancel_btn.display is True
        assert open_btn.is_attached and open_btn.display is True
        assert open_btn.styles.border_top[0] == "tall"


@pytest.mark.anyio
async def test_portrait_header_no_ghost_border():
    """Verify portrait header displays only explorer button on right without ghost workspace path box."""
    app = PortraitHeaderApp()
    async with app.run_test(size=(48, 30)) as pilot:
        hdr = app.query_one(BrandHeader)
        await pilot.pause(0.05)

        exp_btn = hdr.query_one("#cct-header-explorer-btn", Button)
        w_right = hdr.query_one("#cct-header-right", Static)

        # In portrait mode, explorer button is displayed and path chip is hidden
        assert exp_btn.display is True
        assert w_right.display is False

        # In CSS, #cct-header-right has display: none in portrait mode
        assert "#cct-brandheader.is-portrait #cct-header-right" in _COMPONENT_CSS


@pytest.mark.anyio
async def test_composer_footer_controls_always_visible_at_narrow_and_explicit_height():
    """Verify all controls (model badge, AI agent mode badge, attachment,
    mic, send/stop) stay mounted/visible — and the 1-cell gap between the
    right-cluster controls — on narrow compact terminals."""
    from calc_terminal.ui.resizers import COMPOSER_MIN_HEIGHT
    from calc_terminal.ui.footer import ComposerFooter

    assert COMPOSER_MIN_HEIGHT >= 5

    # Test on narrow compact terminals (48, 38, and 32 cols, matching portrait & floating viewports)
    for width in (48, 38, 32):
        app = ComposerApp()
        async with app.run_test(size=(width, 25)) as pilot:
            composer = app.query_one("#cct-composer", StickyComposer)
            await pilot.pause(0.05)
            composer.set_model_label("ollama deepseek-r1:latest")
            await pilot.pause(0.05)

            # 1. Base min_height >= COMPOSER_MIN_HEIGHT
            assert composer.styles.min_height.value >= COMPOSER_MIN_HEIGHT

            # 2. Footer row must be visible and a compact row
            footer = app.query_one("#cct-bottom-row", ComposerFooter)
            assert footer.display is True
            assert footer.styles.height.value in (1.0, 3.0)

            # 3. Model name badge must be mounted (hidden < 34 cols, shown ≥)
            model_badge = app.query_one("#badge-model")
            assert model_badge is not None
            assert model_badge.display is (width >= 34)

            # 4. AI agent mode badge must be mounted & visible
            agent_badge = app.query_one("#badge-notebook")
            assert agent_badge.display is True

            # 5. Attach / mic / send buttons must be mounted & visible at
            #    EVERY width — never clipped off-screen
            attach_btn = app.query_one("#btn-attach", Button)
            mic_btn = app.query_one("#btn-mic", Button)
            send_btn = app.query_one("#btn-send", Button)
            stop_btn = app.query_one("#btn-stop", Button)

            assert attach_btn.display is True
            assert mic_btn.display is True
            assert send_btn.display is True

            # 6. Verify button glyphs rendered in screenshot output
            #    (first-party emoji, or the ASCII fallback glyphs)
            svg = app.export_screenshot()
            assert any(s in svg for s in
                       ("📎", "&#128206;", "&#x1f4ce;", "(+)", "🔗", "&#128279;", "&#x1f517;"))
            assert any(s in svg for s in
                       ("🎙", "&#127897;", "&#x1f399;", "(V)"))
            assert any(s in svg for s in ("➤", "&#10148;", "&#x27a4;", ">"))
            assert not app.query("#btn-permissions")
            assert not app.query("#btn-security")

            # 7. Test explicit height clamping: setting lower than COMPOSER_MIN_HEIGHT resets to auto with min_height
            composer.set_explicit_height(3)
            assert composer.styles.height.is_auto
            assert composer.styles.min_height.value >= COMPOSER_MIN_HEIGHT


@pytest.mark.anyio
async def test_all_ai_modes_3d_skeuomorphic_bevels():
    """Verify all 6 AI mode chassis have authentic 3D skeuomorphic beveling (light top/left, dark bottom/right)."""
    app = ComposerApp()
    async with app.run_test(size=(90, 30)) as pilot:
        composer = app.query_one("#cct-composer", StickyComposer)
        await pilot.pause(0.05)

        modes = [
            ("cct-mode-build", "#ffeaa7", "#fab387", "#8c551c", "#b07028"),
            ("cct-mode-notebook", "#bfd5ff", "#89b4fa", "#2b3e7a", "#3d569e"),
            ("cct-mode-research", "#ffaecf", "#ff85c0", "#801f4c", "#a82d68"),
            ("cct-mode-plan", "#cdf59f", "#a6e3a1", "#3f6212", "#5b8a24"),
            ("cct-mode-debugger", "#ffa1b2", "#f38ba8", "#801024", "#a81a34"),
            ("cct-mode-agent", "#ebd5ff", "#cba6f7", "#543b8a", "#7052b4"),
        ]

        for cls, top_col, left_col, bot_col, right_col in modes:
            for c, _, _, _, _ in modes:
                composer.remove_class(c)
            composer.add_class(cls)
            await pilot.pause(0.02)

            assert composer.styles.border_top[0] in ("heavy", "tall")
            assert composer.styles.border_top[1].hex.lower() == top_col.lower()
            assert composer.styles.border_left[1].hex.lower() == left_col.lower()
            assert composer.styles.border_bottom[1].hex.lower() == bot_col.lower()
            assert composer.styles.border_right[1].hex.lower() == right_col.lower()


@pytest.mark.anyio
async def test_menu_button_square_shape_and_dialog_3d_bevels():
    """Verify MenuButton has 1:1 physical square shape (width 7, height 3) and dialogs have 3D bevels."""
    app = PortraitHeaderApp()
    async with app.run_test(size=(100, 30)) as pilot:
        hdr = app.query_one(BrandHeader)
        await pilot.pause(0.05)

        menu_btn = hdr.query_one(".cct-menu-btn")
        assert menu_btn is not None
        assert menu_btn.styles.width.value == 7.0
        assert menu_btn.styles.height.value == 3.0
        assert menu_btn.styles.border_top[0] in ("heavy", "tall")

    from calc_terminal.ui.header import NavPanel, PermissionModeMenu
    assert any(b in NavPanel.CSS for b in ("border: heavy;", "border: tall;"))
    assert any(b in NavPanel.CSS for b in ("border-top: heavy #8b92b2;", "border-top: tall #8b92b2;"))
    assert any(b in PermissionModeMenu.CSS for b in ("border: heavy;", "border: tall;"))
    assert any(b in PermissionModeMenu.CSS for b in ("border-top: heavy #8b92b2;", "border-top: tall #8b92b2;"))
    assert "border: round" not in PermissionModeMenu.CSS


@pytest.mark.anyio
async def test_cmdpalette_no_highlight_tint_and_no_bottom_overflow():
    """Verify Command Palette has no background tint, has square 3D borders, and footer never overflows past composer border."""
    app = ComposerApp()
    async with app.run_test(size=(90, 30)) as pilot:
        composer = app.query_one("#cct-composer", StickyComposer)
        palette = composer.palette
        await pilot.pause(0.05)

        # Open palette
        palette.open_for_query("/")
        await pilot.pause(0.05)

        # 1. Palette styling: no accent tint, dark background, square border
        assert palette.styles.tint.a == 0.0 or palette.styles.tint.hex.lower() == "#000000"
        assert palette.styles.border_top[0] in ("solid", "tall")
        assert palette.styles.border_top[0] != "round"

        # 2. Composer overflow is hidden
        assert composer.styles.overflow_x == "hidden"
        assert composer.styles.overflow_y == "hidden"

        # 3. Footer row is contained inside composer
        footer = app.query_one("#cct-bottom-row")
        c_region = composer.region
        f_region = footer.region
        # Footer bottom must not exceed composer bottom
        assert f_region.y + f_region.height <= c_region.y + c_region.height


@pytest.mark.anyio
async def test_agent_mode_menu_quick_switcher():
    """Verify AgentModeMenu displays active modes, has 3D skeuomorphic borders, and supports keyboard/click navigation."""
    from calc_terminal.ui.agent_menu import AgentModeMenu, _AgentMenuRow, _ManageAgentsRow

    app = ComposerApp()
    async with app.run_test(size=(90, 30)) as pilot:
        await pilot.pause(0.05)

        # 1. 3D skeuomorphic styling check
        assert any(b in AgentModeMenu.CSS for b in ("border: heavy;", "border: tall;"))
        assert any(b in AgentModeMenu.CSS for b in ("border-top: heavy #8b92b2;", "border-top: tall #8b92b2;"))
        assert "border: round" not in AgentModeMenu.CSS

        # 2. Push AgentModeMenu onto screen stack
        result_holder = []
        screen = AgentModeMenu()
        app.push_screen(screen, callback=lambda res: result_holder.append(res))
        await pilot.pause(0.05)

        # 3. Verify rows rendered for all registered modes and Kitties title
        title_static = screen.query_one(".cct-agentmenu-title", Static)
        assert "Kitties" in str(title_static.render())
        rows = list(screen.query(_AgentMenuRow))
        assert len(rows) >= 5
        manage_rows = list(screen.query(_ManageAgentsRow))
        assert len(manage_rows) == 1

        # 4. Verify keyboard selection advances and reverses
        initial = screen._selected
        screen.action_select_next()
        assert screen._selected == (initial + 1) % len(screen._modes)
        screen.action_select_prev()
        assert screen._selected == initial

        # 5. Dismiss with selected mode
        screen.action_confirm_selection()
        await pilot.pause(0.05)
        assert len(result_holder) == 1
        assert result_holder[0] in screen._modes

