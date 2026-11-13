import asyncio
from unittest.mock import MagicMock
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.extensions_panel import ExtensionsPanel

async def run_test():
    repl_mock = MagicMock()
    stats_mock = MagicMock()
    app = CCTApp(repl_mock, [], stats_mock)
    async with app.run_test(size=(105, 38)) as pilot:
        await pilot.pause(0.2)
        app.push_screen(ExtensionsPanel())
        await pilot.pause(0.3)
        
        screen = app.screen
        assert isinstance(screen, ExtensionsPanel), f"Expected ExtensionsPanel, got {type(screen)}"
        
        # Verify tabs exist
        tab_builtin = screen.query_one("#tab-builtin")
        tab_installed = screen.query_one("#tab-installed")
        tab_mcp = screen.query_one("#tab-mcp")
        tab_discover = screen.query_one("#tab-discover")
        assert tab_builtin is not None
        assert tab_installed is not None
        assert tab_mcp is not None
        assert tab_discover is not None
        print("✓ All 4 top-level category tabs verified!")
        
        # Verify subfilters exist
        sub_all = screen.query_one("#sub-all")
        sub_my = screen.query_one("#sub-my-ext")
        sub_comm = screen.query_one("#sub-community")
        sub_skills = screen.query_one("#sub-skills")
        sub_up = screen.query_one("#sub-updates")
        assert sub_all is not None
        assert sub_my is not None
        assert sub_comm is not None
        assert sub_skills is not None
        assert sub_up is not None
        print("✓ All 5 sub-filters verified!")

        # Verify cards in Built-in tab
        cards = screen.query("#ext-list _ExtCard")
        print(f"Cards found in Built-in tab: {len(cards)}")
        assert len(cards) > 0, "Expected at least 1 card in Built-in tab"
        for card in cards[:6]:
            ext_id = getattr(card, "ext_id", "unknown")
            card_actions = card.query(".ext-card-actions Button")
            btn_labels = [str(b.label) for b in card_actions]
            print(f"  • Card '{ext_id}': actions={btn_labels}")

        # Verify bottom action buttons
        actions = screen.query("#ext-actions Button")
        print(f"Bottom action buttons: {[str(b.label) for b in actions]}")
        assert len(actions) == 4, f"Expected 4 action buttons, got {len(actions)}"
        
        # Test tab switching to MCP Servers
        tab_mcp.press()
        await pilot.pause(0.2)
        mcp_cards = screen.query("#ext-list _ExtCard")
        print(f"Cards in MCP Servers tab: {len(mcp_cards)}")

        # Switch back to Built-in tab
        tab_builtin.press()
        await pilot.pause(0.2)

        # Export screenshot SVG
        svg = app.export_screenshot(title="CAT CLI v0.9 — Extensions & Skills Overhaul")
        with open("scratch/test_extensions_panel_redesign.svg", "w", encoding="utf-8") as f:
            f.write(svg)
        print("✓ SVG screenshot exported successfully to scratch/test_extensions_panel_redesign.svg")

if __name__ == "__main__":
    asyncio.run(run_test())
