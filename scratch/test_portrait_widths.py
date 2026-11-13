import asyncio
import pytest
from textual.app import App, ComposeResult
from calc_terminal.ui import theme_css
from calc_terminal.ui.app import _COMPONENT_CSS
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.footer import ComposerFooter

class TestApp(App):
    CSS = theme_css.BASE_CSS + _COMPONENT_CSS
    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v
    def compose(self) -> ComposeResult:
        yield BrandHeader()
        yield StickyComposer(id="cct-composer")

async def run():
    for width in [40, 50, 60, 80]:
        app = TestApp()
        async with app.run_test(size=(width, 25)) as pilot:
            await pilot.pause(0.1)
            composer = app.query_one("#cct-composer", StickyComposer)
            send_btn = app.query_one("#btn-send")
            attach_btn = app.query_one("#btn-attach")
            perm_btn = app.query_one("#btn-permissions")
            left_ctl = app.query_one("#cct-left-controls")
            right_ctl = app.query_one("#cct-right-controls")
            footer = app.query_one("#cct-bottom-row")
            hdr = app.query_one(BrandHeader)
            
            print(f"\n=== WIDTH {width} ===")
            print("Composer region:", composer.region)
            print("Footer region:", footer.region)
            print("Left controls region:", left_ctl.region)
            print("Right controls region:", right_ctl.region)
            print("Send btn region:", send_btn.region, "display:", send_btn.display)
            print("Attach btn region:", attach_btn.region, "display:", attach_btn.display)
            print("Perm btn region:", perm_btn.region, "display:", perm_btn.display)
            
            # Check if send button is cut off or beyond composer
            c_right = composer.region.x + composer.region.width
            f_right = footer.region.x + footer.region.width
            s_right = send_btn.region.x + send_btn.region.width
            print(f"Composer right: {c_right}, Footer right: {f_right}, Send right: {s_right}")
            if s_right > c_right:
                print(f"!!! OVERFLOW DETECTED: send_btn is {s_right - c_right} cells past composer right edge!")

asyncio.run(run())

