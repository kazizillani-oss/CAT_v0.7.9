"""
Unit tests for Header 3D Effects, Portrait Header Restoration,
Extensions Panel 3D Redesign, and Dialog Button Layouts.
"""

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Static, Input
from textual.containers import Vertical, Horizontal

from calc_terminal.ui import theme_css
from calc_terminal.ui.app import _COMPONENT_CSS
from calc_terminal.ui.header import BrandHeader, MenuButton, Logo, PermissionPill, NavPanel
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui.sidebar import RecentWorkspacesScreen, OpenWorkspaceScreen
from calc_terminal.ui.agent_menu import AgentModeMenu, _AgentMenuRow, _ManageAgentsRow
from calc_terminal.ui.command_palette_modal import CommandPaletteModal


class BaseThemedApp(App):
    CSS = theme_css.BASE_CSS + _COMPONENT_CSS

    def get_css_variables(self):
        variables = dict(super().get_css_variables())
        variables.update(theme_css.css_variables())
        return variables


class PortraitHeaderApp(BaseThemedApp):
    def compose(self) -> ComposeResult:
        yield BrandHeader()


class LandscapeHeaderApp(BaseThemedApp):
    def compose(self) -> ComposeResult:
        yield BrandHeader()


class ExtPanelApp(BaseThemedApp):
    CSS = theme_css.BASE_CSS

    def compose(self) -> ComposeResult:
        yield ExtensionsPanel()


class RecentWsApp(BaseThemedApp):
    CSS = theme_css.BASE_CSS

    def compose(self) -> ComposeResult:
        yield RecentWorkspacesScreen()


class OpenWsApp(BaseThemedApp):
    CSS = theme_css.BASE_CSS

    def compose(self) -> ComposeResult:
        yield OpenWorkspaceScreen()


@pytest.mark.anyio
async def test_portrait_header_restoration_and_controls():
    """Verify BrandHeader is fully visible and correctly sized in portrait mode (w=48)."""
    app = PortraitHeaderApp()
    async with app.run_test(size=(48, 40)) as pilot:
        await pilot.pause(0.05)
        hdr = app.query_one(BrandHeader)

        # 1. Header must remain mounted and displayed
        assert hdr.is_attached
        assert hdr.display is True

        # 2. Header must have height 4 (3 lines of controls + 1 line border)
        assert hdr.styles.height.value == 4.0

        # 3. Portrait controls must be mounted and displayed
        menu_btn = hdr.query_one(MenuButton)
        pill = hdr.query_one(PermissionPill)
        exp_btn = hdr.query_one("#cct-header-explorer-btn", Button)
        w_right = hdr.query_one("#cct-header-right", Static)

        assert menu_btn.display is True
        assert pill.display is True
        # In portrait mode, the explorer toggle button is displayed instead of full path
        assert exp_btn.display is True
        assert w_right.display is False


@pytest.mark.anyio
async def test_landscape_header_3d_controls():
    """Verify BrandHeader controls in landscape mode have 3D keycaps and correct layout."""
    app = LandscapeHeaderApp()
    async with app.run_test(size=(120, 35)) as pilot:
        await pilot.pause(0.05)
        hdr = app.query_one(BrandHeader)

        assert hdr.is_attached
        assert hdr.display is True
        assert hdr.styles.height.value == 4.0

        # In landscape mode, full workspace path chip is displayed
        w_right = hdr.query_one("#cct-header-right", Static)
        exp_btn = hdr.query_one("#cct-header-explorer-btn", Button)
        assert w_right.display is True
        assert exp_btn.display is False

        # Verify 3D bevel definitions exist in _COMPONENT_CSS
        assert "border-top: tall #6b7596;" in _COMPONENT_CSS
        assert "border-left: tall #565f7c;" in _COMPONENT_CSS
        assert "border-bottom: tall #0e0f17;" in _COMPONENT_CSS
        assert "border-right: tall #13141f;" in _COMPONENT_CSS


@pytest.mark.anyio
async def test_extensions_panel_3d_and_responsiveness():
    """Verify ExtensionsPanel 3D chassis, card bevels, and compact mode."""
    app = ExtPanelApp()
    async with app.run_test(size=(90, 30)) as pilot:
        await pilot.pause(0.05)
        panel = app.query_one(ExtensionsPanel)

        # 1. Dialog chassis must be mounted
        box = panel.query_one("#ext-box")
        assert box.is_attached

        # 2. Close button has 3D ruby keycap styling
        close_btn = panel.query_one("#ext-close", Button)
        assert close_btn.is_attached

        # 3. Action buttons present
        gh_btn = panel.query_one("#ext-gh-install-btn", Button)
        assert gh_btn.is_attached
        close2_btn = panel.query_one("#ext-close2", Button)
        assert close2_btn.is_attached

        # 4. CSS contains 3D raised keycaps for cards & actions
        assert ".ext-card" in ExtensionsPanel.CSS
        assert "border-top: solid #cdd6f4;" in ExtensionsPanel.CSS
        assert ".ext-card-actions Button" in ExtensionsPanel.CSS
        assert ".cct-compact" in ExtensionsPanel.CSS


