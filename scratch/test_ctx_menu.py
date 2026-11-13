import sys
sys.path.insert(0, ".")
import asyncio
from textual.app import App
from calc_terminal.ui.context_menu import MessageContextMenu, AI_MENU_ITEMS

class TestApp(App):
    def on_mount(self):
        self.push_screen(MessageContextMenu(AI_MENU_ITEMS, origin=(10, 3)))

async def run():
    app = TestApp()
    async with app.run_test(size=(60, 20)) as pilot:
        await pilot.pause()
        svg = app.export_screenshot()
        with open("scratch/test_context_menu_render.svg", "w", encoding="utf-8") as f:
            f.write(svg)

asyncio.run(run())
