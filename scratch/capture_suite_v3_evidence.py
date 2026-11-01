import os
import sys
import asyncio
from playwright.async_api import async_playwright

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.stdout.reconfigure(encoding='utf-8')

from calc_terminal.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.header import BrandHeader, NavPanel
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.palette import CommandPalette
from calc_terminal.ui.nav_screens import ThemesPanel, UserPanel
from calc_terminal.ui.sidebar import OpenWorkspaceScreen, RecentWorkspacesScreen

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

async def svg_to_png(page, svg_path, png_path):
    if not os.path.exists(svg_path):
        return
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_content = f.read()
    html = f"<!DOCTYPE html><html><body style='margin:0;background:#14151f;'>{svg_content}</body></html>"
    await page.set_content(html)
    el = await page.query_selector("svg")
    if el:
        await el.screenshot(path=png_path)
        print(f"  [Evidence Rendered] {os.path.basename(png_path)}")

async def capture_all_v3():
    print("=" * 70)
    print("CAPTURING HIGH-FIDELITY VISUAL EVIDENCE FOR V3 ULTRA-RESPONSIVE SUITE")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        stats = {"solved": 0, "provider": "none", "model": "none"}

        # 1. Landscape Header Repaired
        print("\n1. Capturing Landscape Header...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "landscape_header_repaired.svg")
            png = os.path.join(ARTIFACT_DIR, "landscape_header_repaired.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 2. Portrait NavPanel with MCP & Backup Providers
        print("\n2. Capturing Portrait NavPanel with MCP & Backup Providers...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(70, 42)) as pilot:
            await pilot.pause()
            panel = NavPanel()
            app.push_screen(panel)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_navpanel_mcp_backup.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_navpanel_mcp_backup.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 3. Portrait Command Palette
        print("\n3. Capturing Portrait Command Palette...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(70, 40)) as pilot:
            await pilot.pause()
            comp = app.query_one(StickyComposer)
            palette = comp.query_one(CommandPalette)
            palette.open_for_query("/")
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_command_palette_repaired.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_command_palette_repaired.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 4. Portrait UserPanel Responsive
        print("\n4. Capturing Portrait UserPanel Responsive...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(65, 42)) as pilot:
            await pilot.pause()
            up = UserPanel(lambda: {"user": {"name": "ADMIN"}, "model": "nemotron-3-ultra", "provider": "nvidia"})
            app.push_screen(up)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_user_panel_responsive.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_user_panel_responsive.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 5. Portrait OpenWorkspaceScreen Responsive
        print("\n5. Capturing Portrait OpenWorkspaceScreen Responsive...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(65, 42)) as pilot:
            await pilot.pause()
            ows = OpenWorkspaceScreen()
            app.push_screen(ows)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_open_workspace_responsive.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_open_workspace_responsive.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 6. Portrait RecentWorkspacesScreen Responsive
        print("\n6. Capturing Portrait RecentWorkspacesScreen Responsive...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(65, 42)) as pilot:
            await pilot.pause()
            rws = RecentWorkspacesScreen()
            app.push_screen(rws)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_recent_workspaces_responsive.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_recent_workspaces_responsive.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        await browser.close()

    print("\n" + "=" * 70)
    print("ALL V3 EVIDENCE CAPTURED AND RENDERED SUCCESSFULLY")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(capture_all_v3())

