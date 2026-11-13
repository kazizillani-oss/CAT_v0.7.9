import os
import sys
import asyncio
from textual.app import App
from textual.widgets import Button

from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.conversation import ConversationView
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.statusbar import StatusBar, StatusFields
from calc_terminal.ui import theme_css, app as cct_app

class VerificationApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS

    def __init__(self, mode="portrait"):
        super().__init__()
        self.mode = mode
        self.status_fields = StatusFields(lambda: {})

    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v

    def compose(self):
        yield BrandHeader()
        yield WorkspaceShell(
            ConversationView(),
            composer=StickyComposer(model_label="nvidia/nemotron")
        )
        yield StatusBar(self.status_fields)

async def main():
    os.makedirs("scratch", exist_ok=True)
    brain_dir = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

    # 1. Portrait Header & Chat Mode (45x30)
    app_port = VerificationApp("portrait")
    async with app_port.run_test(size=(45, 30)) as pilot:
        hdr = app_port.query_one(BrandHeader)
        hdr.add_class("is-portrait")
        shell = app_port.query_one(WorkspaceShell)
        await pilot.pause()

        svg_content = app_port.export_screenshot()
        for out_path in [
            "scratch/v0900_portrait_header_tall_bevel.svg",
            os.path.join(brain_dir, "v0900_portrait_header_tall_bevel.svg")
        ]:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(svg_content)
        print("Exported portrait header tall bevel SVG")

        # Open Explorer in Portrait (Full Screen)
        shell.toggle_sidebar()
        await pilot.pause()
        svg_port_exp = app_port.export_screenshot()
        for out_path in [
            "scratch/v0900_portrait_explorer_fullscreen.svg",
            os.path.join(brain_dir, "v0900_portrait_explorer_fullscreen.svg")
        ]:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(svg_port_exp)
        print("Exported portrait explorer full screen SVG")

    # 2. Landscape Mode (100x26) with Clean Footer & Focused Footer Tab
    app_land = VerificationApp("landscape")
    async with app_land.run_test(size=(100, 26)) as pilot:
        statusbar = app_land.query_one(StatusBar)
        btn_ui = statusbar.query_one("#btn-status-ui", Button)
        btn_ui.focus()
        await pilot.pause()

        svg_land = app_land.export_screenshot()
        for out_path in [
            "scratch/v0900_landscape_clean_footer_and_hover.svg",
            os.path.join(brain_dir, "v0900_landscape_clean_footer_and_hover.svg")
        ]:
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(svg_land)
        print("Exported landscape clean footer and button focus SVG")

if __name__ == "__main__":
    asyncio.run(main())

