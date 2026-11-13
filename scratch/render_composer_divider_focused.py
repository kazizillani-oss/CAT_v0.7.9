"""
scratch/render_composer_divider_focused.py
"""
import os, sys
sys.path.insert(0, os.path.abspath("."))
from textual.app import App
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui import theme_css, app as cct_app

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

class _FocusApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS

    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v

    def compose(self):
        yield StickyComposer(model_label="nvidia/nemotron-3-ultra-550b-a55b")

async def main():
    app = _FocusApp()
    async with app.run_test(size=(90, 16)) as pilot:
        comp = app.query_one(StickyComposer)
        comp.set_ai_mode("agent")
        await pilot.pause()
        svg = app.export_screenshot()
        p = os.path.join(ARTIFACT_DIR, "3d_input_divider_focused_verified.svg")
        with open(p, "w", encoding="utf-8") as f:
            f.write(svg)
        with open("scratch/3d_input_divider_focused_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("Exported:", p)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

