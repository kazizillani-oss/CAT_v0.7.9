import os
import sys
import asyncio
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"c:\Users\ADMIN\OneDrive\PlayGround_Official\Dev_Project_PlayGorund{Dp{P} }_Official_v0.5\CAT_v0.7.9"
sys.path.insert(0, ROOT)

from calc_terminal.app import App
from calc_terminal.ui.app import CCTApp
from calc_terminal.ui.workspace import WorkspaceShell
from calc_terminal.ui.sidebar import Explorer
from calc_terminal.ui.editor import EditorPane

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

async def render_svg_to_png(svg_path, png_path):
    with open(svg_path, "r", encoding="utf-8") as f:
        svg_markup = f.read()

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    margin: 0;
    padding: 0;
    background: #14151f;
    display: flex;
    justify-content: center;
    align-items: center;
  }}
  svg {{
    display: block;
    box-shadow: 0 10px 30px rgba(0,0,0,0.8);
  }}
</style>
</head>
<body>
{svg_markup}
</body>
</html>"""

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html)
        svg_element = await page.query_selector("svg")
        if svg_element:
            box = await svg_element.bounding_box()
            await page.set_viewport_size({"width": max(100, int(box["width"]) + 20), "height": max(100, int(box["height"]) + 20)})
            await svg_element.screenshot(path=png_path)
        else:
            await page.screenshot(path=png_path, full_page=True)
        await browser.close()
    print(f"  [Playwright] Rendered {os.path.basename(png_path)}")

async def capture_views():
    repl = App()
    stats = {"solved": 0, "provider": "none", "model": "none"}
    app = CCTApp(repl, repl.history, stats)
    async with app.run_test(size=(72, 40)) as pilot:
        await pilot.pause()
        shell = app.query_one(WorkspaceShell)
        
        # 1. VS Code portrait terminal on launch (72x40) - verifying dashboard is visible, NOT blank!
        svg1 = os.path.join(ARTIFACT_DIR, "vscode_terminal_portrait_launch.svg")
        png1 = os.path.join(ARTIFACT_DIR, "vscode_terminal_portrait_launch.png")
        with open(svg1, "w", encoding="utf-8") as f:
            f.write(app.export_screenshot(title="VS Code Portrait Launch (72x40) - CAT Dashboard Rendered"))
        await render_svg_to_png(svg1, png1)
        
        # 2. Explorer opened full-screen with Back to CAT button
        shell.toggle_sidebar()
        await pilot.pause()
        svg2 = os.path.join(ARTIFACT_DIR, "portrait_explorer_with_back_btn.svg")
        png2 = os.path.join(ARTIFACT_DIR, "portrait_explorer_with_back_btn.png")
        with open(svg2, "w", encoding="utf-8") as f:
            f.write(app.export_screenshot(title="Portrait Explorer Full-Screen with Back to CAT Button"))
        await render_svg_to_png(svg2, png2)
        
        # 3. Click Back to CAT in Explorer -> Dashboard restored
        await pilot.click("#cct-sidebar-back-btn")
        await pilot.pause()
        svg3 = os.path.join(ARTIFACT_DIR, "portrait_dashboard_returned_from_explorer.svg")
        png3 = os.path.join(ARTIFACT_DIR, "portrait_dashboard_returned_from_explorer.png")
        with open(svg3, "w", encoding="utf-8") as f:
            f.write(app.export_screenshot(title="Portrait Dashboard Restored from Explorer"))
        await render_svg_to_png(svg3, png3)
        
        # 4. Open a file -> Full-screen Code Editor with Back to CAT button
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tf:
            tf.write(b"def cat_agent():\n    return 'ready'\n")
            tname = tf.name
        shell.open_file(tname)
        await pilot.pause()
        svg4 = os.path.join(ARTIFACT_DIR, "portrait_editor_with_back_btn.svg")
        png4 = os.path.join(ARTIFACT_DIR, "portrait_editor_with_back_btn.png")
        with open(svg4, "w", encoding="utf-8") as f:
            f.write(app.export_screenshot(title="Portrait Code Editor Full-Screen with Back to CAT Button"))
        await render_svg_to_png(svg4, png4)
        
        # 5. Click Back to CAT in Editor -> Dashboard and Composer restored
        await pilot.click("#cct-tb-back")
        await pilot.pause()
        svg5 = os.path.join(ARTIFACT_DIR, "portrait_dashboard_returned_from_editor.svg")
        png5 = os.path.join(ARTIFACT_DIR, "portrait_dashboard_returned_from_editor.png")
        with open(svg5, "w", encoding="utf-8") as f:
            f.write(app.export_screenshot(title="Portrait Dashboard Restored from Editor"))
        await render_svg_to_png(svg5, png5)

if __name__ == "__main__":
    asyncio.run(capture_views())

