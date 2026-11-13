import unittest
from unittest.mock import MagicMock
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.extensions_panel import ExtensionsPanel

class TestExtensionsPanelRedesign(unittest.IsolatedAsyncioTestCase):
    async def test_extensions_panel_redesign(self):
        app = CCTApp(MagicMock(), [], MagicMock())
        async with app.run_test(size=(105, 38)) as pilot:
            await pilot.pause(0.1)
            if type(app.screen).__name__ == "WelcomeModal":
                app.pop_screen()
                await pilot.pause(0.1)
            
            panel = ExtensionsPanel()
            await app.push_screen(panel)
            await pilot.pause(0.1)
            
            screen = app.screen
            self.assertIsInstance(screen, ExtensionsPanel)
            
            # Verify 4 Category Tabs
            tab_builtin = screen.query_one("#tab-builtin")
            tab_installed = screen.query_one("#tab-installed")
            tab_mcp = screen.query_one("#tab-mcp")
            tab_discover = screen.query_one("#tab-discover")
            self.assertIsNotNone(tab_builtin)
            self.assertIsNotNone(tab_installed)
            self.assertIsNotNone(tab_mcp)
            self.assertIsNotNone(tab_discover)
            print("✓ 4 Category Tabs verified!")
            
            # Verify top cross button is removed (only bottom close button remains)
            self.assertEqual(len(screen.query("#ext-close")), 0)
            print("✓ Top cross button is removed as requested!")

            # Verify 4 Sub-filters (Updates button removed as requested)
            self.assertIsNotNone(screen.query_one("#sub-all"))
            self.assertIsNotNone(screen.query_one("#sub-my-ext"))
            self.assertIsNotNone(screen.query_one("#sub-community"))
            self.assertIsNotNone(screen.query_one("#sub-skills"))
            self.assertEqual(len(screen.query("#sub-updates")), 0)
            print("✓ 4 Sub-filters verified (Updates button removed)!")
            
            # Verify cards
            cards = screen.query("#ext-list _ExtCard")
            print(f"✓ Cards found in Built-in tab: {len(cards)}")
            self.assertGreater(len(cards), 0)
            
            # Verify action buttons on cards
            for card in cards[:4]:
                action_btns = card.query(".ext-card-actions Button")
                self.assertGreater(len(action_btns), 0)
                for btn in action_btns:
                    self.assertEqual(btn.styles.height.value, 3)
            print("✓ Card action buttons verified tall bevel height=3 (no clipping)!")
            
            # Verify bottom action bar
            bottom_btns = screen.query("#ext-actions Button")
            self.assertEqual(len(bottom_btns), 4)
            print(f"✓ Bottom action bar buttons verified: {[str(b.label) for b in bottom_btns]}")

            # Export SVG
            svg = app.export_screenshot(title="CAT CLI v0.9 — Extensions & Skills Overhaul")
            with open("scratch/v0900_extensions_panel_redesign_verified.svg", "w", encoding="utf-8") as f:
                f.write(svg)
            print("✓ SVG exported to scratch/v0900_extensions_panel_redesign_verified.svg")

            panel.dismiss(None)
            await pilot.pause(0.1)
            app.exit()

if __name__ == "__main__":
    unittest.main()
