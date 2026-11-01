import os
import sys
import asyncio
from playwright.async_api import async_playwright

ARTIFACT_DIR = r"C:\Users\ADMIN\.gemini\antigravity\brain\6044f886-d0e4-4199-9ee7-c7349e91cb18"

async def convert_all():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        for w in [42, 45, 48, 50, 55, 60]:
            svg_path = os.path.join(ARTIFACT_DIR, f"scratch_aria_portrait_{w}x35.svg")
            png_path = os.path.join(ARTIFACT_DIR, f"scratch_aria_portrait_{w}x35.png")
            if os.path.exists(svg_path):
                with open(svg_path, "r", encoding="utf-8") as f:
                    svg_content = f.read()
                html = f"<!DOCTYPE html><html><body style='margin:0;background:#14151f;'>{svg_content}</body></html>"
                await page.set_content(html)
                el = await page.query_selector("svg")
                if el:
                    await el.screenshot(path=png_path)
                    print(f"Converted {w}x35 to {png_path}")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(convert_all())
