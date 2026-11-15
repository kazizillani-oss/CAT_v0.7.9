import os
import sys
import asyncio

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from textual.app import App, ComposeResult
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui.chats_panel import ChatsPanel
from calc_terminal.ui.statusbar import ToolsModal
from calc_terminal.ui import theme_css

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

class TestHostApp(App):
    CSS = """
    Screen {
        background: #1e1e24;
        color: #e2e8f0;
    }
    """
    def get_css_variables(self):
        vars_dict = dict(super().get_css_variables())
        vars_dict.update(theme_css.css_variables())
        return vars_dict

async def verify_panels():
    # 1. Test ExtensionsPanel in Floating Window (72x22)
    print("\n--- Testing ExtensionsPanel in Floating Window (72x22) ---")
    app1 = TestHostApp()
    async with app1.run_test(size=(72, 22)) as pilot:
        ext_panel = ExtensionsPanel()
        await app1.push_screen(ext_panel)
        await pilot.pause(0.2)

        # Check action bar visibility
        actions = ext_panel.query_one("#ext-actions")
        close_btn = ext_panel.query_one("#ext-close2")
        gh_btn = ext_panel.query_one("#ext-gh-install-btn")
        create_btn = ext_panel.query_one("#ext-create-btn")
        enable_btn = ext_panel.query_one("#ext-enable-all")

        assert actions is not None, "Actions bar must exist"
        assert close_btn is not None, "Close button must exist"
        assert gh_btn is not None, "GitHub Install button must exist"
        assert create_btn is not None, "Create button must exist"
        assert enable_btn is not None, "Enable All button must exist"

        print(f"Floating window Actions region: {actions.region}")
        print(f"Floating window Close btn region: {close_btn.region}")
        assert actions.region.y < 22, f"Actions bar must be within screen height (got y={actions.region.y})"

        # Export SVG for visual verification
        svg1 = app1.export_screenshot()
        svg1_path = os.path.join(ARTIFACT_DIR, "v0900_extensions_floating_verified.svg")
        with open(svg1_path, "w", encoding="utf-8") as f:
            f.write(svg1)
        print(f"✓ Saved floating extensions SVG to: {svg1_path}")

    # 2. Test ExtensionsPanel in Portrait (52x42)
    print("\n--- Testing ExtensionsPanel in Portrait (52x42) ---")
    app2 = TestHostApp()
    async with app2.run_test(size=(52, 42)) as pilot:
        ext_panel = ExtensionsPanel()
        await app2.push_screen(ext_panel)
        await pilot.pause(0.2)

        actions = ext_panel.query_one("#ext-actions")
        close_btn = ext_panel.query_one("#ext-close2")
        print(f"Portrait Actions region: {actions.region}")
        print(f"Portrait Close btn region: {close_btn.region}")
        assert actions.region.y < 42, f"Actions bar must be within portrait screen height (got y={actions.region.y})"

        svg2 = app2.export_screenshot()
        svg2_path = os.path.join(ARTIFACT_DIR, "v0900_extensions_portrait_v2_verified.svg")
        with open(svg2_path, "w", encoding="utf-8") as f:
            f.write(svg2)
        print(f"✓ Saved portrait extensions SVG to: {svg2_path}")

    # 3. Test ChatsPanel in Floating Window (72x22)
    print("\n--- Testing ChatsPanel in Floating Window (72x22) ---")
    app3 = TestHostApp()
    async with app3.run_test(size=(72, 22)) as pilot:
        chats_panel = ChatsPanel()
        await app3.push_screen(chats_panel)
        await pilot.pause(0.2)

        btns = chats_panel.query_one("#chats-btns")
        new_btn = chats_panel.query_one("#chats-new")
        open_btn = chats_panel.query_one("#chats-open")

        assert btns is not None, "Chats buttons bar must exist"
        assert new_btn is not None, "+ New button must exist"
        assert open_btn is not None, "Open button must exist"
        print(f"Floating window Chats btns region: {btns.region}")
        assert btns.region.y < 22, f"Chats btns must be within screen height (got y={btns.region.y})"

        svg3 = app3.export_screenshot()
        svg3_path = os.path.join(ARTIFACT_DIR, "v0900_chats_floating_verified.svg")
        with open(svg3_path, "w", encoding="utf-8") as f:
            f.write(svg3)
        print(f"✓ Saved floating chats SVG to: {svg3_path}")

    # 4. Test ToolsModal
    print("\n--- Testing ToolsModal ---")
    app4 = TestHostApp()
    async with app4.run_test(size=(80, 24)) as pilot:
        tm = ToolsModal()
        await app4.push_screen(tm)
        await pilot.pause(0.2)

        snap = tm.query_one("#cct-tools-snapshot-btn")
        ttfd = tm.query_one("#cct-tools-ttfd-btn")
        token = tm.query_one("#cct-tools-token-btn")

        assert snap is not None, "Snapshot button must exist"
        assert ttfd is not None, "TTFD button must exist"
        assert token is not None, "Token button must exist"

        print(f"Snapshot label: '{snap.label}'")
        print(f"TTFD label: '{ttfd.label}'")
        print(f"Token label: '{token.label}'")

        assert "Snapshot" in str(snap.label)
        assert "Time to first draw" in str(ttfd.label)
        assert "Turn token usage" in str(token.label)

        svg4 = app4.export_screenshot()
        svg4_path = os.path.join(ARTIFACT_DIR, "v0900_tools_modal_v2_verified.svg")
        with open(svg4_path, "w", encoding="utf-8") as f:
            f.write(svg4)
        print(f"✓ Saved ToolsModal SVG to: {svg4_path}")

    print("\n=== ALL TEST RUNS AND EXPORTED SCREENSHOTS PASSED SUCCESSFULLY! ===")

if __name__ == "__main__":
    asyncio.run(verify_panels())
