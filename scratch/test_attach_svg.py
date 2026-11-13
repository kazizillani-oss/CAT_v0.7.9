import asyncio
from textual.app import App
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui import theme_css, app as cct_app

class ComposerApp(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS
    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v
    def compose(self):
        yield StickyComposer(id="cct-composer")

async def run():
    for w in (48, 38, 32):
        app = ComposerApp()
        async with app.run_test(size=(w, 25)) as p:
            c = app.query_one("#cct-composer", StickyComposer)
            await p.pause(0.05)
            c.set_model_label("ollama/deepseek-r1:latest")
            await p.pause(0.05)
            btn = app.query_one("#btn-attach")
            btn.styles.padding = (0, 0, 0, 0)
            print("btn.label:", repr(btn.label))
            svg = app.export_screenshot()
            for line in svg.splitlines():
                if "y=\"22" in line or "y=\"21" in line or "y=\"23" in line or "text" in line:
                    if any(c in line for c in ["&#", "\U0001f517", "\u23f1", "➤", "P", "S"]):
                        print("  SVG_LINE:", line)
            has_attach = any(s in svg for s in ("\U0001f517", "&#128279;", "&#x1f517;", "(+)"))
            print(f"w={w} btn.display={btn.display} btn.region={btn.region} has_attach={has_attach}")
            if not has_attach:
                btn_p = app.query_one("#btn-permissions")
                btn_s = app.query_one("#btn-send")
                print(f"  btn_p={btn_p.region} btn_s={btn_s.region}")
                # print snippet of svg where text occurs
                for line in svg.splitlines():
                    if "text" in line and any(c in line for c in ["+", "P", "S", "Ready", "deep"]):
                        print("  LINE:", line.strip())

if __name__ == "__main__":
    asyncio.run(run())
