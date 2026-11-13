import asyncio
from textual.app import App
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui import theme_css, app as cct_app

class A(App):
    CSS = theme_css.BASE_CSS + cct_app._COMPONENT_CSS
    def get_css_variables(self):
        v = super().get_css_variables()
        v.update(theme_css.css_variables())
        return v
    def compose(self):
        yield StickyComposer()

async def t():
    a = A()
    async with a.run_test(size=(80, 20)) as p:
        c = a.query_one(StickyComposer)
        for w in c.query("*"):
            if w.id:
                print(f"{w.id:28}: {w.__class__.__name__:16} {w.region}")

if __name__ == "__main__":
    asyncio.run(t())
