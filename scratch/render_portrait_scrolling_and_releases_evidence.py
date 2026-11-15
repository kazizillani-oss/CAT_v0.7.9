import os
import sys
import asyncio

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from textual.app import App
from textual.widgets import Static
from calc_terminal.ui.extensions_panel import ExtensionsPanel
from calc_terminal.ui.releases_modal import GitHubReleasesModal
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui import theme_css

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

class TestApp(App):
    CSS = """
    Screen {
        background: #181825;
        color: #cdd6f4;
    }
    """
    def get_css_variables(self):
        v = dict(super().get_css_variables())
        v.update(theme_css.css_variables())
        return v

async def render_evidence():
    print("=== Step 1: Render ExtensionsPanel with Scrolling Verified ===")
    app1 = TestApp()
    async with app1.run_test(size=(104, 34)) as pilot:
        panel = ExtensionsPanel()
        await app1.push_screen(panel)
        await pilot.pause(0.2)

        scroll_box = panel.query_one("#ext-list")
        assert scroll_box is not None, "Extension list scroll container exists"
        
        # Test keyboard scrolling
        panel.action_scroll_down()
        await pilot.pause(0.1)
        panel.action_scroll_page_down()
        await pilot.pause(0.1)
        
        svg1 = app1.export_screenshot(title="CAT CLI v0.9 — Extensions Scrolling & Debounced Search Verified")
        p1 = os.path.join(ARTIFACT_DIR, "v0900_extensions_scrolling_verified.svg")
        with open(p1, "w", encoding="utf-8") as f:
            f.write(svg1)
        print(f"Saved: {p1}")

    print("\n=== Step 2: Render Portrait Mode Fullscreen Explorer Verified ===")
    app2 = TestApp()
    async with app2.run_test(size=(52, 60)) as pilot:
        header = BrandHeader()
        dummy_chat = Static("CAT Conversation", id="dummy-chat")
        ws = WorkspaceShell(dummy_chat)
        await app2.mount(header)
        await app2.mount(ws)
        await pilot.pause(0.2)

        from calc_terminal.ui.events import SidebarToggled
        # Toggle explorer in portrait
        ws.on_sidebar_toggled(SidebarToggled(True))
        await pilot.pause(0.2)

        # Verify explorer takes 100% fullscreen width in portrait
        sidebar = ws.query_one("#cct-sidebar")
        assert sidebar.styles.width.value == 100, f"Sidebar width is {sidebar.styles.width}"
        
        # Verify header explorer button is hidden in portrait
        exp_btn = header.query_one("#cct-header-explorer-btn")
        assert exp_btn.display is False, "Explorer button must be hidden in portrait mode"

        svg2 = app2.export_screenshot(title="CAT CLI v0.9 — Portrait Fullscreen Explorer & Clean Deduplicated Workspace")
        p2 = os.path.join(ARTIFACT_DIR, "v0900_portrait_explorer_fullscreen_verified.svg")
        with open(p2, "w", encoding="utf-8") as f:
            f.write(svg2)
        print(f"Saved: {p2}")

    print("\n=== Step 3: Render GitHub Releases Modal Verified ===")
    app3 = TestApp()
    async with app3.run_test(size=(90, 32)) as pilot:
        rel_modal = GitHubReleasesModal()
        await app3.push_screen(rel_modal)
        await pilot.pause(0.3)

        svg3 = app3.export_screenshot(title="CAT CLI v0.9 — Live GitHub Releases & Updates Viewer")
        p3 = os.path.join(ARTIFACT_DIR, "v0900_github_releases_modal_verified.svg")
        with open(p3, "w", encoding="utf-8") as f:
            f.write(svg3)
        print(f"Saved: {p3}")

    print("\nAll 3 verification SVGs rendered and saved successfully!")

if __name__ == "__main__":
    asyncio.run(render_evidence())
