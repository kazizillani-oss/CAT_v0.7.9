# scratch/render_visual_verification.py
import asyncio
from textual.app import App, ComposeResult
from textual.widgets import Button, Static, TextArea
from textual.containers import Vertical, Horizontal

from calc_terminal.ui import theme_css
from calc_terminal.ui.app import _COMPONENT_CSS
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.sidebar import RecentWorkspacesScreen

class VisualApp(App):
    CSS = theme_css.BASE_CSS + _COMPONENT_CSS

    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v

    def compose(self) -> ComposeResult:
        yield BrandHeader()
        yield StickyComposer(id="cct-composer")

async def render():
    # 1. Landscape 100x25
    app1 = VisualApp()
    async with app1.run_test(size=(100, 25)) as pilot:
        await pilot.pause(0.1)
        svg = app1.export_screenshot()
        with open(r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18\composer_and_header_landscape_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("Exported landscape SVG")

    # 2. Portrait 50x30
    app2 = VisualApp()
    async with app2.run_test(size=(50, 30)) as pilot:
        await pilot.pause(0.1)
        svg = app2.export_screenshot()
        with open(r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18\composer_and_header_portrait_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("Exported portrait SVG")

    # 3. Recent Workspaces Dialog 54x25
    class RwsApp(App):
        CSS = theme_css.BASE_CSS + _COMPONENT_CSS
        def get_css_variables(self):
            v = dict(super().get_css_variables())
            v.update(theme_css.css_variables())
            return v
        def compose(self) -> ComposeResult:
            yield Static("background")

    app3 = RwsApp()
    async with app3.run_test(size=(54, 25)) as pilot:
        await app3.push_screen(RecentWorkspacesScreen())
        await pilot.pause(0.1)
        svg = app3.export_screenshot()
        with open(r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18\recent_workspaces_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("Exported recent workspaces SVG")

asyncio.run(render())
