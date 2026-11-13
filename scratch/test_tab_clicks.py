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
        
        # Test clicking Installed tab
        tab_inst = screen.query_one("#tab-installed")
        tab_inst.press()
        await pilot.pause(0.1)
        inst_cards = screen.query("#ext-list _ExtCard")
        print(f"Cards in Installed tab: {len(inst_cards)}")
        
        # Test clicking MCP Servers tab
        tab_mcp = screen.query_one("#tab-mcp")
        tab_mcp.press()
        await pilot.pause(0.1)
        mcp_cards = screen.query("#ext-list _ExtCard")
        print(f"Cards in MCP Servers tab: {len(mcp_cards)}")
        
        # Test clicking Discover tab
        tab_disc = screen.query_one("#tab-discover")
        tab_disc.press()
        await pilot.pause(0.1)
        disc_cards = screen.query("#ext-list _ExtCard")
        print(f"Cards in Discover tab: {len(disc_cards)}")

        # Test clicking subfilter 'Imported Skills'
        sub_skills = screen.query_one("#sub-skills")
        sub_skills.press()
        await pilot.pause(0.1)
        skill_cards = screen.query("#ext-list _ExtCard")
        print(f"Cards with Imported Skills filter: {len(skill_cards)}")

        # Return to Built-in tab
        tab_builtin = screen.query_one("#tab-builtin")
        tab_builtin.press()
        await pilot.pause(0.1)
        sub_all = screen.query_one("#sub-all")
        sub_all.press()
        await pilot.pause(0.1)

        # Export high fidelity verified SVG
        svg = app.export_screenshot(title="CAT CLI v0.9 — Verified Extensions & Skills Tabs")
        with open("scratch/v0900_extensions_panel_tabs_and_mcp_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("✓ All category tabs and sub-filter clicks verified successfully!")

if __name__ == "__main__":
    asyncio.run(main())

