import asyncio, re
from calc_terminal.ui import theme_css, app as cct_app
from calc_terminal.ui.header import BrandHeader
from textual.app import App, ComposeResult

class HdrApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS
    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v
    def compose(self) -> ComposeResult:
        yield BrandHeader()

async def main():
    for w in (45, 60, 80):
        app = HdrApp()
        async with app.run_test(size=(w, 8)) as pilot:
            hdr = app.query_one(BrandHeader)
            hdr.on_resize()
            await pilot.pause(0.05)
            svg = app.export_screenshot()
            print(f'=== WIDTH {w} ===')
            lines_dict = {}
            for match in re.finditer(r'<text[^>]*clip-path="url\(#[^)]+-line-(\d+)\)"[^>]*>(.*?)</text>', svg):
                line_idx = int(match.group(1))
                text_content = match.group(2)
                lines_dict.setdefault(line_idx, []).append(text_content)
            for idx in sorted(lines_dict.keys())[:5]:
                print(f'{idx}: {"".join(lines_dict[idx])}')

if __name__ == "__main__":
    asyncio.run(main())
