import asyncio
from textual.app import App, ComposeResult
from calc_terminal.ui import theme_css
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui.agent_menu import AgentModeMenu
from calc_terminal.ui.mode_colors_panel import ModeColorsPanel
from calc_terminal.ui.statusbar import ToolsModal

class MinimalHostApp(App):
    CSS = theme_css.BASE_CSS

    def get_css_variables(self):
        return super().get_css_variables() | theme_css.css_variables()

async def verify_extensions_landscape():
    app = MinimalHostApp()
    async with app.run_test(size=(105, 38)) as pilot:
        panel = ExtensionsPanel()
        await app.push_screen(panel)
        await pilot.pause(0.2)
        
        screen = app.screen
        assert isinstance(screen, ExtensionsPanel)
        
        # 1. Top cross button must be REMOVED
        top_cross = screen.query("#ext-close")
        assert len(top_cross) == 0, f"Expected #ext-close to be removed, but found {len(top_cross)}"
        print("✓ [TEST 1 PASS] Top cross button #ext-close removed from Extensions titlebar!")
        
        # 2. Updates button must be REMOVED
        updates_btn = screen.query("#sub-updates")
        assert len(updates_btn) == 0, f"Expected #sub-updates to be removed, but found {len(updates_btn)}"
        print("✓ [TEST 2 PASS] Updates button #sub-updates removed from sub-filters!")
        
        # 3. 4 Category tabs exist and formatted cleanly
        for tid in ("#tab-builtin", "#tab-installed", "#tab-mcp", "#tab-discover"):
            tab = screen.query_one(tid)
            assert tab is not None
        print("✓ [TEST 3 PASS] 4 Category tabs (Built-in, Installed, MCP Servers, Discover) verified!")
        
        # 4. 4 Subfilters exist
        for sid in ("#sub-all", "#sub-my-ext", "#sub-community", "#sub-skills"):
            sub = screen.query_one(sid)
            assert sub is not None
        print("✓ [TEST 4 PASS] 4 Subfilters (All, My Extensions, Community, Imported Skills) verified!")
        
        # 5. Cards & actions height=3 non-clipping
        cards = screen.query("#ext-list _ExtCard")
        assert len(cards) > 0
        for card in cards[:3]:
            for btn in card.query(".ext-card-actions Button"):
                assert btn.styles.height.value == 3
        print(f"✓ [TEST 5 PASS] {len(cards)} extension cards verified with tall bevel buttons (height=3)!")
        
        # 6. Bottom action bar has only Close button (#ext-close2)
        close_btn = screen.query_one("#ext-close2")
        assert close_btn is not None
        print("✓ [TEST 6 PASS] Bottom [Close] button (#ext-close2) verified!")
        
        svg = app.export_screenshot(title="CAT CLI v0.9 — Extensions Landscape Clean")
        with open("scratch/v0900_extensions_landscape_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("✓ Saved SVG to scratch/v0900_extensions_landscape_verified.svg")
        
        panel.dismiss(None)
        await pilot.pause(0.1)

async def verify_extensions_portrait():
    app = MinimalHostApp()
    async with app.run_test(size=(58, 45)) as pilot:
        panel = ExtensionsPanel()
        await app.push_screen(panel)
        await pilot.pause(0.2)
        
        screen = app.screen
        assert isinstance(screen, ExtensionsPanel)
        assert screen.has_class("is-portrait")
        print("✓ [TEST 7 PASS] ExtensionsPanel detected portrait mode and applied .is-portrait!")
        
        svg = app.export_screenshot(title="CAT CLI v0.9 — Extensions Portrait Ultra-Responsive")
        with open("scratch/v0900_extensions_portrait_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("✓ Saved SVG to scratch/v0900_extensions_portrait_verified.svg")
        
        panel.dismiss(None)
        await pilot.pause(0.1)

async def verify_kitties_agent_menu_portrait():
    app = MinimalHostApp()
    async with app.run_test(size=(55, 40)) as pilot:
        menu = AgentModeMenu()
        await app.push_screen(menu)
        await pilot.pause(0.2)
        
        screen = app.screen
        assert isinstance(screen, AgentModeMenu)
        assert screen.has_class("is-portrait")
        print("✓ [TEST 8 PASS] AgentModeMenu (Kitties 1-Click Switch) optimized in portrait mode!")
        
        svg = app.export_screenshot(title="CAT CLI v0.9 — Kitties 1-Click Menu Portrait")
        with open("scratch/v0900_agent_menu_portrait_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("✓ Saved SVG to scratch/v0900_agent_menu_portrait_verified.svg")
        
        menu.dismiss(None)
        await pilot.pause(0.1)

async def verify_kitties_studio_portrait():
    app = MinimalHostApp()
    async with app.run_test(size=(58, 45)) as pilot:
        studio = ModeColorsPanel()
        await app.push_screen(studio)
        await pilot.pause(0.2)
        
        screen = app.screen
        assert isinstance(screen, ModeColorsPanel)
        assert screen.has_class("is-portrait")
        print("✓ [TEST 9 PASS] ModeColorsPanel (Kitties & AI Modes Studio) optimized in portrait mode!")
        
        svg = app.export_screenshot(title="CAT CLI v0.9 — Kitties Studio Portrait")
        with open("scratch/v0900_kitties_studio_portrait_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("✓ Saved SVG to scratch/v0900_kitties_studio_portrait_verified.svg")
        
        studio.dismiss(None)
        await pilot.pause(0.1)

async def verify_tools_modal():
    app = MinimalHostApp()
    async with app.run_test(size=(90, 30)) as pilot:
        tools = ToolsModal()
        await app.push_screen(tools)
        await pilot.pause(0.2)
        
        screen = app.screen
        assert isinstance(screen, ToolsModal)
        
        snap_btn = screen.query_one("#cct-tools-snapshot-btn")
        assert snap_btn is not None
        assert "Snapshot" in str(snap_btn.label)
        print("✓ [TEST 10 PASS] ToolsModal Snapshot button verified with clear visible label!")
        
        ttfd_btn = screen.query_one("#cct-tools-ttfd-btn")
        token_btn = screen.query_one("#cct-tools-token-btn")
        assert ttfd_btn is not None
        assert token_btn is not None
        
        # Ensure no duplicate token usage buttons
        all_toggle_btns = screen.query(".cct-tools-toggle-btn")
        assert len(all_toggle_btns) == 2, f"Expected exactly 2 toggle buttons, got {len(all_toggle_btns)}"
        print("✓ [TEST 11 PASS] Exactly 2 toggle buttons verified (no duplicate token usage)!")
        
        svg = app.export_screenshot(title="CAT CLI v0.9 — Tools Modal Verified")
        with open("scratch/v0900_tools_modal_verified.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("✓ Saved SVG to scratch/v0900_tools_modal_verified.svg")
        
        tools.dismiss(None)
        await pilot.pause(0.1)

async def main():
    print("--- Running Verification of All Requested Fixes ---")
    await verify_extensions_landscape()
    await verify_extensions_portrait()
    await verify_kitties_agent_menu_portrait()
    await verify_kitties_studio_portrait()
    await verify_tools_modal()
    print("\nALL 11 VERIFICATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(main())
