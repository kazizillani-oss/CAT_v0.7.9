import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        with open('scratch/test_borders_3d.svg', 'r', encoding='utf-8') as f:
            svg = f.read()
        html = f"<!DOCTYPE html><html><body style='margin:0;background:#14151f;'>{svg}</body></html>"
        await page.set_content(html)
        el = await page.query_selector('svg')
        if el:
            await el.screenshot(path='scratch/test_borders_3d.png')
            print('Saved scratch/test_borders_3d.png')
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())

