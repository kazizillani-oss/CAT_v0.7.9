import asyncio
from unittest.mock import MagicMock
from textual.app import App
from textual.containers import Vertical
from calc_terminal.ui import theme_css, app as cct_app
from calc_terminal.ui.header import BrandHeader, NavPanel, PermissionModeMenu
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.session_tabs import ChatSessionTabBar
from calc_terminal.ui.statusbar import StatusBar, StatusFields
from calc_terminal.ui.agent_menu import AgentModeMenu
from calc_terminal.ui.chats_panel import ChatsPanel
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui.command_palette_modal import CommandPaletteModal
from calc_terminal.ui.whats_new_modal import WhatsNewModal

class InputHeaderHarnessApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS

    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v

    def compose(self):
        yield BrandHeader()
        yield ChatSessionTabBar()
        yield StickyComposer(model_label="nvidia/nemotron-3-ultra-550b-a55b")
        yield StatusBar(StatusFields(lambda: {"workspace": "CAT_v0.7.9", "model_label": "nvidia/nemotron-3-ultra-550b-a55b"}))

class ModalHarnessApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS

    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v

    def __init__(self, screen_cls, **kwargs):
        super().__init__()
        self.screen_cls = screen_cls
        self.kwargs = kwargs

    def on_mount(self):
        self.push_screen(self.screen_cls(**self.kwargs))

async def capture(app_cls, out_file, size=(100, 28), **kwargs):
    if issubclass(app_cls, ModalHarnessApp):
        app = app_cls(**kwargs)
    else:
        app = app_cls()
    async with app.run_test(size=size) as pilot:
        await pilot.pause(0.08)
        svg = app.export_screenshot()
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Captured {out_file}")

async def main():
    await capture(InputHeaderHarnessApp, "scratch/3d_input_area_and_header_verified.svg", size=(100, 22))
    await capture(ModalHarnessApp, "scratch/3d_kitties_menu_verified.svg", size=(80, 25), screen_cls=AgentModeMenu)
    await capture(ModalHarnessApp, "scratch/3d_whats_new_modal_verified.svg", size=(80, 25), screen_cls=WhatsNewModal)
    await capture(ModalHarnessApp, "scratch/3d_main_menu_verified.svg", size=(74, 25), screen_cls=NavPanel)
    await capture(ModalHarnessApp, "scratch/3d_perm_menu_verified.svg", size=(74, 25), screen_cls=PermissionModeMenu)
    await capture(ModalHarnessApp, "scratch/3d_commands_modal_verified.svg", size=(80, 25), screen_cls=CommandPaletteModal)
    await capture(ModalHarnessApp, "scratch/3d_extensions_panel_verified.svg", size=(80, 25), screen_cls=ExtensionsPanel)
    await capture(ModalHarnessApp, "scratch/3d_chats_panel_verified.svg", size=(80, 25), screen_cls=ChatsPanel)

if __name__ == "__main__":
    asyncio.run(main())
