"""Headless verify: real panels with the fit_dialog helper."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from textual.app import App
from textual.widgets import Button
from textual.containers import ScrollableContainer


def make_probe_cls():
    from calc_terminal.ui import theme_css

    class Probe(App):
        CSS = theme_css.BASE_CSS

        def __init__(self, screen_factory):
            super().__init__()
            self._factory = screen_factory

        def compose(self):
            yield from []

        def get_css_variables(self):
            variables = dict(super().get_css_variables())
            variables.update(theme_css.css_variables())
            return variables

        async def on_mount(self):
            self.push_screen(self._factory())

    return Probe


async def check(size, name, fac, probe_cls, setup=None):
    app = probe_cls(fac)
    async with app.run_test(size=size, headless=True) as pilot:
        for _ in range(6):
            await pilot.pause()
            await asyncio.sleep(0.15)
        if setup is not None:
            await setup(app.screen)
            for _ in range(6):
                await pilot.pause()
                await asyncio.sleep(0.15)
        screen = app.screen
        full_map = screen._compositor.full_map

        def mreg(w):
            g = full_map.get(w)
            return g.region if g is not None else None

        box = screen.query_one(f"#{name}-box")
        box_r = mreg(box)
        vh, vw = screen.size.height, screen.size.width

        def ok(b):
            b_r = mreg(b)
            if b_r is None or box_r is None:
                return False
            if box_r.contains_region(b_r):
                return True
            # content scrolled out of a scrollable area inside the box is fine
            for a in b.ancestors_with_self:
                if a is box:
                    break
                if str(getattr(a.styles, "overflow_y", "")) == "auto":
                    a_r = mreg(a)
                    if a_r is not None and box_r.contains_region(a_r):
                        return True
            return False

        inside, outside = [], []
        for b in screen.query(Button):
            b_r = mreg(b)
            if b_r is None or b_r.height <= 0:
                continue
            if ok(b):
                inside.append(b.id)
            else:
                outside.append((b.id, b_r.y, b_r.bottom))
        # overlap check: a button must never stick out of its own row
        # (the old height-3-with-padding rows overflowed into the footer)
        overflow = []
        for b in screen.query(Button):
            b_r = mreg(b)
            if b_r is None or b_r.height <= 0 or b.display is False:
                continue
            parent = b.parent
            if parent is None:
                continue
            p_r = mreg(parent)
            if p_r is not None and p_r.contains_region(b_r):
                continue
            # inside a scrollable area: scrolled content may exceed the row
            sc = parent
            while sc is not None and sc is not box:
                if str(getattr(sc.styles, "overflow_y", "")) == "auto":
                    break
                sc = sc.parent
            if sc is not None and sc is not box:
                sc_r = mreg(sc)
                if sc_r is not None and sc_r.contains_region(b_r):
                    continue
            overflow.append((b.id, b_r.y, b_r.bottom, parent.id, p_r))
        on_screen = all(
            (mreg(b) is None) or mreg(b).bottom <= vh for b in screen.query(Button))
        content_driven = box_r is not None and box_r.height < 0.85 * vh
        fits_width = box_r is None or box_r.width <= vw
        print(f"{name} @ {vw}x{vh}: box={box_r} box_fits={box_r.height <= vh} "
              f"fits_width={fits_width} content_driven={content_driven} "
              f"buttons_on_screen={on_screen}")
        if outside:
            print(f"   OUTSIDE buttons: {outside}")
        if overflow:
            print(f"   !! ROW-OVERFLOW buttons (sticking out of their row): {overflow}")
        if not inside:
            print("   !! NO buttons inside box")


async def main():
    Probe = make_probe_cls()
    from calc_terminal.ui.mcp_panel import McpServersPanel, _AddMcpForm
    from calc_terminal.ui.backup_panel import BackupProvidersPanel, _AddProviderForm
    from calc_terminal.ui.attach_panel import AttachPanel
    from calc_terminal.ui.activity_panel import ActivityPanel
    from calc_terminal.ui.personalization_panel import PersonalizationPanel
    from calc_terminal.ui.welcome_modal import WelcomeModal

    async def setup_attach(screen):
        screen._cwd = os.path.dirname(os.path.abspath(__file__))
        screen._enter_mode("files")

    panels = [
        ("mcp", lambda: McpServersPanel(), None),
        ("amf", lambda: _AddMcpForm(), None),
        ("bpp", lambda: BackupProvidersPanel(), None),
        ("apf", lambda: _AddProviderForm(), None),
        ("ap", lambda: AttachPanel(), setup_attach),
        ("act", lambda: ActivityPanel(), None),
        ("pp", lambda: PersonalizationPanel(), None),
        ("wm", lambda: WelcomeModal(), None),
    ]
    for size in [(100, 40), (100, 24), (80, 24)]:
        for name, fac, setup in panels:
            try:
                await check(size, name, fac, Probe, setup=setup)
            except Exception as e:
                print(f"{name} @ {size}: ERROR {type(e).__name__}: {e}")
        print()


if __name__ == "__main__":
    asyncio.run(main())
