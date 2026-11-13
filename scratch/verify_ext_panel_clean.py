import asyncio
from textual.app import App
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui import theme_css

class TestApp(App):
    CSS = theme_css.BASE_CSS
    def get_css_variables(self):
        vars_dict = dict(super().get_css_variables())
        vars_dict.update(theme_css.css_variables())
        return vars_dict
    def on_mount(self):
        self.push_screen(ExtensionsPanel())

async def main():
    app = TestApp()
    async with app.run_test(size=(105, 38)) as pilot:
        await pilot.pause(0.2)
        screen = app.screen
        print("Active screen:", type(screen).__name__)
        
        tab_builtin = screen.query_one("#tab-builtin")
        print("tab_builtin:", tab_builtin)
        tab_installed = screen.query_one("#tab-installed")
        print("tab_installed:", tab_installed)
        tab_mcp = screen.query_one("#tab-mcp")
        print("tab_mcp:", tab_mcp)
        tab_discover = screen.query_one("#tab-discover")
        print("tab_discover:", tab_discover)
        
        sub_all = screen.query_one("#sub-all")
        print("sub_all:", sub_all)
        
        cards = screen.query("#ext-list _ExtCard")
        print(f"Cards in active tab: {len(cards)}")
        for c in cards[:4]:
            ext_id = getattr(c, "ext_id", "?")
            btns = [str(b.label) for b in c.query(".ext-card-actions Button")]
            print(f"  {ext_id}: {btns}")

        # Check button heights
        for c in cards:
            for b in c.query(".ext-card-actions Button"):
                assert b.styles.height.value == 3
        print("✓ All card buttons verified height=3 (no clipping)!")

        # Export SVG
        svg = app.export_screenshot(title="CAT CLI v0.9 — Extensions & Skills Overhaul")
        with open("scratch/v0900_extensions_panel_redesign_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("✓ SVG exported successfully!")

if __name__ == "__main__":
    asyncio.run(main())
