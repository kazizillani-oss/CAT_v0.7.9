import asyncio
from unittest.mock import MagicMock
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.header import NavPanel, PermissionModeMenu
from calc_terminal.ui.agent_menu import AgentModeMenu
from calc_terminal.ui.chats_panel import ChatsPanel
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui.command_palette_modal import CommandPaletteModal

async def capture_screen(screen_cls, filename, size=(100, 32), **kwargs):
    repl = MagicMock()
    repl.palette_mode = False
    hist = MagicMock()
    stats = MagicMock()
    app = CCTApp(repl, hist, stats)
    async with app.run_test(size=size) as pilot:
        screen = screen_cls(**kwargs)
        app.push_screen(screen)
        await pilot.pause(0.1)
        svg = app.export_screenshot()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Captured {filename}")

async def capture_main_app(filename, size=(100, 32)):
    repl = MagicMock()
    repl.palette_mode = False
    hist = MagicMock()
    stats = MagicMock()
    app = CCTApp(repl, hist, stats)
    async with app.run_test(size=size) as pilot:
        await pilot.pause(0.15)
        svg = app.export_screenshot()
        with open(filename, "w", encoding="utf-8") as f:
            f.write(svg)
        print(f"Captured {filename}")

async def main():
    await capture_main_app("scratch/3d_input_area_and_header_verified.svg")
    await capture_screen(NavPanel, "scratch/3d_main_menu_verified.svg")
    await capture_screen(PermissionModeMenu, "scratch/3d_perm_menu_verified.svg")
    await capture_screen(AgentModeMenu, "scratch/3d_kitties_menu_verified.svg")
    await capture_screen(ChatsPanel, "scratch/3d_chats_panel_verified.svg")
    await capture_screen(ExtensionsPanel, "scratch/3d_extensions_panel_verified.svg")
    await capture_screen(CommandPaletteModal, "scratch/3d_commands_modal_verified.svg")

if __name__ == "__main__":
    asyncio.run(main())
