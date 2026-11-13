"""
scratch/render_debug_and_input_fixes_verified.py
================================================
Renders SVG visual artifacts for:
1. 3D input area with internal divider (#cct-composer-divider) and tall bevel
2. Bottom status bar with ○ UI tab and opened UI diagnostics popover
3. Sidebar (Explorer) bottom with real-time Debug Information HUD
"""

import os
import sys
sys.path.insert(0, os.path.abspath("."))

from textual.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.sidebar import Explorer
from calc_terminal.ui.statusbar import StatusBar, StatusFields, UIDiagnosticsModal
from calc_terminal.ui import theme_css, app as cct_app

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"


class _FullVisualApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS

    def __init__(self):
        super().__init__()
        self.debug_overlay_enabled = True
        self.status_fields = StatusFields(lambda: {
            "workspace": "CAT_v0.7.9",
            "model_label": "nvidia/nemotron-3-ultra-550b-a55b",
            "simulation": None
        })

    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v

    def compose(self):
        yield Explorer()
        yield StickyComposer(model_label="nvidia/nemotron-3-ultra-550b-a55b")
        yield StatusBar(self.status_fields)


async def main():
    app = _FullVisualApp()
    async with app.run_test(size=(120, 36)) as pilot:
        comp = app.query_one(StickyComposer)
        comp.set_ai_mode("agent")
        await pilot.pause()

        # 1. Capture Full App with Explorer HUD and Composer Divider
        svg1 = app.export_screenshot()
        p1 = os.path.join(ARTIFACT_DIR, "3d_input_and_sidebar_hud_verified.svg")
        with open(p1, "w", encoding="utf-8") as f:
            f.write(svg1)
        with open("scratch/3d_input_and_sidebar_hud_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg1)
        print("Exported:", p1)

        # 2. Push UI Diagnostics Modal
        app.push_screen(UIDiagnosticsModal())
        await pilot.pause()

        svg2 = app.export_screenshot()
        p2 = os.path.join(ARTIFACT_DIR, "bottom_statusbar_ui_modal_verified.svg")
        with open(p2, "w", encoding="utf-8") as f:
            f.write(svg2)
        with open("scratch/bottom_statusbar_ui_modal_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg2)
        print("Exported:", p2)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
