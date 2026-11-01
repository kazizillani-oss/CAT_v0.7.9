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
from calc_terminal.ui.header import BrandHeader
from calc_terminal.ui.sidebar import RecentWorkspacesScreen, OpenWorkspaceScreen
from calc_terminal.ui.nav_screens import UserPanel, ThemesPanel

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

async def capture_all_v4():
    print("=" * 70)
    print("CAPTURING HIGH-FIDELITY VISUAL EVIDENCE FOR V4 3D SUITE")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        stats = {"solved": 0, "provider": "none", "model": "none"}

        # 1. Landscape Header 3D Centered
        print("\n1. Capturing Landscape Header 3D...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "landscape_header_3d_centered.svg")
            png = os.path.join(ARTIFACT_DIR, "landscape_header_3d_centered.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 2. Recent Workspaces Fixed 3D
        print("\n2. Capturing Recent Workspaces Fixed 3D...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(70, 38)) as pilot:
            await pilot.pause()
            rws = RecentWorkspacesScreen()
            app.push_screen(rws)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "recent_workspaces_fixed_3d.svg")
            png = os.path.join(ARTIFACT_DIR, "recent_workspaces_fixed_3d.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 3. Open Workspace Fixed 3D
        print("\n3. Capturing Open Workspace Fixed 3D...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(70, 38)) as pilot:
            await pilot.pause()
            ows = OpenWorkspaceScreen()
            app.push_screen(ows)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "open_folder_fixed_3d.svg")
            png = os.path.join(ARTIFACT_DIR, "open_folder_fixed_3d.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 4. User Section 3D Responsive
        print("\n4. Capturing User Section 3D...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(65, 42)) as pilot:
            await pilot.pause()
            up = UserPanel(lambda: {"user": {"name": "ADMIN"}, "model": "nemotron-3-ultra", "provider": "nvidia"})
            app.push_screen(up)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "user_section_3d_responsive.svg")
            png = os.path.join(ARTIFACT_DIR, "user_section_3d_responsive.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 5. SignOut Modal 3D
        print("\n5. Capturing SignOut Modal 3D...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(65, 35)) as pilot:
            await pilot.pause()
            app._handle_signout()
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "signout_modal_3d.svg")
            png = os.path.join(ARTIFACT_DIR, "signout_modal_3d.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 6. Quit Modal 3D
        print("\n6. Capturing Quit Modal 3D...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(65, 35)) as pilot:
            await pilot.pause()
            app._handle_quit()
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "quit_modal_3d.svg")
            png = os.path.join(ARTIFACT_DIR, "quit_modal_3d.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        await browser.close()

    print("\n" + "=" * 70)
    print("ALL V4 3D EVIDENCE CAPTURED AND RENDERED SUCCESSFULLY")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(capture_all_v4())

