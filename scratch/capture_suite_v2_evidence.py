import os
import sys
import asyncio
import tempfile
from playwright.async_api import async_playwright

ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.stdout.reconfigure(encoding="utf-8")

from calc_terminal.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.sidebar import Explorer
from calc_terminal.ui.editor import EditorPane
from calc_terminal.ui.composer import StickyComposer
from calc_terminal.ui.header import BrandHeader, NavPanel
from calc_terminal.ui.palette import CommandPalette

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

async def capture_all_evidence():
    print("=" * 70)
    print("CAPTURING HIGH-FIDELITY VISUAL EVIDENCE FOR V2 SUITE")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        stats = {"solved": 0, "provider": "none", "model": "none"}

        # 1. Aria Chat Composer in Portrait
        print("\n1. Capturing Portrait Aria Chat Composer...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(72, 40)) as pilot:
            await pilot.pause()
            comp = app.query_one(StickyComposer)
            comp.set_ai_mode("build")
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_aria_chat_repaired.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_aria_chat_repaired.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 2. Command Palette in Portrait
        print("\n2. Capturing Portrait Slash Command Palette...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(72, 40)) as pilot:
            await pilot.pause()
            comp = app.query_one(StickyComposer)
            palette = comp.query_one(CommandPalette)
            palette.open_for_query("/")
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_slash_command_palette.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_slash_command_palette.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 3. Portrait Header with Explorer Button
        print("\n3. Capturing Portrait Header with Explorer Button...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(72, 40)) as pilot:
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_header_with_explorer_btn.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_header_with_explorer_btn.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 4. User Menu (NavPanel) in Portrait
        print("\n4. Capturing Portrait User Menu (NavPanel)...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(72, 40)) as pilot:
            await pilot.pause()
            panel = NavPanel()
            app.push_screen(panel)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_user_menu_responsive.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_user_menu_responsive.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        # 5. Landscape Editor Split View with Close Button & ⿻
        print("\n5. Capturing Landscape Editor Split View with Close & ⿻...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(140, 45)) as pilot:
            await pilot.pause()
            shell = app.query_one(WorkspaceShell)
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tf:
                tf.write(b"# Landscape editor verification\ndef calculate():\n    return 42\n")
                tpath = tf.name
            shell.open_file(tpath)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "landscape_editor_split_with_close_btn.svg")
            png = os.path.join(ARTIFACT_DIR, "landscape_editor_split_with_close_btn.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

            # Maximize editor via ⿻
            await pilot.click("#cct-tb-split")
            await pilot.pause()
            await pilot.pause()
            svg_max = os.path.join(ARTIFACT_DIR, "landscape_editor_maximized_view.svg")
            png_max = os.path.join(ARTIFACT_DIR, "landscape_editor_maximized_view.png")
            app.save_screenshot(svg_max)
            await svg_to_png(page, svg_max, png_max)

        # 6. Portrait File opened from Explorer
        print("\n6. Capturing Portrait Editor with Back to CAT...")
        repl = App()
        app = CCTApp(repl, repl.history, stats)
        async with app.run_test(size=(75, 42)) as pilot:
            await pilot.pause()
            shell = app.query_one(WorkspaceShell)
            shell.toggle_sidebar()
            await pilot.pause()
            with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tf:
                tf.write(b"# Portrait file opened\nprint('CAT portrait editor')\n")
                tpath = tf.name
            shell.open_file(tpath)
            await pilot.pause()
            await pilot.pause()
            svg = os.path.join(ARTIFACT_DIR, "portrait_editor_opened_from_explorer.svg")
            png = os.path.join(ARTIFACT_DIR, "portrait_editor_opened_from_explorer.png")
            app.save_screenshot(svg)
            await svg_to_png(page, svg, png)

        await browser.close()

    print("\n" + "=" * 70)
    print("ALL VISUAL EVIDENCE GENERATED SUCCESSFULLY")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(capture_all_evidence())