@pytest.mark.anyio
async def test_dialog_close_and_action_buttons():
    """Verify RecentWorkspaces and OpenWorkspace 3D close and bottom button layout."""
    # Test RecentWorkspaces
    app_rws = RecentWsApp()
    async with app_rws.run_test(size=(80, 25)) as pilot:
        await pilot.pause(0.05)
        rws = app_rws.query_one(RecentWorkspacesScreen)
        close_btn = rws.query_one("#cct-recentws-close", Button)
        assert close_btn.is_attached

        clear_btn = rws.query_one("#cct-recentws-clear", Button)
        cancel_btn = rws.query_one("#cct-recentws-cancel", Button)
        open_btn = rws.query_one("#cct-recentws-open", Button)
        assert clear_btn.is_attached
        assert cancel_btn.is_attached
        assert open_btn.is_attached

    # Test OpenWorkspace
    app_ows = OpenWsApp()
    async with app_ows.run_test(size=(80, 25)) as pilot:
        await pilot.pause(0.05)
        ows = app_ows.query_one(OpenWorkspaceScreen)
        close_btn = ows.query_one("#ows-close-btn", Button)
        assert close_btn.is_attached


class AgentMenuApp(BaseThemedApp):
    def compose(self) -> ComposeResult:
        yield AgentModeMenu()


class NavPanelApp(BaseThemedApp):
    def compose(self) -> ComposeResult:
        yield NavPanel()


class CmdModalApp(BaseThemedApp):
    def compose(self) -> ComposeResult:
        yield CommandPaletteModal()


@pytest.mark.anyio
async def test_agent_mode_menu_tall_bevel_and_docked_footer():
    """Verify Kitties section popup has tall bevel border, close button, and docked footer."""
    app = AgentMenuApp()
    async with app.run_test(size=(80, 25)) as pilot:
        await pilot.pause(0.05)
        menu = app.query_one(AgentModeMenu)
        box = menu.query_one("#cct-agentmenu-box")
        assert box.styles.border_top[0] == "tall"
        assert box.styles.border_left[0] == "tall"
        assert box.styles.border_bottom[0] == "tall"
        assert box.styles.border_right[0] == "tall"

        # Close button present in titlebar
        titlebar = menu.query_one("#cct-agentmenu-titlebar")
        assert titlebar is not None
        close_btn = menu.query_one("#cct-agentmenu-close", Button)
        assert close_btn is not None

        # Scrollable list is a VerticalScroll
        list_scroll = menu.query_one("#cct-agentmenu-list")
        assert list_scroll.__class__.__name__ == "VerticalScroll"

        # Docked footer with manage row
        footer = menu.query_one("#cct-agentmenu-footer")
        assert footer is not None
        manage_row = menu.query_one(_ManageAgentsRow)
        assert manage_row is not None


@pytest.mark.anyio
async def test_navmenu_and_menubutton_tall_bevel():
    """Verify MenuButton and NavPanel dropdown have tall bevel borders."""
    app = LandscapeHeaderApp()
    async with app.run_test(size=(100, 30)) as pilot:
        await pilot.pause(0.05)
        menu_btn = app.query_one(MenuButton)
        assert menu_btn.styles.border_top[0] == "tall"
        assert menu_btn.styles.border_left[0] == "tall"

    app_nav = NavPanelApp()
    async with app_nav.run_test(size=(80, 25)) as pilot:
        await pilot.pause(0.05)
        nav_box = app_nav.query_one("#cct-navmenu-box")
        assert nav_box.styles.border_top[0] == "tall"
        assert nav_box.styles.border_left[0] == "tall"


@pytest.mark.anyio
async def test_command_palette_modal_tall_bevel():
    """Verify CommandPaletteModal dialog chassis uses tall bevel border."""
    app_cmd = CmdModalApp()
    async with app_cmd.run_test(size=(80, 25)) as pilot:
        await pilot.pause(0.05)
        cmd_box = app_cmd.query_one("#cct-cmd-modal-box")
        assert cmd_box.styles.border_top[0] == "tall"
        assert cmd_box.styles.border_left[0] == "tall"


class PermMenuApp(BaseThemedApp):
    def compose(self) -> ComposeResult:
        yield Static("Main")
    def on_mount(self):
        from calc_terminal.ui.header import PermissionModeMenu
        self.push_screen(PermissionModeMenu())


@pytest.mark.anyio
async def test_permission_mode_menu_tall_bevel():
    """Verify PermissionModeMenu dialog chassis uses tall bevel border."""
    app_perm = PermMenuApp()
    async with app_perm.run_test(size=(80, 25)) as pilot:
        await pilot.pause(0.05)
        perm_box = app_perm.screen.query_one("#cct-permmenu-box")
        assert perm_box.styles.border_top[0] == "tall"
        assert perm_box.styles.border_left[0] == "tall"


